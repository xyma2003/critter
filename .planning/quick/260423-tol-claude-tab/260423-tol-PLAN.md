---
phase: 260423-tol
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - ui/panel.py
  - services/notes/__init__.py
  - services/diary/__init__.py
  - config.py
autonomous: true
requirements:
  - DIARY-01
  - DIARY-02
  - DIARY-03

must_haves:
  truths:
    - "每天第一次打开便签 Tab 时，自动触发当天日记生成（如果今天还没有日记）"
    - "日记条目以宠物第一人称视角写成，反映当天互动次数（喂食/玩耍/休息/抚摸）和当前心情"
    - "日记卡片在便签列表中有明显区别样式（与普通便签不同）"
    - "日记卡片只读，点击展开全文但不进入编辑模式"
    - "每日互动计数在 pet_stats.json 中持久化，重启应用后不会丢失"
  artifacts:
    - path: "services/diary/__init__.py"
      provides: "日记生成服务：调用 Claude CLI 生成宠物视角日记，返回日记文本"
      exports: ["generate_diary"]
    - path: "services/notes/__init__.py"
      provides: "notes CRUD，含 kind 字段支持（diary/note）"
    - path: "ui/panel.py"
      provides: "互动计数追踪 + Notes Tab 日记卡片渲染"
  key_links:
    - from: "ui/panel.py (_feed/_play/_sleep/_pet)"
      to: "pet_stats.json (diary_counts)"
      via: "_increment_diary_count() 写入今天的计数"
    - from: "ui/panel.py (_notes_show_list)"
      to: "services/diary"
      via: "每次打开便签 Tab 时检查 _check_and_generate_diary()"
    - from: "services/diary"
      to: "services/notes.create()"
      via: "生成后调用 notes_service.create_diary() 存入 notes.json"
---

<objective>
宠物日记：每天自动生成一条宠物视角日记，存入便签 Tab，日记卡片有特殊样式。

Purpose: 让 Critter 产生「有历史感」的陪伴感——用户可以在便签里回顾宠物视角的每日心情和互动。
Output: 互动计数追踪 + 日记生成服务 + 便签 Tab 中的日记卡片 UI
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@ui/panel.py
@services/notes/__init__.py
@services/diary/__init__.py
@config.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: 每日互动计数持久化 + 日记触发检测</name>
  <files>ui/panel.py, services/notes/__init__.py, config.py</files>
  <action>
**1. config.py** — 添加路径常量：
```python
DIARY_COUNTS_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/diary_counts.json")
```

**2. services/notes/__init__.py** — 新增 `create_diary(content, date_str)` 函数：
```python
def create_diary(content, date_str):
    """创建日记便签，带 kind='diary' 和 date 字段。id 用时间戳，避免重复。"""
    notes = load_all()
    now = int(time.time())
    note = {
        'id': now,
        'content': content,
        'updated': now,
        'kind': 'diary',
        'date': date_str,   # 'YYYY-MM-DD'
    }
    notes.append(note)
    save_all(notes)
    return note
```

**3. ui/panel.py** — 在 `MainPanel.__init__` 或 `_build()` 附近（找 `self._decay_running` 那一块的初始化区域）：

a) 引入 `DIARY_COUNTS_FILE`：在顶部 import 区加到 `from config import ...` 那行。

b) 添加辅助方法 `_today_str()` 和 `_increment_diary_count(action)` 和 `_get_diary_counts_today()`:

```python
def _today_str(self):
    import datetime
    return datetime.date.today().isoformat()   # 'YYYY-MM-DD'

def _load_diary_counts(self):
    return load_json(DIARY_COUNTS_FILE, {})

def _increment_diary_count(self, action):
    """action: 'feed' | 'play' | 'rest' | 'pet'"""
    today = self._today_str()
    counts = self._load_diary_counts()
    day = counts.get(today, {'feed': 0, 'play': 0, 'rest': 0, 'pet': 0})
    day[action] = day.get(action, 0) + 1
    counts[today] = day
    save_json(DIARY_COUNTS_FILE, counts)

def _get_diary_counts_today(self):
    today = self._today_str()
    counts = self._load_diary_counts()
    return counts.get(today, {'feed': 0, 'play': 0, 'rest': 0, 'pet': 0})
```

c) 在 `_feed`, `_play`, `_sleep`, `_pet` 四个方法末尾各加一行：
- `_feed`: `self._increment_diary_count('feed')`
- `_play`: `self._increment_diary_count('play')`
- `_sleep`: `self._increment_diary_count('rest')`
- `_pet`: `self._increment_diary_count('pet')`

d) 添加 `_check_and_generate_diary()` 方法（在 `_build_notes_tab` 附近）：

