---
phase: 260423-gqd
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - config.py
  - ui/pet_window.py
  - ui/panel.py
autonomous: true
requirements: [CUSTOM-IMG-01, CUSTOM-IMG-02, CUSTOM-IMG-03, CUSTOM-IMG-04]

must_haves:
  truths:
    - "用户可在 Settings Tab 宠物形象卡片内点击上传图片，选择 PNG/JPG/WEBP 后悬浮窗立即替换 emoji 为圆形头像"
    - "Pet Tab 左侧头像区域显示 60px 圆形自定义图片（未上传时回退到 mood emoji）"
    - "点击重置按钮后悬浮窗恢复 emoji、Pet Tab 回退到 mood emoji"
    - "重启应用后自定义头像持久保留（读取 data/pet_avatar.png）"
  artifacts:
    - path: "config.py"
      provides: "PET_AVATAR_FILE 常量"
      contains: "PET_AVATAR_FILE"
    - path: "ui/pet_window.py"
      provides: "_load_avatar, reload_avatar, _draw_pet"
      exports: ["reload_avatar"]
    - path: "ui/panel.py"
      provides: "_refresh_pet_tab_avatar, _upload_avatar, _reset_avatar, 上传/重置按钮"
  key_links:
    - from: "ui/panel.py _upload_avatar"
      to: "ui/pet_window.py reload_avatar"
      via: "self.pet.reload_avatar()"
    - from: "ui/panel.py _upload_avatar"
      to: "ui/panel.py _refresh_pet_tab_avatar"
      via: "self._refresh_pet_tab_avatar()"
    - from: "ui/pet_window.py _draw_pet"
      to: "self._avatar_photo"
      via: "canvas.create_image with instance ref"
---

<objective>
Phase 4 自定义宠物图片：让用户能上传图片作为宠物头像，Pillow 圆形裁剪后存到 data/pet_avatar.png，悬浮窗替换 emoji 显示圆形头像，Pet Tab 头像也同步，Settings Tab 新增上传和重置按钮。

Purpose: 实现 Phase 4 核心功能——个性化宠物视觉，让桌面宠物更有专属感。
Output: config.py + pet_window.py + panel.py 三个文件的修改，无新文件。
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260423-gqd-phase-4-ui-pillow-emoji-tab/260423-gqd-RESEARCH.md

<interfaces>
<!-- Key existing code the executor must know. No codebase exploration needed. -->

From config.py (lines 6–16):
```python
NEWS_SCRIPT    = os.path.expanduser("~/.openclaw/workspace/skills/...")
CACHE_FILE     = os.path.expanduser("~/.openclaw/workspace/desktop-pet/news_cache.json")
# ... all paths follow this pattern
PET_STATS_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/pet_stats.json")
```
Add after PET_STATS_FILE:
```python
PET_AVATAR_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/data/pet_avatar.png")
```

From ui/pet_window.py (lines 159–167) — current _draw_emoji:
```python
def _draw_emoji(self, offset_y):
    self.canvas.delete('all')
    emoji = self.settings.get('pet_emoji', '🐱')
    font_size = max(20, int(self.w * 0.6))
    cx = self.w // 2
    cy = self.h // 2 + offset_y
    self.canvas.create_text(cx, cy, text=emoji,
                            font=('Apple Color Emoji', font_size),
                            anchor='center')
```
Line 155 calls: `self._draw_emoji(offset_y)`