```python
def _check_and_generate_diary(self):
    """如果今天还没有日记，后台生成一条。每次打开便签 Tab 时调用。"""
    today = self._today_str()
    all_notes = notes_service.load_all()
    already_exists = any(
        n.get('kind') == 'diary' and n.get('date') == today
        for n in all_notes
    )
    if already_exists:
        return
    # 后台生成，不阻塞 UI
    import threading
    counts = self._get_diary_counts_today()
    stats_snap = {
        'mood': round(self.stats.mood, 1),
        'hunger': round(self.stats.hunger, 1),
        'energy': round(self.stats.energy, 1),
        'mood_label': self.stats.mood_label(),
    }
    pet_name = self.pet.settings.get('pet_name', '小猫')
    pet_personality = self.pet.settings.get('pet_personality', '温柔')
    pet_catchphrase = self.pet.settings.get('pet_catchphrase', '喵~')

    def _gen():
        try:
            import services.diary as diary_service
            text = diary_service.generate_diary(
                stats_snap, counts, pet_name, pet_personality, pet_catchphrase, today
            )
            if text:
                notes_service.create_diary(text, today)
                # 如果当前仍在 notes list 模式，刷新列表
                if self.win and self.win.winfo_exists():
                    self.win.after(0, self._notes_refresh_if_list)
        except Exception:
            pass

    threading.Thread(target=_gen, daemon=True).start()

def _notes_refresh_if_list(self):
    """如果当前在便签列表模式，刷新列表（日记生成完毕后调用）。"""
    if getattr(self, '_notes_mode', 'list') == 'list':
        self._notes_show_list()
```

e) 在 `_build_notes_tab` 的 `if notes_service.load_all():` 那行之前，调用：
```python
self._check_and_generate_diary()
```

注意：`_build_notes_tab` 只在 panel 初始化时建一次，但用户每次点击便签 Tab 要重新触发检测。找到 `_switch_tab` 方法（或等价的 tab 切换逻辑），在切换到 `'notes'` tab 时也调用 `self._check_and_generate_diary()`。在 panel.py 中搜索 `_switch_tab` 或 sidebar button click handler，在切换到 notes tab 时追加：`self._check_and_generate_diary()`。
  </action>
  <verify>
    <automated>cd /Users/maxinyue09/.openclaw/workspace/desktop-pet && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -c "from ui.panel import MainPanel; from services.notes import create_diary; n=create_diary('test diary', '2026-04-23'); print('kind:', n.get('kind'), 'date:', n.get('date'))"</automated>
  </verify>
  <done>
    - `services/notes.create_diary()` 创建带 `kind='diary'` 和 `date` 字段的便签
    - `DIARY_COUNTS_FILE` 常量已在 config.py 定义
    - `_feed/_play/_sleep/_pet` 调用后计数写入 diary_counts.json
    - 便签 Tab 打开时触发 `_check_and_generate_diary()`（后台线程，不阻塞 UI）
  </done>
</task>

<task type="auto">
  <name>Task 2: 日记生成服务（Claude CLI）</name>
  <files>services/diary/__init__.py</files>
  <action>
新建 `services/diary/__init__.py`：

```python
"""
services/diary — 宠物日记生成服务
调用 Claude CLI 生成当日宠物视角日记，返回纯文本。
"""
import subprocess
import datetime
from config import CLAUDE_CLI


def generate_diary(stats_snap, counts, pet_name, pet_personality, pet_catchphrase, date_str):
    """
    生成宠物视角的每日日记。

    stats_snap: {'mood': float, 'hunger': float, 'energy': float, 'mood_label': str}
    counts:     {'feed': int, 'play': int, 'rest': int, 'pet': int}
    返回日记文本字符串，失败返回 None。
    """
    # 将日期格式化为可读形式
    try:
        d = datetime.date.fromisoformat(date_str)
        date_readable = f"{d.month}月{d.day}日"
    except Exception:
        date_readable = date_str

    # 组装互动描述
    interaction_lines = []
    if counts.get('feed', 0) > 0:
        interaction_lines.append(f"被喂食了 {counts['feed']} 次")
    if counts.get('play', 0) > 0:
        interaction_lines.append(f"玩耍了 {counts['play']} 次")
    if counts.get('rest', 0) > 0:
        interaction_lines.append(f"休息了 {counts['rest']} 次")
    if counts.get('pet', 0) > 0:
        interaction_lines.append(f"被抚摸了 {counts['pet']} 次")

    if not interaction_lines:
        interaction_lines.append("今天好像没有太多互动")

    interaction_str = "、".join(interaction_lines)

    prompt = (
        f"你是一只名叫{pet_name}的桌面小猫，性格{pet_personality}，"
        f"口头禅是"{pet_catchphrase}"。\n"
        f"今天是{date_readable}，写一条今天的日记（100字以内），"
        f"用第一人称猫咪视角，内容基于：{interaction_str}。"
        f"当前心情状态：{stats_snap.get('mood_label', '一般')}。\n"
        f"语气可爱真实，不要太正式，像猫咪在自言自语。"
        f"直接输出日记正文，不加标题、不加日期前缀。"
    )

    try:
        result = subprocess.run(
            [CLAUDE_CLI, '--print', prompt],
            capture_output=True, text=True, timeout=30
        )
        text = result.stdout.strip()
        return text if text else None
    except Exception:
        return None
```

注意：`services/diary/` 目录需要有 `__init__.py`，即这个文件本身就是 `__init__.py`，放在新建的 `services/diary/` 目录下。确保创建目录后写文件。
  </action>
  <verify>
    <automated>cd /Users/maxinyue09/.openclaw/workspace/desktop-pet && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -c "import services.diary as d; print(d.generate_diary({'mood':75,'hunger':60,'energy':50,'mood_label':'心情不错'}, {'feed':2,'play':1,'rest':0,'pet':3}, '小橘','温柔','喵~','2026-04-23'))"</automated>
  </verify>
  <done>
    - `services/diary/__init__.py` 存在，`generate_diary()` 可调用
    - 调用 Claude CLI 后返回 100 字以内的猫咪视角日记文本
    - 无互动时有 fallback 文本，subprocess 失败时返回 None
  </done>
</task>

<task type="auto">
  <name>Task 3: 日记卡片特殊样式（便签 Tab UI）</name>
  <files>ui/panel.py</files>
  <action>
在 `_build_notes_tab` → `_notes_show_list` → `_make_card` 函数中，根据 `note.get('kind') == 'diary'` 分支处理，给日记卡片以下差异化样式：

1. **背景色**：日记卡片用 `th['BG_SEL']`（蓝色选中背景）作为卡片背景，而非普通的 `th['BG_CARD']`
2. **边框色**：`highlightbackground=th['FG_ACCENT']`（accent 蓝色），`highlightthickness=2`
3. **顶部 emoji 条**：在卡片 y=4 位置放一行小 emoji："📖 宠物日记"，用 `th['FG_ACCENT']` 颜色，font size 9
4. **标题文字**：内容预览从 y=24 开始（为顶部 emoji 条让位），wraplength 略窄
5. **时间戳**：改为显示 `note.get('date', '')` 日期字符串（如 "2026-04-23"）
6. **删除按钮**：保留 × 删除按钮（日记也可删除）
7. **点击行为**：日记卡片点击后展开只读视图——不调用 `_notes_open_editor`（编辑器）而是调用新方法 `_notes_open_readonly(note_id)`

新增 `_notes_open_readonly(note_id)` 方法：
```python
def _notes_open_readonly(self, note_id):
    """日记卡片点击后展开只读全文。"""
    self._notes_mode = 'edit'   # 复用 edit 布局的 back 按钮
    th = THEMES[self._theme_mode]
    notes = notes_service.load_all()

    if self._notes_list_frame:
        self._notes_list_frame.pack_forget()

    self._notes_current_id = note_id
    content = ''
    date_str = ''
    for n in notes:
        if n['id'] == note_id:
            content = n['content']
            date_str = n.get('date', '')
            break

    self._notes_title_label.configure(text=f'📖 {date_str} 日记')
    self._notes_back_btn.pack(side=tk.LEFT, pady=4)
    # 不显示保存按钮

    self._notes_text.configure(state=tk.NORMAL)
    self._notes_text.delete('1.0', tk.END)
    self._notes_text.insert('1.0', content)
    self._notes_text.configure(state=tk.DISABLED)   # 只读
    self._notes_text.pack(fill=tk.BOTH, expand=True)
```

修改 `_make_card` 函数：在函数开头根据 `note.get('kind') == 'diary'` 决定 `is_diary = True/False`，然后条件化地设置 card 背景、边框、click handler。