From ui/panel.py — three locations to touch:
1. Line 1682–1685: `_pet_emoji_label` tk.Label (to replace with Canvas):
```python
self._pet_emoji_label = tk.Label(left,
    text=self.stats.mood_emoji(),
    bg=th['BG_CONTENT'], font=('Apple Color Emoji', 72))
self._pet_emoji_label.pack(pady=(20, 4))
```
2. Lines 1776–1777 in `_sync_pet_ui`:
```python
if hasattr(self, '_pet_emoji_label') and self._pet_emoji_label.winfo_exists():
    self._pet_emoji_label.configure(text=mood_em)
```
3. Lines 2501–2513 in `_build_settings_tab` — end of card1 block (after emoji row):
```python
card1 = _section('宠物形象')
row = tk.Frame(card1, bg=th['BG_CARD'])
row.pack(fill=tk.X, padx=16, pady=12)
# emoji picker row ends here; add divider + upload row after pack
```
4. Lines 2592–2593 in `_set_emoji`:
```python
if hasattr(self, '_pet_emoji_label'):
    self._pet_emoji_label.configure(text=em)
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: config.py 添加 PET_AVATAR_FILE 常量</name>
  <files>config.py</files>
  <action>
在 config.py 的 PET_STATS_FILE 行（第 15 行）之后添加一行：

```python
PET_AVATAR_FILE   = os.path.expanduser("~/.openclaw/workspace/desktop-pet/data/pet_avatar.png")
```

紧跟 PET_STATS_FILE，保持缩进对齐风格（用空格对齐等号列）。不改动其他任何内容。
  </action>
  <verify>
    <automated>grep -n "PET_AVATAR_FILE" /Users/maxinyue09/.openclaw/workspace/desktop-pet/config.py</automated>
  </verify>
  <done>config.py 包含 PET_AVATAR_FILE 常量，指向 data/pet_avatar.png</done>
</task>

<task type="auto">
  <name>Task 2: pet_window.py — 添加头像加载逻辑，_draw_emoji 改为 _draw_pet</name>
  <files>ui/pet_window.py</files>
  <action>
三处修改，全部在 ui/pet_window.py：

**修改 A — __init__ 中初始化 _avatar_photo**
在 `self.canvas.pack(...)` 之后（canvas pack 完成，Tk root 已存在），添加：
```python
self._avatar_photo = self._load_avatar()
```

**修改 B — 添加两个方法，放在 _draw_emoji 定义之前**
```python
def _load_avatar(self):
    """加载 pet_avatar.png -> 圆形裁剪 ImageTk.PhotoImage，失败返回 None。"""
    from config import PET_AVATAR_FILE
    try:
        from PIL import Image, ImageDraw, ImageTk
    except ImportError:
        return None
    if not os.path.exists(PET_AVATAR_FILE):
        return None
    size = self.w
    size4 = size * 4
    src = Image.open(PET_AVATAR_FILE).convert('RGBA')
    src = src.resize((size4, size4), Image.LANCZOS)
    mask = Image.new('L', (size4, size4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size4, size4), fill=255)
    src.putalpha(mask)
    result = src.resize((size, size), Image.LANCZOS)
    return ImageTk.PhotoImage(result)

def reload_avatar(self):
    """由 MainPanel 在保存/重置头像后调用。"""
    self._avatar_photo = self._load_avatar()
```

**修改 C — 将 _draw_emoji 改名为 _draw_pet，并修改渲染逻辑**
将现有的 `_draw_emoji` 方法整体替换为：
```python
def _draw_pet(self, offset_y):
    self.canvas.delete('all')
    cx = self.w // 2
    cy = self.h // 2 + offset_y
    if self._avatar_photo:
        self.canvas.create_image(cx, cy, image=self._avatar_photo, anchor='center')
        self.canvas._avatar_ref = self._avatar_photo   # 防止 GC
    else:
        emoji = self.settings.get('pet_emoji', '🐱')
        font_size = max(20, int(self.w * 0.6))
        self.canvas.create_text(cx, cy, text=emoji,
                                font=('Apple Color Emoji', font_size),
                                anchor='center')