具体修改：
```python
def _make_card(parent, note, col, row_i):
    is_diary = note.get('kind') == 'diary'
    card_bg = th['BG_SEL'] if is_diary else th['BG_CARD']
    border_color = th['FG_ACCENT'] if is_diary else th['BORDER']
    border_thickness = 2 if is_diary else 1

    card = tk.Frame(parent, bg=card_bg,
                    highlightbackground=border_color,
                    highlightthickness=border_thickness,
                    cursor='hand2', width=CARD_W, height=120)
    card.grid(row=row_i, column=col, padx=6, pady=6, sticky='nsew')
    card.pack_propagate(False)

    if is_diary:
        # 顶部 emoji 标签条
        tk.Label(card, text='📖 宠物日记', bg=card_bg, fg=th['FG_ACCENT'],
                 font=('PingFang SC', 9)).place(x=8, y=4)
        title_y = 22
        date_display = note.get('date', '')
    else:
        title_y = 8
        date_display = time.strftime('%m/%d %H:%M', time.localtime(note.get('updated', 0)))

    title = (note['content'][:20].replace('\n', ' ') + '…') if len(note['content']) > 20 else note['content'].replace('\n', ' ')
    tk.Label(card, text=title or '（空日记）' if is_diary else '（空便签）',
             bg=card_bg, fg=th['FG_MAIN'],
             font=('PingFang SC', 11), wraplength=CARD_W - 16,
             justify=tk.LEFT, anchor='nw').place(x=8, y=title_y, width=CARD_W-16, height=64)

    tk.Label(card, text=date_display, bg=card_bg, fg=th['FG_MUTED'],
             font=('PingFang SC', 9)).place(x=8, y=94)

    del_btn = tk.Label(card, text='×', bg=card_bg, fg=th['FG_MUTED'],
                       font=('PingFang SC', 14, 'bold'), cursor='hand2')
    del_btn.place(x=CARD_W-20, y=2)

    def _open(e, nid=note['id']):
        if is_diary:
            self._notes_open_readonly(nid)
        else:
            self._notes_open_editor(nid)

    def _delete(e, nid=note['id']):
        self._notes_delete(nid)
    def _enter(e):
        card.configure(highlightbackground=th['FG_ACCENT'] if not is_diary else th['FG_GREEN'])
    def _leave(e):
        card.configure(highlightbackground=border_color)

    for w in (card,):
        w.bind('<Button-1>', _open)
        w.bind('<Enter>', _enter)
        w.bind('<Leave>', _leave)
    del_btn.bind('<Button-1>', _delete)
    del_btn.bind('<Enter>', lambda e: del_btn.configure(fg=th['FG_RED']))
    del_btn.bind('<Leave>', lambda e: del_btn.configure(fg=th['FG_MUTED']))
```

将 `_notes_show_list` 中原有的 `_make_card` 函数体完整替换为上述版本。
  </action>
  <verify>
    <automated>cd /Users/maxinyue09/.openclaw/workspace/desktop-pet && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -c "import ast, sys; ast.parse(open('ui/panel.py').read()); print('panel.py syntax OK')"</automated>
  </verify>
  <done>
    - 日记卡片背景为 BG_SEL（蓝调），边框为 FG_ACCENT，厚度 2px
    - 卡片顶部显示 "📖 宠物日记" 标签
    - 点击日记卡片进入只读展开视图（不可编辑）
    - 普通便签卡片行为不变
    - panel.py 语法检查通过
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    - 每次喂食/玩耍/休息/抚摸时，互动计数写入 diary_counts.json
    - 打开便签 Tab 时，若今日无日记，后台调用 Claude CLI 生成日记并存入 notes.json
    - 便签列表中，日记卡片有蓝色边框 + "📖 宠物日记" 顶部标签
    - 点击日记卡片展开只读全文
  </what-built>
  <how-to-verify>
    1. 启动应用：`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 /Users/maxinyue09/.openclaw/workspace/desktop-pet/main.py`
    2. 点击宠物，打开主面板
    3. 先去宠物 Tab 点几下喂食/玩耍/抚摸按钮
    4. 切换到便签 Tab，等待约 5-15 秒
    5. 验证：便签列表中出现一张蓝色边框的 "📖 宠物日记" 卡片
    6. 点击日记卡片，应展开只读全文（猫咪视角的今日日记，约 100 字）
    7. 确认不能在编辑框里打字
    8. 点击返回，回到卡片列表
    9. 重启应用后再次打开便签 Tab，验证：日记卡片仍然存在（持久化）
    10. 检查 `/Users/maxinyue09/.openclaw/workspace/desktop-pet/diary_counts.json` 是否记录了今日计数
  </how-to-verify>
  <resume-signal>功能正常则输入 "approved"；有问题请描述（如：日记卡片未出现 / 样式不对 / 报错信息）</resume-signal>
</task>

</tasks>

<verification>
- `services/diary/__init__.py` 可被导入，`generate_diary()` 函数存在
- `services/notes.create_diary()` 创建的便签含 `kind='diary'` 和 `date` 字段
- `panel.py` 语法检查通过（`ast.parse`）
- `diary_counts.json` 在互动后被创建和更新
- 便签 Tab 中日记卡片样式与普通便签有明显区分
</verification>

<success_criteria>
- 当天第一次打开便签 Tab 时自动生成宠物日记（后台，不卡 UI）
- 日记基于真实互动次数和当前心情
- 日记卡片外观明显区别于普通便签（蓝色边框/背景 + 📖 标签）
- 日记只读，普通便签可编辑
- 互动计数持久化到 diary_counts.json，重启不丢失
</success_criteria>

<output>
完成后创建 `.planning/quick/260423-tol-claude-tab/260423-tol-SUMMARY.md`
</output>