```

同时将第 155 行的调用 `self._draw_emoji(offset_y)` 改为 `self._draw_pet(offset_y)`。

注意：`os` 模块已在 pet_window.py 中 import，无需重复添加。
  </action>
  <verify>
    <automated>grep -n "_draw_pet\|_load_avatar\|reload_avatar\|_avatar_photo" /Users/maxinyue09/.openclaw/workspace/desktop-pet/ui/pet_window.py</automated>
  </verify>
  <done>pet_window.py 包含 _load_avatar、reload_avatar、_draw_pet 三个方法；_animate 调用 _draw_pet；不再有 _draw_emoji 残留</done>
</task>

<task type="auto">
  <name>Task 3: panel.py — Pet Tab 头像 Canvas + Settings Tab 上传/重置行 + _sync_pet_ui 修复</name>
  <files>ui/panel.py</files>
  <action>
五处修改，全部在 ui/panel.py：

**修改 A — _build_pet_tab：替换 _pet_emoji_label tk.Label 为 Canvas**
找到（约第 1682–1685 行）：
```python
self._pet_emoji_label = tk.Label(left,
    text=self.stats.mood_emoji(),
    bg=th['BG_CONTENT'], font=('Apple Color Emoji', 72))
self._pet_emoji_label.pack(pady=(20, 4))
```
替换为：
```python
self._pet_avatar_canvas = tk.Canvas(
    left, width=60, height=60,
    bg=th['BG_CONTENT'], highlightthickness=0, bd=0)
self._pet_avatar_canvas.pack(pady=(20, 4))
self._refresh_pet_tab_avatar()
```

**修改 B — _sync_pet_ui：不再 configure _pet_emoji_label，改为刷新头像**
找到（约第 1776–1777 行）：
```python
if hasattr(self, '_pet_emoji_label') and self._pet_emoji_label.winfo_exists():
    self._pet_emoji_label.configure(text=mood_em)
```
替换为：
```python
self._refresh_pet_tab_avatar()
```

**修改 C — _set_emoji：移除对 _pet_emoji_label 的 configure**
找到（约第 2592–2593 行）：
```python
if hasattr(self, '_pet_emoji_label'):
    self._pet_emoji_label.configure(text=em)
```
替换为：
```python
self._refresh_pet_tab_avatar()
```

**修改 D — _build_settings_tab：在 card1（宠物形象）的 emoji 行 pack 之后添加分割线 + 上传行**
找到 card1 的 emoji picker row 末尾（emoji loop 的 b.bind 之后，card2 = _section 之前），插入：
```python
        # ── 自定义头像行 ──
        tk.Frame(card1, bg=th['DIVIDER'], height=1).pack(fill=tk.X, padx=16)
        row_avatar = tk.Frame(card1, bg=th['BG_CARD'])
        row_avatar.pack(fill=tk.X, padx=16, pady=10)
        tk.Label(row_avatar, text='自定义头像', bg=th['BG_CARD'], fg=th['FG_MUTED'],
                 font=('PingFang SC', 11), width=8, anchor='w').pack(side=tk.LEFT)
        btn_upload = tk.Label(row_avatar, text='上传图片', bg=th['FG_ACCENT'],
                              fg='#ffffff', font=('PingFang SC', 11), padx=10, pady=3,
                              cursor='hand2')
        btn_upload.pack(side=tk.LEFT, padx=(0, 8))
        btn_upload.bind('<Button-1>', lambda e: self._upload_avatar())
        btn_reset = tk.Label(row_avatar, text='重置默认', bg=th['BG_HOVER'],
                             fg=th['FG_MUTED'], font=('PingFang SC', 11), padx=10, pady=3,
                             cursor='hand2')
        btn_reset.pack(side=tk.LEFT)
        btn_reset.bind('<Button-1>', lambda e: self._reset_avatar())
        self._avatar_status = tk.Label(row_avatar, text='', bg=th['BG_CARD'],
                                       fg=th['FG_GREEN'], font=('PingFang SC', 11))
        self._avatar_status.pack(side=tk.LEFT, padx=(10, 0))
```

**修改 E — 添加三个新方法到 MainPanel 类**
在 `_set_emoji` 方法之后（约第 2589 行），添加三个方法：

```python
    def _refresh_pet_tab_avatar(self):
        """刷新 Pet Tab 左侧头像 Canvas：有自定义图则显示圆形图，否则显示 mood emoji。"""
        if not (hasattr(self, '_pet_avatar_canvas') and
                self._pet_avatar_canvas.winfo_exists()):
            return
        c = self._pet_avatar_canvas
        c.delete('all')
        from config import PET_AVATAR_FILE
        try:
            from PIL import Image, ImageDraw, ImageTk
            if os.path.exists(PET_AVATAR_FILE):
                size4 = 240
                img = Image.open(PET_AVATAR_FILE).convert('RGBA')
                img = img.resize((size4, size4), Image.LANCZOS)
                mask = Image.new('L', (size4, size4), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size4, size4), fill=255)
                img.putalpha(mask)
                img = img.resize((60, 60), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                c.create_image(30, 30, image=photo, anchor='center')
                c._img_ref = photo
                return
        except Exception:
            pass
        # fallback: mood emoji
        c.create_text(30, 30, text=self.stats.mood_emoji(),
                      font=('Apple Color Emoji', 40), anchor='center')

    def _upload_avatar(self):
        """打开文件选择对话框，复制到 PET_AVATAR_FILE，刷新悬浮窗和 Pet Tab。"""
        from tkinter import filedialog
        import shutil
        path = filedialog.askopenfilename(
            title='选择宠物图片',
            filetypes=[('图片', '*.png *.jpg *.jpeg *.webp'), ('所有文件', '*.*')]
        )
        if not path:
            return
        from config import PET_AVATAR_FILE
        os.makedirs(os.path.dirname(PET_AVATAR_FILE), exist_ok=True)
        shutil.copy(path, PET_AVATAR_FILE)
        self.pet.reload_avatar()
        self._refresh_pet_tab_avatar()
        if hasattr(self, '_avatar_status'):
            self._avatar_status.configure(text='已更新')
            self.win.after(2000, lambda: self._avatar_status.configure(text=''))

    def _reset_avatar(self):
        """删除 PET_AVATAR_FILE，恢复悬浮窗 emoji 和 Pet Tab mood emoji。"""
        from config import PET_AVATAR_FILE
        if os.path.exists(PET_AVATAR_FILE):
            os.remove(PET_AVATAR_FILE)
        self.pet.reload_avatar()
        self._refresh_pet_tab_avatar()
        if hasattr(self, '_avatar_status'):
            self._avatar_status.configure(text='已恢复默认')
            self.win.after(2000, lambda: self._avatar_status.configure(text=''))
```

注意：`os` 模块已在 panel.py 中 import，无需重复添加。
  </action>
  <verify>
    <automated>grep -n "_refresh_pet_tab_avatar\|_upload_avatar\|_reset_avatar\|_pet_avatar_canvas\|_avatar_status" /Users/maxinyue09/.openclaw/workspace/desktop-pet/ui/panel.py</automated>
  </verify>
  <done>panel.py 包含 _refresh_pet_tab_avatar/_upload_avatar/_reset_avatar 三个方法；Pet Tab 不再有 _pet_emoji_label；Settings Tab 宠物形象卡片内有上传/重置按钮行</done>
</task>

</tasks>

<verification>
启动应用验证：
```
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 /Users/maxinyue09/.openclaw/workspace/desktop-pet/main.py
```
1. 打开主面板 -> Settings Tab -> 宠物形象卡片下方有「自定义头像」行，含「上传图片」「重置默认」按钮
2. 点击「上传图片」，选择一张图片，悬浮窗从 emoji 变为圆形头像
3. 切换到 Pet Tab，左侧显示 60px 圆形头像
4. 点击「重置默认」，悬浮窗恢复 emoji，Pet Tab 恢复 mood emoji
5. 重启应用，若 data/pet_avatar.png 存在，悬浮窗仍显示圆形头像
</verification>

<success_criteria>
- config.py 有 PET_AVATAR_FILE 常量
- 悬浮窗在 data/pet_avatar.png 存在时显示圆形头像，不存在时显示 emoji（向后兼容）
- Settings Tab 宠物形象卡片有上传+重置按钮，操作后立即生效
- Pet Tab 头像 Canvas 与悬浮窗状态同步
- 应用启动无错误（即使 Pillow import 失败也能回退到 emoji）
</success_criteria>

<output>
After completion, create `.planning/quick/260423-gqd-phase-4-ui-pillow-emoji-tab/260423-gqd-SUMMARY.md`
</output>
