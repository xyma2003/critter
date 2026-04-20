#!/usr/bin/env python3
"""
桌面宠物 - 主程序
猫咪永远置顶悬浮，主面板普通窗口（可被其他窗口遮挡）
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
import json
import time
import os
import re
import math
import subprocess
import random
import ctypes

NEWS_SCRIPT = os.path.expanduser("~/.openclaw/workspace/skills/news-digest/scripts/fetch_news.py")
CACHE_FILE  = os.path.expanduser("~/.openclaw/workspace/desktop-pet/web-pet/news_cache.json")
NOTE_FILE   = os.path.expanduser("~/.openclaw/workspace/desktop-pet/notes.json")
SETTINGS_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/settings.json")
CACHE_TTL   = 30 * 60
BOOKMARKS_FILE   = os.path.expanduser("~/.openclaw/workspace/desktop-pet/bookmarks.json")
USER_PROFILE_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/user_profile.json")

# ── 颜色主题 ──────────────────────────────────────────
THEMES = {
    "dark": {
        "BG_WIN":     "#1a1a1a",
        "BG_SIDEBAR": "#141414",
        "BG_CONTENT": "#1e1e1e",
        "BG_CARD":    "#262626",
        "BG_TOOLBAR": "#141414",
        "BG_HOVER":   "#2e2e2e",
        "BG_SEL":     "#1e3a52",
        "FG_MAIN":    "#e8e8e8",
        "FG_DIM":     "#909090",
        "FG_MUTED":   "#b0b0b0",
        "FG_ACCENT":  "#4fc3f7",
        "FG_GREEN":   "#81c784",
        "FG_YELLOW":  "#ffd54f",
        "FG_RED":     "#ef5350",
        "BORDER":     "#333333",
        "DIVIDER":    "#2a2a2a",
        "BG_BTN":     "#1565c0",
        "ACCENT_BAR": "#4fc3f7",
    },
    "light": {
        "BG_WIN":     "#ffffff",
        "BG_SIDEBAR": "#f5f5f5",
        "BG_CONTENT": "#ffffff",
        "BG_CARD":    "#ffffff",
        "BG_TOOLBAR": "#fafafa",
        "BG_HOVER":   "#f0f7ff",
        "BG_SEL":     "#e3f2fd",
        "FG_MAIN":    "#1a1a1a",
        "FG_DIM":     "#555555",
        "FG_MUTED":   "#888888",
        "FG_ACCENT":  "#0078d4",
        "FG_GREEN":   "#2e7d32",
        "FG_YELLOW":  "#f57f17",
        "FG_RED":     "#c62828",
        "BORDER":     "#e8e8e8",
        "DIVIDER":    "#efefef",
        "BG_BTN":     "#0078d4",
        "ACCENT_BAR": "#0078d4",
    },
}

# ── 全局颜色常量（兼容旧引用）──────────────────────────
BG_DARK    = "#161616"
BG_PANEL   = "#242424"
BG_CARD    = "#2e2e2e"
BG_HOVER   = "#3a3a3a"
FG_MAIN    = "#e0e0e0"
FG_DIM     = "#666666"
FG_ACCENT  = "#4fc3f7"
FG_GREEN   = "#81c784"
FG_YELLOW  = "#ffd54f"
FG_RED     = "#ef5350"
BORDER     = "#2e2e2e"


# ══════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════

def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ══════════════════════════════════════════════════════
#  StorageRepository — 书签 / 稍后再看 持久化层
# ══════════════════════════════════════════════════════

class StorageRepository:
    """
    Encapsulates JSON I/O for named collections.
    Current backend: single JSON file at self._path.
    Interface is intentionally backend-agnostic so it can be
    swapped for SQLite or any other store later.

    Storage format:
        {
          "bookmarks": [...],
          "read_later": [...]
        }
    Each item dict must contain at minimum: id, title, link, source, saved_at.
    """

    def __init__(self, path):
        self._path = path

    def _load(self):
        return load_json(self._path, {})

    def _save(self, data):
        save_json(self._path, data)

    def add(self, collection, item):
        """
        Add item to collection.
        item must be a dict with keys: id, title, link, source, saved_at.
        If an item with the same id already exists it is silently replaced.
        Returns True on success, False on error.
        """
        try:
            data = self._load()
            items = data.get(collection, [])
            items = [x for x in items if x.get('id') != item.get('id')]
            items.append(item)
            data[collection] = items
            self._save(data)
            return True
        except Exception:
            return False

    def remove(self, collection, item_id):
        """
        Remove item by id from collection.
        No-op if item_id not found.
        Returns True on success, False on error.
        """
        try:
            data = self._load()
            items = data.get(collection, [])
            data[collection] = [x for x in items if x.get('id') != item_id]
            self._save(data)
            return True
        except Exception:
            return False

    def list_items(self, collection):
        """
        Return list of item dicts for collection (newest-first by saved_at).
        Returns empty list if collection does not exist or file missing.
        """
        try:
            data = self._load()
            items = data.get(collection, [])
            return sorted(items, key=lambda x: x.get('saved_at', ''), reverse=True)
        except Exception:
            return []

# ══════════════════════════════════════════════════════
#  PetStats — 心情 / 饱食 / 精力 数值管理
# ══════════════════════════════════════════════════════

PET_STATS_FILE = os.path.expanduser("~/.openclaw/workspace/desktop-pet/pet_stats.json")

class PetStats:
    """
    三个数值各 0-100，随时间自然衰减，互动可回复。
    数值持久化到 pet_stats.json，重启后继续。
    """
    DECAY_INTERVAL_MS = 10 * 60 * 1000   # 每 10 分钟衰减一次
    HUNGER_DECAY  = 6    # 饱食度每次 -6
    ENERGY_DECAY  = 4    # 精力每次 -4
    # 心情由饱食度和精力共同决定，不单独衰减

    # emoji 映射（根据 mood 值）
    MOOD_EMOJI = [
        (80, '😊'),
        (60, '🙂'),
        (40, '😐'),
        (20, '😔'),
        (0,  '😞'),
    ]

    def __init__(self):
        data = load_json(PET_STATS_FILE, {})
        self.hunger = float(data.get('hunger', 80))
        self.energy = float(data.get('energy', 80))
        self._compute_mood()

    def _compute_mood(self):
        self.mood = (self.hunger * 0.5 + self.energy * 0.5)

    def _clamp(self, v):
        return max(0.0, min(100.0, v))

    def feed(self):
        self.hunger = self._clamp(self.hunger + 35)
        self.energy = self._clamp(self.energy + 10)
        self._compute_mood()
        self._save()

    def play(self):
        self.hunger = self._clamp(self.hunger - 10)
        self.energy = self._clamp(self.energy - 15)
        self.mood   = self._clamp(self.mood + 20)   # 玩耍直接拉心情
        self._save()

    def rest(self):
        self.energy = self._clamp(self.energy + 40)
        self._compute_mood()
        self._save()

    def on_chat(self):
        """每次对话结束后调用，心情小幅提升。"""
        self.mood = self._clamp(self.mood + 8)
        self._save()

    def decay(self):
        """定时衰减，由 win.after 调用。"""
        self.hunger = self._clamp(self.hunger - self.HUNGER_DECAY)
        self.energy = self._clamp(self.energy - self.ENERGY_DECAY)
        self._compute_mood()
        self._save()

    def mood_emoji(self):
        for threshold, em in self.MOOD_EMOJI:
            if self.mood >= threshold:
                return em
        return '😞'

    def mood_label(self):
        if self.mood >= 80:
            return '😊 心情很好'
        if self.mood >= 60:
            return '🙂 还不错'
        if self.mood >= 40:
            return '😐 一般般'
        if self.mood >= 20:
            return '😔 有点低落'
        return '😞 心情很差'

    def hunger_label(self):
        if self.hunger >= 80:
            return '🍚 吃得饱饱'
        if self.hunger >= 55:
            return '😋 不太饿'
        if self.hunger >= 30:
            return '😐 有点饿了'
        return '😫 好饿好饿'

    def energy_label(self):
        if self.energy >= 80:
            return '⚡ 精力充沛'
        if self.energy >= 55:
            return '🙂 还有劲'
        if self.energy >= 30:
            return '😴 有点困'
        return '🌙 累坏了'

    def system_prompt_hint(self):
        """返回注入 system prompt 的心情描述。"""
        if self.mood >= 80:
            return '你现在心情很好，说话活泼开朗，喜欢用叠词和撒娇语气。'
        if self.mood >= 60:
            return '你现在心情不错，正常温柔可爱。'
        if self.mood >= 40:
            return '你现在心情一般，话少一点，偶尔叹气。'
        if self.mood >= 20:
            return '你现在有点低落，说话简短，偶尔委屈。'
        return '你现在心情很差，说话有气无力，会撒娇说想被陪伴。'

    def _save(self):
        save_json(PET_STATS_FILE, {
            'hunger': round(self.hunger, 1),
            'energy': round(self.energy, 1),
            'mood':   round(self.mood, 1),
        })


def load_settings():
    return load_json(SETTINGS_FILE, {
        'auto_refresh_min': 30,
        'notify_on_refresh': False,
        'pet_emoji': '🐱',
        'pet_size': 76,
    })

def save_settings(s):
    save_json(SETTINGS_FILE, s)

def load_cache():
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('content'), data.get('timestamp', 0)
    except Exception:
        return None, 0

def save_cache(content):
    save_json(CACHE_FILE, {'content': content, 'timestamp': time.time()})

def fetch_news_raw():
    result = subprocess.run(['python3', NEWS_SCRIPT],
                            capture_output=True, text=True, timeout=30)
    return result.stdout

def get_news(force=False):
    cached_content, cached_time = load_cache()
    if cached_content and (time.time() - cached_time < CACHE_TTL) and not force:
        return cached_content, True, int(cached_time)
    content = fetch_news_raw()
    save_cache(content)
    return content, False, int(time.time())

def parse_news(text):
    sections = []
    current = None
    for line in text.split('\n'):
        if line.startswith('==='):
            if current:
                sections.append(current)
            current = {'source': line.replace('===', '').strip(), 'items': []}
        elif re.match(r'^\d+\.', line) and current is not None:
            title = re.sub(r'^\d+\.\s*', '', line).strip()
            current['items'].append({'title': title, 'link': None})
        elif '🔗' in line and current and current['items']:
            current['items'][-1]['link'] = line.replace('🔗', '').strip()
    if current:
        sections.append(current)
    return sections

def send_notification(title, body):
    safe_t = title.replace('"', '\\"').replace("'", "\\'")
    safe_b = body.replace('"', '\\"').replace("'", "\\'")
    script = f'display notification "{safe_b}" with title "{safe_t}" sound name "Blow"'
    subprocess.run(['osascript', '-e', script], timeout=5)


def _translate_titles_with_claude(titles):
    """用 Claude CLI 把英文标题批量翻译成「中文（原文）」格式。失败时返回原标题。"""
    if not titles:
        return titles
    numbered = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(titles))
    prompt = (
        '把下面的英文热搜词条翻译成中文，格式为「中文译名（原文）」，'
        '每行一条，保持编号，只输出翻译结果，不要解释：\n' + numbered
    )
    try:
        result = subprocess.run(
            ['/opt/homebrew/bin/claude', '--print', prompt],
            capture_output=True, text=True, timeout=30
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        translated = []
        for line in lines:
            line = re.sub(r'^\d+\.\s*', '', line)
            translated.append(line)
        if len(translated) == len(titles):
            return translated
    except Exception:
        pass
    return titles



# ══════════════════════════════════════════════════════
#  主面板
# ══════════════════════════════════════════════════════

class MainPanel:
    WIN_W, WIN_H = 1024, 620
    NAV_W = 80

    GREETINGS = [
        ('今天还开心吗？', '不管怎样，我在这里陪着你 🐱'),
        ('嘿，你回来啦！', '我一直在等你呢 ✨'),
        ('今天吃了什么好吃的？', '记得好好吃饭，不然我要担心了 🍜'),
        ('工作顺利吗？', '休息一下，摸摸我也许会好一点 😸'),
        ('今天天气怎么样？', '不管晴雨，有我陪着就够了 🌤'),
        ('有没有让你开心的事？', '分享给我听听吧 🎉'),
        ('最近睡得好吗？', '睡眠很重要哦，我晚上都在守护你 🌙'),
        ('今天有没有喝够水？', '记得补充水分，身体是最重要的 💧'),
        ('压力大吗？', '深呼吸，一切都会好起来的 🌿'),
        ('有没有做让自己骄傲的事？', '你已经很棒了，继续加油！⭐'),
        ('今天学到什么新东西了吗？', '每天进步一点点就很好了 📚'),
        ('有没有想念的人？', '记得联系一下他们，别让感情生疏了 💌'),
        ('最近有什么小确幸？', '生活里的小美好值得被记录 🌸'),
        ('今天有没有笑一笑？', '笑一个嘛，你笑起来很好看的 😄'),
        ('有没有什么烦恼？', '说出来也许会轻松一些，我在听 👂'),
    ]

    def __init__(self, pet):
        self.pet = pet
        self.win = None
        self._news_loaded = False
        self._theme_mode = 'light'
        self._chat_sessions = []
        self._current_session_id = None
        self._storage = StorageRepository(BOOKMARKS_FILE)
        self._news_current_view = 'feed'   # 'feed' | 'bookmarks' | 'read_later'
        self._news_refresh_job = None
        self._profile_enabled = True       # 本对话是否记录用户画像，默认开
        self.stats = PetStats()            # 心情 / 饱食 / 精力数值

    # ── macOS 窗口层级修复 ────────────────────────────

    def _fix_panel_window_level(self):
        try:
            objc = ctypes.cdll.LoadLibrary('/usr/lib/libobjc.dylib')
            objc.objc_getClass.restype = ctypes.c_void_p
            objc.objc_getClass.argtypes = [ctypes.c_char_p]
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]

            def sel(name):
                return objc.sel_registerName(name.encode())

            def msg0(obj, sel_name):
                objc.objc_msgSend.restype = ctypes.c_void_p
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                return objc.objc_msgSend(obj, sel(sel_name))

            def msg_long(obj, sel_name):
                objc.objc_msgSend.restype = ctypes.c_long
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                return objc.objc_msgSend(obj, sel(sel_name))

            def nsstring_to_py(nsstr):
                if not nsstr:
                    return ''
                objc.objc_msgSend.restype = ctypes.c_char_p
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                b = objc.objc_msgSend(nsstr, sel('UTF8String'))
                return b.decode('utf-8', errors='replace') if b else ''

            NSApp_cls = objc.objc_getClass(b'NSApplication')
            NSApp = msg0(NSApp_cls, 'sharedApplication')
            windows = msg0(NSApp, 'windows')
            count = msg_long(windows, 'count')
            panel_title = self.win.title()
            nswin = None
            for i in range(count):
                objc.objc_msgSend.restype = ctypes.c_void_p
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
                w = objc.objc_msgSend(windows, sel('objectAtIndex:'), ctypes.c_ulong(i))
                t = nsstring_to_py(msg0(w, 'title'))
                if t == panel_title:
                    nswin = w
                    break

            if nswin:
                NSWindowCollectionBehaviorTransient = 1 << 3
                objc.objc_msgSend.restype = None
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
                objc.objc_msgSend(nswin, sel('setCollectionBehavior:'),
                                  ctypes.c_ulong(NSWindowCollectionBehaviorTransient))
        except Exception:
            pass

    # ── 打开 / 重新显示 ───────────────────────────────

    def open(self):
        if self.win and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            if hasattr(self, '_pet_emoji_label'):
                self._pet_emoji_label.configure(
                    text=self.pet.settings.get('pet_emoji', '🐱'))
            if hasattr(self, '_home_emoji'):
                self._home_emoji.configure(
                    text=self.pet.settings.get('pet_emoji', '🐱'))
            self._switch_tab(self._active_tab)
            return
        self._build()

    # ── 构建整体骨架 ──────────────────────────────────

    def _build(self):
        th = THEMES[self._theme_mode]

        self.win = tk.Toplevel()
        self.win.title('Critter')
        self.win.configure(bg=th['BG_WIN'])
        self.win.wm_transient('')
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - self.WIN_W) // 2
        y = (sh - self.WIN_H) // 2
        self.win.geometry(f'{self.WIN_W}x{self.WIN_H}+{x}+{y}')
        self.win.attributes('-topmost', False)
        self.win.resizable(True, True)
        self.win.protocol('WM_DELETE_WINDOW', self.win.withdraw)
        self.win.after(100, self._fix_panel_window_level)

        # ── 顶部标题栏 ──
        titlebar = tk.Frame(self.win, bg=th['BG_WIN'], height=44)
        titlebar.pack(fill=tk.X)
        titlebar.pack_propagate(False)

        tk.Label(titlebar, text='Critter',
                 bg=th['BG_WIN'], fg=th['FG_MAIN'],
                 font=('PingFang SC', 13, 'bold')).pack(side=tk.LEFT, padx=16)

        # 主题切换（右上角）
        for icon, mode in [('☀️', 'light'), ('🌙', 'dark')]:
            btn = tk.Label(titlebar, text=icon, bg=th['BG_WIN'],
                           font=('Apple Color Emoji', 15), cursor='hand2',
                           padx=8)
            btn.pack(side=tk.RIGHT, padx=2)
            btn.bind('<Button-1>', lambda e, m=mode: self._apply_theme(m))
            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=th['BG_HOVER']))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=th['BG_WIN']))
            if icon == '☀️':
                self._sun_btn = btn
            else:
                self._moon_btn = btn

        # 分隔线
        tk.Frame(self.win, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        # ── 主体：左侧导航 + 右侧内容 ──
        body = tk.Frame(self.win, bg=th['BG_WIN'])
        body.pack(fill=tk.BOTH, expand=True)

        # 左侧导航栏
        self._nav = tk.Frame(body, bg=th['BG_SIDEBAR'], width=self.NAV_W)
        self._nav.pack(side=tk.LEFT, fill=tk.Y)
        self._nav.pack_propagate(False)

        # 导航栏右侧分割线
        tk.Frame(body, bg=th['DIVIDER'], width=1).pack(side=tk.LEFT, fill=tk.Y)

        # 右侧内容区（叠放）
        self._content_host = tk.Frame(body, bg=th['BG_CONTENT'])
        self._content_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._content_host.grid_rowconfigure(0, weight=1)
        self._content_host.grid_columnconfigure(0, weight=1)

        # ── 构建各 Tab 内容 ──
        self._active_tab = 'home'
        self._nav_btns = {}
        self._tab_frames = {}

        tab_defs = [
            ('home',     '🏠', '主页'),
            ('news',     '📰', '新闻'),
            ('pet',      '🐾', '宠物'),
            ('notes',    '📝', '便签'),
            ('settings', '⚙️', '设置'),
        ]

        for key, icon, label in tab_defs:
            self._add_nav_btn(key, icon, label)

        self._tab_frames['home']     = self._build_home_tab(self._content_host)
        self._tab_frames['news']     = self._build_news_tab(self._content_host)
        self._tab_frames['pet']      = self._build_pet_tab(self._content_host)
        self._tab_frames['notes']    = self._build_notes_tab(self._content_host)
        self._tab_frames['settings'] = self._build_settings_tab(self._content_host)

        for frame in self._tab_frames.values():
            frame.grid(row=0, column=0, sticky='nsew')

        self._switch_tab('home')
        self._start_stats_decay()

    def _add_nav_btn(self, key, icon, label):
        th = THEMES[self._theme_mode]
        # 外层容器：左侧 3px active 指示条 + 右侧内容
        outer = tk.Frame(self._nav, bg=th['BG_SIDEBAR'], cursor='hand2')
        outer.pack(fill=tk.X)

        # 左侧 active 指示条（3px 宽，默认与侧边栏同色）
        bar = tk.Frame(outer, bg=th['BG_SIDEBAR'], width=3)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        bar.pack_propagate(False)

        # 右侧内容区
        inner = tk.Frame(outer, bg=th['BG_SIDEBAR'])
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        icon_lbl = tk.Label(inner, text=icon, bg=th['BG_SIDEBAR'],
                            font=('Apple Color Emoji', 20), pady=6)
        icon_lbl.pack()
        text_lbl = tk.Label(inner, text=label, bg=th['BG_SIDEBAR'],
                            fg=th['FG_DIM'], font=('PingFang SC', 9), pady=0)
        text_lbl.pack(pady=(0, 8))

        def _on_enter(e):
            if key != self._active_tab:
                for w in (outer, inner, icon_lbl, text_lbl):
                    w.configure(bg=th['BG_HOVER'])

        def _on_leave(e):
            if key != self._active_tab:
                for w in (outer, inner, icon_lbl, text_lbl):
                    w.configure(bg=th['BG_SIDEBAR'])

        for w in (outer, inner, icon_lbl, text_lbl):
            w.bind('<Button-1>', lambda e, k=key: self._switch_tab(k))
            w.bind('<Enter>', _on_enter)
            w.bind('<Leave>', _on_leave)

        self._nav_btns[key] = (outer, inner, bar, icon_lbl, text_lbl)

    # ── Tab 切换 ──────────────────────────────────────

    def _switch_tab(self, key):
        self._active_tab = key
        self._tab_frames[key].tkraise()
        th = THEMES[self._theme_mode]

        for k, (outer, inner, bar, icon_lbl, text_lbl) in self._nav_btns.items():
            if k == key:
                outer.configure(bg=th['BG_SEL'])
                inner.configure(bg=th['BG_SEL'])
                bar.configure(bg=th['ACCENT_BAR'])
                icon_lbl.configure(bg=th['BG_SEL'])
                text_lbl.configure(bg=th['BG_SEL'], fg=th['FG_ACCENT'])
            else:
                outer.configure(bg=th['BG_SIDEBAR'])
                inner.configure(bg=th['BG_SIDEBAR'])
                bar.configure(bg=th['BG_SIDEBAR'])
                icon_lbl.configure(bg=th['BG_SIDEBAR'])
                text_lbl.configure(bg=th['BG_SIDEBAR'], fg=th['FG_DIM'])

        self.win.update_idletasks()
        if key == 'news':
            self._news_canvas.event_generate('<Configure>')
            if not self._news_loaded:
                self._news_loaded = True
                self._load_news_async(force=False)

    # ── 主题切换 ──────────────────────────────────────

    def _apply_theme(self, mode):
        self._theme_mode = mode
        th = THEMES[mode]
        self._recolor_widget(self.win, th)
        self._switch_tab(self._active_tab)

    def _recolor_widget(self, widget, th):
        cls = widget.winfo_class()
        try:
            cur_bg = widget.cget('bg')
        except Exception:
            cur_bg = None

        all_bgs = {}
        all_fgs = {}
        for t in THEMES.values():
            all_bgs[t['BG_WIN']]       = th['BG_WIN']
            all_bgs[t['BG_SIDEBAR']]   = th['BG_SIDEBAR']
            all_bgs[t['BG_CONTENT']]   = th['BG_CONTENT']
            all_bgs[t['BG_CARD']]      = th['BG_CARD']
            all_bgs[t['BG_TOOLBAR']]   = th['BG_TOOLBAR']
            all_bgs[t['BG_HOVER']]     = th['BG_HOVER']
            all_bgs[t['BG_SEL']]       = th['BG_SEL']
            all_bgs[t['BG_BTN']]       = th['BG_BTN']
            all_bgs[t['ACCENT_BAR']]   = th['ACCENT_BAR']
            all_fgs[t['FG_MAIN']]      = th['FG_MAIN']
            all_fgs[t['FG_DIM']]       = th['FG_DIM']
            all_fgs[t['FG_MUTED']]     = th['FG_MUTED']
            all_fgs[t['FG_ACCENT']]    = th['FG_ACCENT']
            all_fgs[t['FG_GREEN']]     = th['FG_GREEN']
            all_fgs[t['BORDER']]       = th['BORDER']
            all_fgs[t['DIVIDER']]      = th['DIVIDER']

        if cur_bg and cur_bg in all_bgs:
            try:
                widget.configure(bg=all_bgs[cur_bg])
            except Exception:
                pass

        if cls in ('Label', 'Button', 'Checkbutton', 'Radiobutton', 'Text', 'Canvas', 'Frame'):
            try:
                cur_fg = widget.cget('fg')
                if cur_fg in all_fgs:
                    widget.configure(fg=all_fgs[cur_fg])
            except Exception:
                pass
            try:
                cur_hl = widget.cget('highlightbackground')
                if cur_hl in all_fgs:
                    widget.configure(highlightbackground=all_fgs[cur_hl])
            except Exception:
                pass

        if cls == 'Text':
            try:
                widget.configure(insertbackground=th['FG_ACCENT'],
                                 selectbackground=th['BG_SEL'])
            except Exception:
                pass

        if cls in ('Radiobutton', 'Checkbutton'):
            try:
                widget.configure(selectcolor=all_bgs.get(widget.cget('selectcolor'), th['BG_CARD']),
                                 activebackground=th['BG_CARD'])
            except Exception:
                pass

        if cls == 'Button':
            try:
                widget.configure(activebackground=th['BG_HOVER'],
                                 activeforeground=th['FG_MAIN'])
            except Exception:
                pass

        for child in widget.winfo_children():
            self._recolor_widget(child, th)


    # ══════════════════════════════════════════════════
    #  Tab: 主页（问候 + 聊天）
    # ══════════════════════════════════════════════════

    def _build_home_tab(self, parent):
        th = THEMES[self._theme_mode]
        self._chat_thinking = False
        self._chat_started = False
        frame = tk.Frame(parent, bg=th['BG_CONTENT'])

        # ══ 欢迎页 ══
        self._welcome_frame = tk.Frame(frame, bg=th['BG_CONTENT'])
        self._welcome_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 左上角：历史对话按钮
        self._history_btn = tk.Label(self._welcome_frame, text='🕐 历史对话',
            bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
            font=('PingFang SC', 11), cursor='hand2', padx=4)
        self._history_btn.place(relx=0, rely=0, anchor='nw', x=16, y=14)
        self._history_btn.bind('<Button-1>', lambda e: self._show_session_picker())
        self._history_btn.bind('<Enter>',
            lambda e: self._history_btn.configure(fg=th['FG_ACCENT']))
        self._history_btn.bind('<Leave>',
            lambda e: self._history_btn.configure(fg=th['FG_MUTED']))

        # 居中容器
        center = tk.Frame(self._welcome_frame, bg=th['BG_CONTENT'])
        center.place(relx=0.5, rely=0.42, anchor='center')

        q, sub = random.choice(self.GREETINGS)
        self._welcome_greeting = (q, sub)

        self._home_emoji = tk.Label(center,
            text=self.pet.settings.get('pet_emoji', '🐱'),
            bg=th['BG_CONTENT'], font=('Apple Color Emoji', 72))
        self._home_emoji.pack(pady=(0, 18))

        self._home_question = tk.Label(center, text=q,
            bg=th['BG_CONTENT'], fg=th['FG_MAIN'],
            font=('PingFang SC', 20, 'bold'))
        self._home_question.pack()

        self._home_sub = tk.Label(center, text=sub,
            bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
            font=('PingFang SC', 13))
        self._home_sub.pack(pady=(6, 0))

        # 时间（右上角）
        self._home_time_label = tk.Label(self._welcome_frame, text='',
            bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
            font=('PingFang SC', 11))
        self._home_time_label.place(relx=1.0, rely=0, anchor='ne', x=-20, y=14)
        self._update_home_clock()

        # 欢迎页输入栏（底部）
        welcome_input_wrap = tk.Frame(self._welcome_frame, bg=th['BG_CONTENT'])
        welcome_input_wrap.place(relx=0.5, rely=1.0, anchor='s',
                                 relwidth=0.72, y=-24)

        _ibar_h = 44
        _btn_r  = 15
        _btn_margin = 8

        wib = tk.Canvas(welcome_input_wrap, height=_ibar_h,
            bg=th['BG_CONTENT'], highlightthickness=0, bd=0)
        wib.pack(fill=tk.X)

        def _draw_pill(canvas, fill_color):
            canvas.delete('pill')
            w = canvas.winfo_width() or 600
            h = canvas.winfo_height() or _ibar_h
            r = h // 2
            canvas.create_arc(0, 0, r*2, r*2, start=90, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_arc(w-r*2, 0, w, r*2, start=0, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_arc(0, h-r*2, r*2, h, start=180, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_rectangle(r, 0, w-r, h,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_rectangle(0, r, w, h-r,
                fill=fill_color, outline=fill_color, tags='pill')

        def _draw_send_btn_w(canvas, color):
            canvas.delete('sendbtn')
            w = canvas.winfo_width() or 600
            h = canvas.winfo_height() or _ibar_h
            cx = w - _btn_r - _btn_margin
            cy = h // 2
            canvas.create_oval(cx-_btn_r, cy-_btn_r, cx+_btn_r, cy+_btn_r,
                fill=color, outline=color, tags='sendbtn')
            canvas.create_text(cx, cy, text='↑',
                fill=th['BG_WIN'], font=('PingFang SC', 13, 'bold'), tags='sendbtn')

        self._welcome_input = tk.Text(wib,
            bg=th['BG_CARD'], fg=th['FG_MAIN'],
            font=('PingFang SC', 13), relief=tk.FLAT,
            padx=4, pady=0, wrap=tk.WORD, height=1,
            insertbackground=th['FG_ACCENT'],
            selectbackground=th['BG_SEL'],
            borderwidth=0, highlightthickness=0)
        _wi_id = wib.create_window(
            _ibar_h // 2, _ibar_h // 2, anchor='w', window=self._welcome_input)

        def _refresh_wib(e=None):
            w = wib.winfo_width() or 600
            _draw_pill(wib, th['BG_CARD'])
            _draw_send_btn_w(wib, th['FG_ACCENT'])
            text_w = max(w - _ibar_h // 2 - _btn_r * 2 - _btn_margin * 2 - 8, 60)
            wib.itemconfig(_wi_id, width=text_w)
            wib.tag_raise('sendbtn')

        wib.bind('<Configure>', _refresh_wib)
        wib.after(10, _refresh_wib)

        wib.tag_bind('sendbtn', '<Button-1>', lambda e: self._send_chat())
        wib.configure(cursor='arrow')
        wib.tag_bind('sendbtn', '<Enter>', lambda e: wib.configure(cursor='hand2'))
        wib.tag_bind('sendbtn', '<Leave>', lambda e: wib.configure(cursor='arrow'))

        self._welcome_input.bind('<Return>', self._on_chat_enter)
        self._set_placeholder(self._welcome_input, '说点什么，开始聊天吧…', th)

        wib._refresh      = _refresh_wib
        wib._draw_sendbtn = _draw_send_btn_w
        self._wib         = wib
        send_w_canvas     = wib

        # ══ 聊天页 ══
        self._chat_frame = tk.Frame(frame, bg=th['BG_CONTENT'])

        # 顶部栏（聊天模式）
        chat_topbar = tk.Frame(self._chat_frame, bg=th['BG_TOOLBAR'], height=44)
        chat_topbar.pack(fill=tk.X)
        chat_topbar.pack_propagate(False)

        back_btn = tk.Label(chat_topbar, text='← 主页',
            bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
            font=('PingFang SC', 11), cursor='hand2', padx=12)
        back_btn.pack(side=tk.LEFT)
        back_btn.bind('<Button-1>', lambda e: self._back_to_welcome())
        back_btn.bind('<Enter>', lambda e: back_btn.configure(fg=th['FG_ACCENT']))
        back_btn.bind('<Leave>', lambda e: back_btn.configure(fg=th['FG_MAIN']))

        em_lbl = tk.Label(chat_topbar,
            text=self.pet.settings.get('pet_emoji', '🐱'),
            bg=th['BG_TOOLBAR'], font=('Apple Color Emoji', 16))
        em_lbl.pack(side=tk.LEFT, padx=(0, 4))
        self._chat_topbar_emoji = em_lbl

        tk.Label(chat_topbar, text='桌面宠物',
            bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
            font=('PingFang SC', 12, 'bold')).pack(side=tk.LEFT)

        # 右侧：用户画像记录开关
        self._profile_btn = tk.Label(chat_topbar, text='🧠 记录',
            bg=th['BG_TOOLBAR'], fg=th['FG_ACCENT'],
            font=('PingFang SC', 10), cursor='hand2', padx=10)
        self._profile_btn.pack(side=tk.RIGHT)
        self._profile_btn.bind('<Button-1>', lambda e: self._toggle_profile_recording())

        tk.Frame(self._chat_frame, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        # 聊天输入栏（先 pack BOTTOM）
        chat_input_bar = tk.Frame(self._chat_frame, bg=th['BG_TOOLBAR'])
        chat_input_bar.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(chat_input_bar, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        # 消息滚动区
        msg_canvas = tk.Canvas(self._chat_frame, bg=th['BG_CONTENT'],
                               highlightthickness=0)
        msg_sb = tk.Scrollbar(self._chat_frame, orient='vertical',
                              command=msg_canvas.yview)
        msg_canvas.configure(yscrollcommand=msg_sb.set)
        msg_sb.pack(side=tk.RIGHT, fill=tk.Y)
        msg_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._chat_inner = tk.Frame(msg_canvas, bg=th['BG_CONTENT'])
        self._chat_win_id = msg_canvas.create_window(
            (0, 0), window=self._chat_inner, anchor='nw')
        self._chat_canvas = msg_canvas

        self._chat_inner.bind('<Configure>',
            lambda e: msg_canvas.configure(scrollregion=msg_canvas.bbox('all')))
        msg_canvas.bind('<Configure>',
            lambda e: msg_canvas.itemconfig(self._chat_win_id, width=e.width))

        def _scroll(e):
            if abs(e.delta) <= 10:
                msg_canvas.yview_scroll(-e.delta, 'units')
            else:
                msg_canvas.yview_scroll(-1 * (e.delta // 120), 'units')
        msg_canvas.bind('<MouseWheel>', _scroll)
        self._chat_inner.bind('<MouseWheel>', _scroll)

        # 聊天页输入栏
        _cibar_h  = 44
        _cbtn_r   = 15
        _cbtn_margin = 8

        cib = tk.Canvas(chat_input_bar, height=_cibar_h,
            bg=th['BG_TOOLBAR'], highlightthickness=0, bd=0)
        cib.pack(fill=tk.X, padx=16, pady=10)

        def _draw_pill_c(canvas, fill_color):
            canvas.delete('pill')
            w = canvas.winfo_width() or 600
            h = canvas.winfo_height() or _cibar_h
            r = h // 2
            canvas.create_arc(0, 0, r*2, r*2, start=90, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_arc(w-r*2, 0, w, r*2, start=0, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_arc(0, h-r*2, r*2, h, start=180, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_rectangle(r, 0, w-r, h,
                fill=fill_color, outline=fill_color, tags='pill')
            canvas.create_rectangle(0, r, w, h-r,
                fill=fill_color, outline=fill_color, tags='pill')

        def _draw_send_btn_c(canvas, color):
            canvas.delete('sendbtn')
            w = canvas.winfo_width() or 600
            h = canvas.winfo_height() or _cibar_h
            cx = w - _cbtn_r - _cbtn_margin
            cy = h // 2
            canvas.create_oval(cx-_cbtn_r, cy-_cbtn_r, cx+_cbtn_r, cy+_cbtn_r,
                fill=color, outline=color, tags='sendbtn')
            canvas.create_text(cx, cy, text='↑',
                fill=th['BG_WIN'], font=('PingFang SC', 13, 'bold'), tags='sendbtn')

        self._chat_input = tk.Text(cib,
            bg=th['BG_CARD'], fg=th['FG_MAIN'],
            font=('PingFang SC', 13), relief=tk.FLAT,
            padx=4, pady=0, wrap=tk.WORD, height=1,
            insertbackground=th['FG_ACCENT'],
            selectbackground=th['BG_SEL'],
            borderwidth=0, highlightthickness=0)
        _ci_id = cib.create_window(
            _cibar_h // 2, _cibar_h // 2, anchor='w', window=self._chat_input)
        self._chat_input.bind('<Return>', self._on_chat_enter)

        def _refresh_cib(e=None):
            w = cib.winfo_width() or 600
            _draw_pill_c(cib, th['BG_CARD'])
            _draw_send_btn_c(cib, th['FG_ACCENT'])
            text_w = max(w - _cibar_h // 2 - _cbtn_r * 2 - _cbtn_margin * 2 - 8, 60)
            cib.itemconfig(_ci_id, width=text_w)
            cib.tag_raise('sendbtn')

        cib.bind('<Configure>', _refresh_cib)
        cib.after(10, _refresh_cib)

        cib.tag_bind('sendbtn', '<Button-1>', lambda e: self._send_chat())
        cib.configure(cursor='arrow')
        cib.tag_bind('sendbtn', '<Enter>', lambda e: cib.configure(cursor='hand2'))
        cib.tag_bind('sendbtn', '<Leave>', lambda e: cib.configure(cursor='arrow'))

        cib._refresh      = _refresh_cib
        cib._draw_sendbtn = _draw_send_btn_c
        self._cib         = cib
        send_c_canvas     = cib

        self._send_btns = [send_w_canvas, send_c_canvas]

        return frame

    def _set_send_btns_color(self, color, enabled):
        for canvas in getattr(self, '_send_btns', []):
            try:
                if hasattr(canvas, '_draw_sendbtn'):
                    canvas._draw_sendbtn(canvas, color)
                    canvas.tag_raise('sendbtn')
            except Exception:
                pass

    def _set_placeholder(self, widget, text, th):
        widget._placeholder = text
        widget._has_placeholder = False

        def _on_focus_in(e):
            if widget._has_placeholder:
                widget.delete('1.0', tk.END)
                widget.configure(fg=th['FG_MAIN'])
                widget._has_placeholder = False

        def _on_focus_out(e):
            if not widget.get('1.0', tk.END).strip():
                widget.insert('1.0', text)
                widget.configure(fg=th['FG_DIM'])
                widget._has_placeholder = True

        widget.insert('1.0', text)
        widget.configure(fg=th['FG_DIM'])
        widget._has_placeholder = True

        widget.bind('<FocusIn>', _on_focus_in)
        widget.bind('<FocusOut>', _on_focus_out)

    def _back_to_welcome(self):
        self._save_current_session()
        for w in self._chat_inner.winfo_children():
            w.destroy()
        self._current_session_id = None
        self._chat_started = False

        q, sub = random.choice(self.GREETINGS)
        self._welcome_greeting = (q, sub)
        self._home_question.configure(text=q)
        self._home_sub.configure(text=sub)

        self._refresh_history_btn()

        self._chat_frame.place_forget()
        self._welcome_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _switch_to_chat(self):
        self._chat_started = True
        self._profile_enabled = True   # 每次新对话默认开启画像记录
        self._update_profile_btn()
        sid = int(time.time() * 1000)
        self._current_session_id = sid
        self._chat_sessions.append({
            'id': sid,
            'title': time.strftime('%m/%d %H:%M'),
            'bubbles': [],
        })
        self._welcome_frame.place_forget()
        self._chat_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _toggle_profile_recording(self):
        self._profile_enabled = not self._profile_enabled
        self._update_profile_btn()

    def _update_profile_btn(self):
        th = THEMES[self._theme_mode]
        btn = getattr(self, '_profile_btn', None)
        if btn and btn.winfo_exists():
            if self._profile_enabled:
                btn.configure(text='🧠 记录', fg=th['FG_ACCENT'])
            else:
                btn.configure(text='🧠 不记录', fg=th['FG_DIM'])

    def _save_current_session(self):
        if self._current_session_id is None:
            return
        sess = next((s for s in self._chat_sessions
                     if s['id'] == self._current_session_id), None)
        if sess is None:
            return
        bubbles = []
        for row in self._chat_inner.winfo_children():
            for child in row.winfo_children():
                if child.winfo_class() == 'Canvas' and hasattr(child, '_text_id'):
                    text = child.itemcget(child._text_id, 'text')
                    th = THEMES[self._theme_mode]
                    role = 'user' if child._bubble_bg == th['FG_ACCENT'] else 'pet'
                    bubbles.append((role, text))
                elif child.winfo_class() == 'Frame':
                    for sub in child.winfo_children():
                        if sub.winfo_class() == 'Canvas' and hasattr(sub, '_text_id'):
                            text = sub.itemcget(sub._text_id, 'text')
                            bubbles.append(('pet', text))
        sess['bubbles'] = bubbles
        if bubbles:
            for role, text in bubbles:
                if role == 'user':
                    sess['title'] = text[:20] + ('…' if len(text) > 20 else '')
                    break

    def _refresh_history_btn(self):
        th = THEMES[self._theme_mode]
        if self._chat_sessions:
            self._history_btn.configure(fg=th['FG_DIM'])
            self._history_btn.place(relx=0, rely=0, anchor='nw', x=16, y=14)
        else:
            self._history_btn.place_forget()

    def _show_session_picker(self):
        if not self._chat_sessions:
            return
        th = THEMES[self._theme_mode]

        if hasattr(self, '_picker_frame') and self._picker_frame.winfo_exists():
            self._picker_frame.destroy()
            return

        picker = tk.Frame(self._welcome_frame, bg=th['BG_CARD'],
                          highlightbackground=th['DIVIDER'], highlightthickness=1)
        picker.place(relx=0, rely=0, anchor='nw', x=16, y=40)
        self._picker_frame = picker

        tk.Label(picker, text='历史对话', bg=th['BG_CARD'], fg=th['FG_DIM'],
                 font=('PingFang SC', 10), padx=12, pady=6).pack(anchor='w')
        tk.Frame(picker, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        for sess in reversed(self._chat_sessions):
            sid = sess['id']
            title = sess['title']
            row = tk.Frame(picker, bg=th['BG_CARD'], cursor='hand2')
            row.pack(fill=tk.X)
            lbl = tk.Label(row, text=title, bg=th['BG_CARD'], fg=th['FG_MAIN'],
                           font=('PingFang SC', 12), padx=16, pady=8, anchor='w')
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            for w in (row, lbl):
                w.bind('<Enter>', lambda e, r=row: r.configure(bg=th['BG_HOVER']))
                w.bind('<Leave>', lambda e, r=row: r.configure(bg=th['BG_CARD']))
                w.bind('<Button-1>', lambda e, s=sid: self._load_session(s))

        self._welcome_frame.bind('<Button-1>',
            lambda e: picker.destroy() if picker.winfo_exists() else None,
            add='+')

    def _load_session(self, session_id):
        sess = next((s for s in self._chat_sessions if s['id'] == session_id), None)
        if not sess:
            return
        if hasattr(self, '_picker_frame') and self._picker_frame.winfo_exists():
            self._picker_frame.destroy()

        self._current_session_id = session_id
        self._chat_started = True
        self._welcome_frame.place_forget()
        self._chat_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        for w in self._chat_inner.winfo_children():
            w.destroy()

        th = THEMES[self._theme_mode]
        loading_frame = tk.Frame(self._chat_inner, bg=th['BG_CONTENT'])
        loading_frame.pack(expand=True, pady=40)
        loading_lbl = tk.Label(loading_frame, text='···',
            bg=th['BG_CONTENT'], fg=th['FG_DIM'],
            font=('PingFang SC', 18))
        loading_lbl.pack()

        _dots = ['·', '··', '···']
        _dot_idx = [0]
        def _tick():
            if loading_lbl.winfo_exists():
                _dot_idx[0] = (_dot_idx[0] + 1) % 3
                loading_lbl.configure(text=_dots[_dot_idx[0]])
                self.win.after(300, _tick)
        self.win.after(300, _tick)

        self._chat_canvas.configure(scrollregion=self._chat_canvas.bbox('all'))
        self.win.update_idletasks()

        def _render():
            if not (self.win and self.win.winfo_exists()):
                return
            if loading_frame.winfo_exists():
                loading_frame.destroy()
            for role, text in sess['bubbles']:
                self._add_chat_bubble(role, text)

        self.win.after(50, _render)

    def _update_home_clock(self):
        if not (self.win and self.win.winfo_exists()):
            return
        self._home_time_label.configure(text=time.strftime('%H:%M  %m/%d'))
        self.win.after(30000, self._update_home_clock)

    def _rounded_bubble(self, parent, text, bg_color, fg_color, max_wrap=400):
        font_spec = ('PingFang SC', 12)
        pad_x, pad_y, radius = 14, 9, 12

        def _measure(t):
            tmp = tk.Label(parent, text=t or ' ', font=font_spec,
                           wraplength=max_wrap, justify=tk.LEFT,
                           padx=0, pady=0, borderwidth=0)
            tmp.update_idletasks()
            tw, th_h = tmp.winfo_reqwidth(), tmp.winfo_reqheight()
            tmp.destroy()
            return tw, th_h

        tw, th_h = _measure(text)
        w = tw + pad_x * 2
        h = th_h + pad_y * 2

        c = tk.Canvas(parent, width=w, height=h,
                      bg=parent['bg'], highlightthickness=0, bd=0)
        c._bubble_bg   = bg_color
        c._bubble_fg   = fg_color
        c._bubble_padx = pad_x
        c._bubble_pady = pad_y
        c._bubble_r    = radius
        c._bubble_wrap = max_wrap
        c._measure     = _measure

        def _draw(canvas, cw, ch):
            canvas.delete('bubble_bg')
            r = canvas._bubble_r
            bg = canvas._bubble_bg
            canvas.create_arc(0, 0, r*2, r*2, start=90, extent=90,
                fill=bg, outline=bg, tags='bubble_bg')
            canvas.create_arc(cw-r*2, 0, cw, r*2, start=0, extent=90,
                fill=bg, outline=bg, tags='bubble_bg')
            canvas.create_arc(0, ch-r*2, r*2, ch, start=180, extent=90,
                fill=bg, outline=bg, tags='bubble_bg')
            canvas.create_arc(cw-r*2, ch-r*2, cw, ch, start=270, extent=90,
                fill=bg, outline=bg, tags='bubble_bg')
            canvas.create_rectangle(r, 0, cw-r, ch, fill=bg, outline=bg, tags='bubble_bg')
            canvas.create_rectangle(0, r, cw, ch-r, fill=bg, outline=bg, tags='bubble_bg')

        _draw(c, w, h)
        tid = c.create_text(pad_x, pad_y, text=text, fill=fg_color,
                            font=font_spec, anchor='nw',
                            width=max_wrap, justify=tk.LEFT)
        c._text_id = tid
        c._draw    = _draw
        return c, tid

    def _update_bubble(self, canvas, new_text):
        if not (canvas and canvas.winfo_exists()):
            return
        tw, th_h = canvas._measure(new_text)
        w = tw + canvas._bubble_padx * 2
        h = th_h + canvas._bubble_pady * 2
        canvas.configure(width=w, height=h)
        canvas.delete('bubble_bg')
        r = canvas._bubble_r
        bg = canvas._bubble_bg
        canvas.create_arc(0, 0, r*2, r*2, start=90, extent=90,
            fill=bg, outline=bg, tags='bubble_bg')
        canvas.create_arc(w-r*2, 0, w, r*2, start=0, extent=90,
            fill=bg, outline=bg, tags='bubble_bg')
        canvas.create_arc(0, h-r*2, r*2, h, start=180, extent=90,
            fill=bg, outline=bg, tags='bubble_bg')
        canvas.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90,
            fill=bg, outline=bg, tags='bubble_bg')
        canvas.create_rectangle(r, 0, w-r, h, fill=bg, outline=bg, tags='bubble_bg')
        canvas.create_rectangle(0, r, w, h-r, fill=bg, outline=bg, tags='bubble_bg')
        canvas.tag_raise(canvas._text_id)
        canvas.itemconfigure(canvas._text_id, text=new_text)

    def _add_chat_bubble(self, role, text):
        th = THEMES[self._theme_mode]
        is_user = (role == 'user')

        row = tk.Frame(self._chat_inner, bg=th['BG_CONTENT'])
        row.pack(fill=tk.X, padx=20, pady=(6, 2))

        if is_user:
            spacer = tk.Frame(row, bg=th['BG_CONTENT'])
            spacer.pack(side=tk.LEFT, fill=tk.X, expand=True)
            canvas, _ = self._rounded_bubble(row, text,
                bg_color=th['FG_ACCENT'], fg_color=th['BG_WIN'])
            canvas.pack(side=tk.RIGHT, anchor='e')
        else:
            em = self.pet.settings.get('pet_emoji', '🐱')
            tk.Label(row, text=em, bg=th['BG_CONTENT'],
                font=('Apple Color Emoji', 22)).pack(
                side=tk.LEFT, anchor='s', padx=(0, 10), pady=(0, 2))
            col = tk.Frame(row, bg=th['BG_CONTENT'])
            col.pack(side=tk.LEFT, anchor='w')
            canvas, _ = self._rounded_bubble(col, text,
                bg_color=th['BG_CARD'], fg_color=th['FG_MAIN'])
            canvas.pack(anchor='w')

        self._chat_inner.update_idletasks()
        self._chat_canvas.configure(scrollregion=self._chat_canvas.bbox('all'))
        self._chat_canvas.yview_moveto(1.0)
        return row, canvas

    def _on_chat_enter(self, event):
        if not (event.state & 0x1):
            self._send_chat()
            return 'break'

    def _send_chat(self):
        if self._chat_thinking:
            return

        if self._chat_started:
            src = self._chat_input
        else:
            src = self._welcome_input

        if getattr(src, '_has_placeholder', False):
            return
        text = src.get('1.0', tk.END).strip()
        if not text:
            return
        src.delete('1.0', tk.END)

        if not self._chat_started:
            self._switch_to_chat()
            q, sub = self._welcome_greeting
            self._add_chat_bubble('pet', f'{q}\n{sub}')

        self._add_chat_bubble('user', text)

        self._chat_thinking = True
        th = THEMES[self._theme_mode]
        self._set_send_btns_color(th['FG_DIM'], enabled=False)

        self._thinking_row, self._thinking_canvas = self._add_chat_bubble('pet', '···')

        def run():
            self._stream_pet_ai(text)

        threading.Thread(target=run, daemon=True).start()
        self.pet.trigger_bounce()

    def _stream_pet_ai(self, user_text):
        emoji = self.pet.settings.get('pet_emoji', '🐱')
        pet_name        = self.pet.settings.get('pet_name', '小猫')
        pet_personality = self.pet.settings.get('pet_personality', '温柔')
        pet_catchphrase = self.pet.settings.get('pet_catchphrase', '喵~')
        system = (
            f'你是一只可爱的桌面宠物 {emoji}，名字叫{pet_name}，'
            f'性格{pet_personality}，说话简短可爱，'
            f'偶尔使用你的口头禅"{pet_catchphrase}"，'
            '偶尔用叠词或语气词，回复控制在 2-3 句以内，不要用 Markdown 格式。'
            + self.stats.system_prompt_hint()
        )
        profile = load_json(USER_PROFILE_FILE, {})
        if profile:
            parts = []
            if profile.get('name'):
                parts.append(f"用户名字叫{profile['name']}")
            if profile.get('pet_nickname'):
                parts.append(f"用户叫你{profile['pet_nickname']}")
            if profile.get('notes'):
                parts.append('；'.join(profile['notes']))
            if parts:
                system += '关于用户你已知道：' + '，'.join(parts) + '。'
        accumulated = ''
        try:
            proc = subprocess.Popen(
                ['/opt/homebrew/bin/claude', '--print',
                 '--output-format', 'stream-json',
                 '--include-partial-messages',
                 '--verbose',
                 '--system-prompt', system],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1
            )
            proc.stdin.write(user_text)
            proc.stdin.close()

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if (evt.get('type') == 'stream_event' and
                        evt.get('event', {}).get('type') == 'content_block_delta'):
                    delta = evt['event'].get('delta', {})
                    if delta.get('type') == 'text_delta':
                        accumulated += delta.get('text', '')
                        t = accumulated
                        if self.win and self.win.winfo_exists():
                            self.win.after(0, lambda t=t: self._on_stream_chunk(t))

            proc.wait()
        except Exception as e:
            accumulated = f'呜，出了点小问题：{e}'

        final = accumulated.strip() or '喵？我没听清楚，再说一遍吧～'
        if self.win and self.win.winfo_exists():
            self.win.after(0, lambda: self._on_stream_done(final))

    def _on_stream_chunk(self, text_so_far):
        canvas = getattr(self, '_thinking_canvas', None)
        if canvas and canvas.winfo_exists():
            self._update_bubble(canvas, text_so_far)
            self._chat_canvas.configure(
                scrollregion=self._chat_canvas.bbox('all'))
            self._chat_canvas.yview_moveto(1.0)

    def _on_stream_done(self, final_text):
        th = THEMES[self._theme_mode]
        canvas = getattr(self, '_thinking_canvas', None)
        if canvas and canvas.winfo_exists():
            self._update_bubble(canvas, final_text)
            self._chat_canvas.configure(
                scrollregion=self._chat_canvas.bbox('all'))
            self._chat_canvas.yview_moveto(1.0)
        self._chat_thinking = False
        self._set_send_btns_color(th['FG_ACCENT'], enabled=True)
        self.pet.trigger_bounce()
        self.stats.on_chat()
        self._sync_pet_ui()
        if self._profile_enabled:
            # 取本轮对话最后一条用户消息（即刚发送的那条）
            # bubbles 存为 (role, text) 元组列表
            sess = next((s for s in self._chat_sessions
                         if s['id'] == self._current_session_id), None)
            last_user = ''
            if sess:
                for b in reversed(sess.get('bubbles', [])):
                    role = b[0] if isinstance(b, (tuple, list)) else b.get('role', '')
                    text = b[1] if isinstance(b, (tuple, list)) else b.get('text', '')
                    if role == 'user':
                        last_user = text
                        break
            # bubbles 在 _save_current_session 才更新，这里直接用 _thinking_canvas 之前的输入
            # 通过 _chat_inner 子控件读取最后一个 user bubble
            if not last_user:
                for row in reversed(self._chat_inner.winfo_children()):
                    found = False
                    for child in row.winfo_children():
                        if child.winfo_class() == 'Canvas' and hasattr(child, '_text_id'):
                            role = 'user' if child._bubble_bg == THEMES[self._theme_mode]['FG_ACCENT'] else 'pet'
                            if role == 'user':
                                last_user = child.itemcget(child._text_id, 'text')
                                found = True
                                break
                    if found:
                        break
            if last_user:
                threading.Thread(
                    target=self._extract_profile_async,
                    args=(last_user, final_text),
                    daemon=True
                ).start()


    # ══════════════════════════════════════════════════
    #  Tab: 新闻
    # ══════════════════════════════════════════════════

    def _extract_profile_async(self, user_text, pet_reply):
        """Call Claude to extract profile info from one exchange; merge into user_profile.json."""
        existing = load_json(USER_PROFILE_FILE, {})
        existing_summary = json.dumps(existing, ensure_ascii=False)
        prompt = (
            f'从下面这段对话中提取用户的个人信息，只关注：用户名字、用户对 AI 的称呼/命名、用户的自我介绍。'
            f'已有画像：{existing_summary}\n'
            f'用户说：{user_text}\nAI回复：{pet_reply}\n'
            '请以 JSON 格式返回需要更新的字段，字段名只用：name（用户名字）、pet_nickname（用户给AI的称呼）、notes（list，其他自我介绍信息）。'
            '如果这段对话没有任何新的个人信息，返回空 JSON {}。只返回 JSON，不要任何解释。'
        )
        try:
            proc = subprocess.Popen(
                ['/opt/homebrew/bin/claude', '--print',
                 '--output-format', 'json'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True
            )
            out, _ = proc.communicate(input=prompt, timeout=30)
            # claude --output-format json 返回 {"result": "..."}
            try:
                wrapper = json.loads(out)
                raw = wrapper.get('result', out)
            except Exception:
                raw = out
            # 从 raw 里提取第一个 JSON 对象
            import re as _re
            m = _re.search(r'\{.*\}', raw, _re.DOTALL)
            if not m:
                return
            updates = json.loads(m.group())
            if not updates:
                return
            # 合并：name/pet_nickname 直接覆盖；notes 追加去重
            if 'name' in updates and updates['name']:
                existing['name'] = updates['name']
            if 'pet_nickname' in updates and updates['pet_nickname']:
                existing['pet_nickname'] = updates['pet_nickname']
            if 'notes' in updates and updates['notes']:
                old_notes = existing.get('notes', [])
                for note in updates['notes']:
                    if note and note not in old_notes:
                        old_notes.append(note)
                existing['notes'] = old_notes
            save_json(USER_PROFILE_FILE, existing)
        except Exception:
            pass

    # ══════════════════════════════════════════════════
    #  Tab: 新闻
    # ══════════════════════════════════════════════════

    def _build_news_tab(self, parent):
        th = THEMES[self._theme_mode]
        frame = tk.Frame(parent, bg=th['BG_CONTENT'])
        self._news_tab_body = frame   # used by _build_collection_view to attach collection frames

        # ── 工具栏 ──
        toolbar = tk.Frame(frame, bg=th['BG_TOOLBAR'], height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text='热点新闻', bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
                 font=('PingFang SC', 13, 'bold')).pack(side=tk.LEFT, padx=16)

        self._news_status = tk.Label(toolbar, text='', bg=th['BG_TOOLBAR'],
                                     fg=th['FG_MUTED'], font=('PingFang SC', 10))
        self._news_status.pack(side=tk.LEFT, padx=4)

        self._refresh_var = tk.StringVar(
            value=str(self.pet.settings.get('auto_refresh_min', 30)))
        self._notify_var = tk.BooleanVar(
            value=self.pet.settings.get('notify_on_refresh', False))

        # 推送通知开关
        notify_frame = tk.Frame(toolbar, bg=th['BG_TOOLBAR'])
        notify_frame.pack(side=tk.RIGHT, padx=8)
        tk.Label(notify_frame, text='推送', bg=th['BG_TOOLBAR'],
                 fg=th['FG_MUTED'], font=('PingFang SC', 10)).pack(side=tk.LEFT)
        tk.Checkbutton(notify_frame, variable=self._notify_var,
                       bg=th['BG_TOOLBAR'], activebackground=th['BG_TOOLBAR'],
                       fg=th['FG_MUTED'], selectcolor=th['BG_HOVER'],
                       cursor='hand2',
                       command=self._save_news_settings).pack(side=tk.LEFT)

        # 刷新间隔
        interval_frame = tk.Frame(toolbar, bg=th['BG_TOOLBAR'])
        interval_frame.pack(side=tk.RIGHT, padx=4)
        tk.Label(interval_frame, text='间隔', bg=th['BG_TOOLBAR'],
                 fg=th['FG_MUTED'], font=('PingFang SC', 10)).pack(side=tk.LEFT)
        for mins in ['15', '30', '60']:
            rb = tk.Radiobutton(interval_frame, text=f'{mins}m',
                                variable=self._refresh_var, value=mins,
                                bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
                                selectcolor=th['BG_SEL'],
                                activebackground=th['BG_TOOLBAR'],
                                activeforeground=th['FG_ACCENT'],
                                font=('PingFang SC', 10), cursor='hand2',
                                command=self._save_news_settings)
            rb.pack(side=tk.LEFT, padx=2)

        # 操作按钮（emoji + 文字，hover tooltip）
        def _make_tooltip(widget, text):
            tip = None
            def _show(e):
                nonlocal tip
                if tip:
                    return
                x = widget.winfo_rootx() + widget.winfo_width() // 2
                y = widget.winfo_rooty() + widget.winfo_height() + 4
                tip = tk.Toplevel(widget)
                tip.overrideredirect(True)
                tip.attributes('-topmost', True)
                tk.Label(tip, text=text,
                         bg='#333333', fg='#ffffff',
                         font=('PingFang SC', 10),
                         padx=8, pady=4).pack()
                tip.update_idletasks()
                tw = tip.winfo_width()
                tip.geometry(f'+{x - tw//2}+{y}')
            def _hide(e):
                nonlocal tip
                if tip:
                    tip.destroy()
                    tip = None
            widget.bind('<Enter>', _show, add='+')
            widget.bind('<Leave>', _hide, add='+')

        for icon, label, cmd in [
            ('⚡', '抓取最新', lambda: self._load_news_async(True)),
            ('🔄', '读取缓存', lambda: self._load_news_async(False)),
            ('🔔', '推送通知', self._push_news),
        ]:
            b = tk.Frame(toolbar, bg=th['BG_TOOLBAR'], cursor='hand2')
            b.pack(side=tk.RIGHT, padx=4, pady=6)
            tk.Label(b, text=icon, bg=th['BG_TOOLBAR'],
                     fg=th['FG_MUTED'], font=('Apple Color Emoji', 12),
                     cursor='hand2').pack(side=tk.LEFT)
            tk.Label(b, text=label, bg=th['BG_TOOLBAR'],
                     fg=th['FG_MUTED'], font=('PingFang SC', 10),
                     cursor='hand2').pack(side=tk.LEFT, padx=(2, 0))
            def _enter(e, w=b):
                for c in w.winfo_children():
                    c.configure(fg=th['FG_ACCENT'])
            def _leave(e, w=b):
                for c in w.winfo_children():
                    c.configure(fg=th['FG_MUTED'])
            b.bind('<Enter>', _enter)
            b.bind('<Leave>', _leave)
            b.bind('<Button-1>', lambda e, c=cmd: c())
            for child in b.winfo_children():
                child.bind('<Enter>', _enter)
                child.bind('<Leave>', _leave)
                child.bind('<Button-1>', lambda e, c=cmd: c())

        tk.Frame(frame, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        # ── 视图切换子工具栏 ──
        view_bar = tk.Frame(frame, bg=th['BG_TOOLBAR'])
        view_bar.pack(fill=tk.X)
        self._news_view_btns = {}
        for view_key, view_label in [('feed', '热点'), ('bookmarks', '收藏'), ('read_later', '稍后再看')]:
            btn = tk.Label(view_bar, text=view_label,
                           bg=th['BG_TOOLBAR'],
                           fg=th['FG_ACCENT'] if view_key == 'feed' else th['FG_MUTED'],
                           font=('PingFang SC', 11, 'bold') if view_key == 'feed' else ('PingFang SC', 11),
                           cursor='hand2', padx=14, pady=6)
            btn.pack(side=tk.LEFT)
            btn.bind('<Button-1>', lambda e, v=view_key: self._switch_news_view(v))
            self._news_view_btns[view_key] = btn
        tk.Frame(frame, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        # ── 滚动新闻列表 ──
        canvas = tk.Canvas(frame, bg=th['BG_CONTENT'], highlightthickness=0)
        self._news_canvas_sb = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        sb = self._news_canvas_sb
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._news_inner = tk.Frame(canvas, bg=th['BG_CONTENT'])
        self._news_canvas_win = canvas.create_window((0, 0), window=self._news_inner, anchor='nw')
        self._news_canvas = canvas

        self._news_inner.bind('<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        self._news_canvas_last_cols = 0
        def _on_canvas_resize(e):
            canvas.itemconfig(self._news_canvas_win, width=e.width)
            cols = max(1, e.width // 280)
            if cols != self._news_canvas_last_cols:
                self._news_canvas_last_cols = cols
                if hasattr(self, '_news_sections_cache') and self._news_sections_cache:
                    self._render_news(self._news_sections_cache, self._news_status.cget('text'), cols=cols)
        canvas.bind('<Configure>', _on_canvas_resize)

        def _scroll(e):
            if abs(e.delta) <= 10:
                canvas.yview_scroll(-e.delta, 'units')
            else:
                canvas.yview_scroll(-1 * (e.delta // 120), 'units')
        canvas.bind('<MouseWheel>', _scroll)
        self._news_inner.bind('<MouseWheel>', _scroll)

        self._show_news_loading('🔄 正在加载...')
        return frame

    def _save_news_settings(self):
        s = self.pet.settings
        s['auto_refresh_min'] = int(self._refresh_var.get())
        s['notify_on_refresh'] = self._notify_var.get()
        save_settings(s)
        self.pet.settings = s

    def _switch_news_view(self, view):
        """Switch the News tab between 'feed', 'bookmarks', 'read_later'."""
        self._news_current_view = view
        th = THEMES[self._theme_mode]

        # Update tab-bar button highlights
        for v, btn in self._news_view_btns.items():
            if v == view:
                btn.configure(fg=th['FG_ACCENT'],
                              font=('PingFang SC', 11, 'bold'))
            else:
                btn.configure(fg=th['FG_MUTED'],
                              font=('PingFang SC', 11))

        if view == 'feed':
            # Hide collection frame, show news canvas + scrollbar
            if hasattr(self, '_news_collection_frame'):
                self._news_collection_frame.pack_forget()
            self._news_canvas_sb.pack(side=tk.RIGHT, fill=tk.Y)
            self._news_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        else:
            # Hide news canvas + scrollbar, show collection frame
            self._news_canvas.pack_forget()
            self._news_canvas_sb.pack_forget()
            self._build_collection_view(view)

    def _build_collection_view(self, collection):
        """Render the bookmark or read-later list inside the news tab."""
        th = THEMES[self._theme_mode]

        # Destroy any previous collection frame
        if hasattr(self, '_news_collection_frame') and self._news_collection_frame.winfo_exists():
            self._news_collection_frame.destroy()

        frame = tk.Frame(self._news_tab_body, bg=th['BG_CONTENT'])
        frame.pack(fill=tk.BOTH, expand=True)
        self._news_collection_frame = frame

        # Scrollable list
        canvas = tk.Canvas(frame, bg=th['BG_CONTENT'], highlightthickness=0)
        sb = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=th['BG_CONTENT'])
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))

        def _scroll(e):
            if abs(e.delta) <= 10:
                canvas.yview_scroll(-e.delta, 'units')
            else:
                canvas.yview_scroll(-1 * (e.delta // 120), 'units')
        canvas.bind('<MouseWheel>', _scroll)
        inner.bind('<MouseWheel>', _scroll)

        items = self._storage.list_items(collection)

        if not items:
            label_text = '还没有收藏' if collection == 'bookmarks' else '还没有稍后再看'
            tk.Label(inner, text=label_text,
                     bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
                     font=('PingFang SC', 13)).pack(pady=40)
            return

        for item in items:
            row = tk.Frame(inner, bg=th['BG_CARD'],
                           highlightbackground=th['BORDER'], highlightthickness=1)
            row.pack(fill=tk.X, padx=14, pady=4)

            text_col = tk.Frame(row, bg=th['BG_CARD'])
            text_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0), pady=8)

            tk.Label(text_col, text=item.get('title', ''),
                     bg=th['BG_CARD'], fg=th['FG_MAIN'],
                     font=('PingFang SC', 11),
                     wraplength=520, justify=tk.LEFT, anchor='w').pack(fill=tk.X)
            tk.Label(text_col,
                     text=f"{item.get('source', '')}  •  {item.get('saved_at', '')[:10]}",
                     bg=th['BG_CARD'], fg=th['FG_MUTED'],
                     font=('PingFang SC', 9), anchor='w').pack(fill=tk.X, pady=(2, 0))

            # Open link on row click
            def _click(e, link=item.get('link')):
                if link:
                    import subprocess as _sp
                    _sp.Popen(['open', link])
            row.bind('<Button-1>', _click)
            text_col.bind('<Button-1>', _click)

            # Delete button
            del_btn = tk.Label(row, text='✕', bg=th['BG_CARD'], fg=th['FG_MUTED'],
                               font=('PingFang SC', 13), cursor='hand2',
                               padx=10, pady=8)
            del_btn.pack(side=tk.RIGHT)

            def _delete(e, iid=item.get('id'), col=collection):
                self._storage.remove(col, iid)
                # Rebuild the view to reflect deletion
                self._build_collection_view(col)
            del_btn.bind('<Button-1>', _delete)
            del_btn.bind('<Enter>', lambda e, b=del_btn: b.configure(fg=th['FG_RED']))
            del_btn.bind('<Leave>', lambda e, b=del_btn: b.configure(fg=th['FG_MUTED']))

    def _show_news_loading(self, msg):
        th = THEMES[self._theme_mode]
        for w in self._news_inner.winfo_children():
            w.destroy()
        # 清掉旧的 loading window
        for item in self._news_canvas.find_withtag('loading_win'):
            self._news_canvas.delete(item)

        container = tk.Frame(self._news_canvas, bg=th['BG_CONTENT'])
        # 等 canvas 布局完成后居中放置
        def _place():
            if not self._news_canvas.winfo_exists():
                return
            cw = self._news_canvas.winfo_width()
            ch = self._news_canvas.winfo_height()
            cx = max(cw // 2, 100)
            cy = max(ch // 2, 120)
            self._news_canvas.create_window(cx, cy, window=container,
                                            anchor='center', tags='loading_win')
        self._news_canvas.after(50, _place)

        accent  = th.get('FG_ACCENT', '#0078d4')
        accent2 = '#4fc3f7' if self._theme_mode == 'dark' else '#42a5f5'
        muted   = th.get('FG_MUTED',  '#cccccc')
        bg      = th['BG_CONTENT']

        size = 100
        cx = cy = size // 2
        cv = tk.Canvas(container, width=size, height=size,
                       bg=bg, highlightthickness=0)
        cv.pack()

        # ── 两层同心圆环 ──
        # 外圈：细，慢，顺时针，120° 弧
        R1, S1 = 40, 2
        cv.create_arc(cx-R1, cy-R1, cx+R1, cy+R1,
                      start=0, extent=359, style='arc', outline=muted, width=S1)
        arc1 = cv.create_arc(cx-R1, cy-R1, cx+R1, cy+R1,
                              start=0, extent=120, style='arc', outline=accent2, width=S1)

        # 内圈：粗，逆时针，90° 弧
        R2, S2 = 26, 4
        cv.create_arc(cx-R2, cy-R2, cx+R2, cy+R2,
                      start=0, extent=359, style='arc', outline=muted, width=S2)
        arc2 = cv.create_arc(cx-R2, cy-R2, cx+R2, cy+R2,
                              start=0, extent=90, style='arc', outline=accent, width=S2)

        # 中心 emoji
        cv.create_text(cx, cy, text='🐾', font=('Apple Color Emoji', 13), tags='emoji')

        # 底部文字
        tk.Label(container, text='加载中…', bg=bg,
                 fg=muted, font=('PingFang SC', 10)).pack(pady=(8, 0))

        a1, a2 = [0], [0]

        def _animate():
            if not cv.winfo_exists():
                return
            a1[0] = (a1[0] + 2) % 360
            a2[0] = (a2[0] - 5) % 360
            cv.itemconfig(arc1, start=a1[0])
            cv.itemconfig(arc2, start=a2[0])
            cv.after(16, _animate)

        _animate()

    def _load_news_async(self, force=False):
        msg = '⚡ 正在抓取最新数据...' if force else '🔄 正在加载...'
        self._show_news_loading(msg)
        self._news_status.configure(text='')
        def run():
            content, cached, ts = get_news(force=force)
            sections = parse_news(content)
            for sec in sections:
                if 'Google' in sec.get('source', '') and sec['items']:
                    titles = [it['title'] for it in sec['items']]
                    translated = _translate_titles_with_claude(titles)
                    for it, tr in zip(sec['items'], translated):
                        it['title'] = tr
            tag = '缓存' if cached else '最新'
            tstr = time.strftime('%H:%M', time.localtime(ts))
            status = f'{tstr} [{tag}]'
            if self.win and self.win.winfo_exists():
                self.win.after(0, lambda: self._render_news(sections, status))
                self.win.after(0, self._schedule_news_refresh)
        threading.Thread(target=run, daemon=True).start()

    def _schedule_news_refresh(self):
        """Schedule the next automatic news refresh based on auto_refresh_min setting."""
        if self._news_refresh_job is not None:
            try:
                self.win.after_cancel(self._news_refresh_job)
            except Exception:
                pass
            self._news_refresh_job = None
        mins = int(self.pet.settings.get('auto_refresh_min', 30))
        if mins > 0 and self.win and self.win.winfo_exists():
            self._news_refresh_job = self.win.after(
                mins * 60 * 1000,
                lambda: self._load_news_async(force=True)
            )

    def _render_news(self, sections, status, cols=None):
        th = THEMES[self._theme_mode]
        self._news_status.configure(text=status)
        self._news_sections_cache = sections
        self._news_canvas.delete('loading_win')
        for w in self._news_inner.winfo_children():
            w.destroy()

        if cols is None:
            w = self._news_canvas.winfo_width()
            cols = max(1, w // 280) if w > 1 else 2

        SOURCE_ICONS = {
            'Google Trends': '🔍',
            '百度热点': '🔥',
            '微博热搜': '💬',
        }
        RANK_COLORS = ['#ef5350', '#ff7043', '#ffa726']

        grid = tk.Frame(self._news_inner, bg=th['BG_CONTENT'])
        grid.pack(fill=tk.X, padx=14, pady=10)
        for c in range(cols):
            grid.columnconfigure(c, weight=1)

        import hashlib as _hashlib
        import time as _time

        def _make_item_id(item):
            """Stable ID: hash of title + source."""
            return _hashlib.md5(
                (item.get('title', '') + item.get('source', '')).encode()
            ).hexdigest()[:12]

        for idx, sec in enumerate(sections):
            col = idx % cols
            row_idx = idx // cols

            col_frame = tk.Frame(grid, bg=th['BG_CONTENT'])
            col_frame.grid(row=row_idx, column=col, sticky='nsew', padx=5, pady=6)

            # 来源标题行
            header = tk.Frame(col_frame, bg=th['BG_CONTENT'])
            header.pack(fill=tk.X, pady=(0, 6))

            icon = SOURCE_ICONS.get(sec['source'], '📰')
            tk.Label(header, text=icon,
                     bg=th['BG_CONTENT'], font=('Apple Color Emoji', 13)).pack(side=tk.LEFT)
            tk.Label(header, text=f"  {sec['source']}",
                     bg=th['BG_CONTENT'], fg=th['FG_MAIN'],
                     font=('PingFang SC', 12, 'bold')).pack(side=tk.LEFT)
            tk.Label(header, text=f"Top {len(sec['items'])}",
                     bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
                     font=('PingFang SC', 9)).pack(side=tk.RIGHT, padx=2)

            # 卡片（圆角边框）
            card = tk.Frame(col_frame, bg=th['BG_CARD'],
                            highlightbackground=th['BORDER'], highlightthickness=1)
            card.pack(fill=tk.X)

            for i, item in enumerate(sec['items']):
                row = tk.Frame(card, bg=th['BG_CARD'], cursor='hand2')
                row.pack(fill=tk.X)

                # 序号：圆形色块效果（用 Canvas 画）
                rank_color = RANK_COLORS[i] if i < 3 else th['FG_MUTED']
                num_canvas = tk.Canvas(row, width=22, height=22,
                                       bg=th['BG_CARD'], highlightthickness=0)
                num_canvas.pack(side=tk.LEFT, padx=(10, 0), pady=8)
                if i < 3:
                    num_canvas.create_oval(1, 1, 21, 21, fill=rank_color, outline=rank_color)
                    num_canvas.create_text(11, 11, text=str(i+1),
                                           fill='white', font=('PingFang SC', 9, 'bold'))
                else:
                    num_canvas.create_text(11, 11, text=str(i+1),
                                           fill=rank_color, font=('PingFang SC', 10))

                col_w = max(160, (self._news_canvas.winfo_width() - 28) // cols - 50)
                title_lbl = tk.Label(row, text=item['title'],
                                     bg=th['BG_CARD'], fg=th['FG_MAIN'],
                                     font=('PingFang SC', 11),
                                     wraplength=col_w, justify=tk.LEFT,
                                     anchor='w', padx=8, pady=7)
                title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

                # ── 收藏 / 稍后再看 按钮 ──
                item_id = _make_item_id(item)
                saved_item = {
                    'id': item_id,
                    'title': item.get('title', ''),
                    'link': item.get('link', ''),
                    'source': sec.get('source', ''),
                    'saved_at': _time.strftime('%Y-%m-%dT%H:%M:%S'),
                }

                # Check current state (already bookmarked or read-later?)
                bm_ids = {x['id'] for x in self._storage.list_items('bookmarks')}
                rl_ids = {x['id'] for x in self._storage.list_items('read_later')}
                bm_icon = '📌' if item_id in bm_ids else '🔖'
                rl_icon = '✅' if item_id in rl_ids else '⏰'

                bm_btn = tk.Label(row, text=bm_icon, bg=th['BG_CARD'],
                                  font=('Apple Color Emoji', 11), cursor='hand2',
                                  padx=4, pady=8)
                bm_btn.pack(side=tk.RIGHT, padx=(0, 2))

                rl_btn = tk.Label(row, text=rl_icon, bg=th['BG_CARD'],
                                  font=('Apple Color Emoji', 11), cursor='hand2',
                                  padx=4, pady=8)
                rl_btn.pack(side=tk.RIGHT, padx=(0, 0))

                def _toggle_bookmark(e, btn=bm_btn, sid=saved_item, iid=item_id):
                    ids = {x['id'] for x in self._storage.list_items('bookmarks')}
                    if iid in ids:
                        self._storage.remove('bookmarks', iid)
                        btn.configure(text='🔖')
                    else:
                        self._storage.add('bookmarks', sid)
                        btn.configure(text='📌')

                def _toggle_read_later(e, btn=rl_btn, sid=saved_item, iid=item_id):
                    ids = {x['id'] for x in self._storage.list_items('read_later')}
                    if iid in ids:
                        self._storage.remove('read_later', iid)
                        btn.configure(text='⏰')
                    else:
                        self._storage.add('read_later', sid)
                        btn.configure(text='✅')

                bm_btn.bind('<Button-1>', _toggle_bookmark)
                rl_btn.bind('<Button-1>', _toggle_read_later)

                # Hover backgrounds for action buttons
                bm_btn.bind('<Enter>', lambda e, b=bm_btn: b.configure(bg=th['BG_HOVER']))
                bm_btn.bind('<Leave>', lambda e, b=bm_btn: b.configure(bg=th['BG_CARD']))
                rl_btn.bind('<Enter>', lambda e, b=rl_btn: b.configure(bg=th['BG_HOVER']))
                rl_btn.bind('<Leave>', lambda e, b=rl_btn: b.configure(bg=th['BG_CARD']))

                if i < len(sec['items']) - 1:
                    tk.Frame(card, bg=th['DIVIDER'], height=1).pack(fill=tk.X, padx=10)

                def _enter(e, r=row, n=num_canvas, l=title_lbl, rc=rank_color, ii=i, bb=bm_btn, rb=rl_btn):
                    r.configure(bg=th['BG_HOVER'])
                    n.configure(bg=th['BG_HOVER'])
                    l.configure(bg=th['BG_HOVER'], fg=th['FG_ACCENT'])
                    bb.configure(bg=th['BG_HOVER'])
                    rb.configure(bg=th['BG_HOVER'])
                    if ii >= 3:
                        n.itemconfig(1, fill=th['FG_ACCENT'])
                def _leave(e, r=row, n=num_canvas, l=title_lbl, rc=rank_color, ii=i, bb=bm_btn, rb=rl_btn):
                    r.configure(bg=th['BG_CARD'])
                    n.configure(bg=th['BG_CARD'])
                    l.configure(bg=th['BG_CARD'], fg=th['FG_MAIN'])
                    bb.configure(bg=th['BG_CARD'])
                    rb.configure(bg=th['BG_CARD'])
                    if ii >= 3:
                        n.itemconfig(1, fill=rc)
                def _click(e, link=item.get('link')):
                    if link:
                        subprocess.Popen(['open', link])
                for w in (row, num_canvas, title_lbl):
                    w.bind('<Enter>', _enter)
                    w.bind('<Leave>', _leave)
                    w.bind('<Button-1>', _click)

    def _push_news(self):
        def run():
            content, _, _ = get_news()
            sections = parse_news(content)
            for sec in sections:
                if sec['items']:
                    try:
                        send_notification(f"📰 {sec['source']}", sec['items'][0]['title'])
                    except Exception:
                        pass
        threading.Thread(target=run, daemon=True).start()
        self._news_status.configure(text='✅ 已推送')


    # ══════════════════════════════════════════════════
    #  Tab: 宠物
    # ══════════════════════════════════════════════════

    def _build_pet_tab(self, parent):
        th = THEMES[self._theme_mode]
        frame = tk.Frame(parent, bg=th['BG_CONTENT'])

        toolbar = tk.Frame(frame, bg=th['BG_TOOLBAR'], height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        tk.Label(toolbar, text='我的宠物', bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
                 font=('PingFang SC', 13, 'bold')).pack(side=tk.LEFT, padx=16)
        tk.Frame(frame, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        body = tk.Frame(frame, bg=th['BG_CONTENT'])
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # ── 左侧：emoji + 按钮 ──
        left = tk.Frame(body, bg=th['BG_CONTENT'])
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        self._pet_emoji_label = tk.Label(left,
            text=self.stats.mood_emoji(),
            bg=th['BG_CONTENT'], font=('Apple Color Emoji', 72))
        self._pet_emoji_label.pack(pady=(20, 4))

        self._pet_mood_lbl = tk.Label(left, text=self.stats.mood_label(),
            bg=th['BG_CONTENT'], fg=th['FG_ACCENT'],
            font=('PingFang SC', 12, 'bold'))
        self._pet_mood_lbl.pack()

        self._pet_name_display_lbl = tk.Label(
            left,
            text=self.pet.settings.get('pet_name', '小猫'),
            bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
            font=('PingFang SC', 11))
        self._pet_name_display_lbl.pack(pady=(0, 4))

        btn_frame = tk.Frame(left, bg=th['BG_CONTENT'])
        btn_frame.pack(pady=16)
        for text, action in [('🐟 喂食', self._feed),
                              ('🎾 逗猫', self._play),
                              ('💤 休息', self._sleep)]:
            b = tk.Label(btn_frame, text=text, bg=th['BG_CARD'], fg=th['FG_MAIN'],
                         font=('PingFang SC', 12), cursor='hand2',
                         padx=12, pady=8,
                         highlightbackground=th['BORDER'], highlightthickness=1)
            b.pack(fill=tk.X, pady=3)
            b.bind('<Button-1>', lambda e, a=action: a())
            b.bind('<Enter>', lambda e, w=b: w.configure(bg=th['BG_HOVER']))
            b.bind('<Leave>', lambda e, w=b: w.configure(bg=th['BG_CARD']))

        # ── 右侧：数值卡片 + 互动记录 ──
        right = tk.Frame(body, bg=th['BG_CONTENT'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        card = tk.Frame(right, bg=th['BG_CARD'],
                        highlightbackground=th['BORDER'], highlightthickness=1)
        card.pack(fill=tk.X, pady=(8, 12))

        # 三行数值：心情 / 饱食 / 精力，每行带进度条
        self._stat_bars   = {}   # key -> Canvas (进度条)
        self._stat_labels = {}   # key -> Label  (文字)

        BAR_W, BAR_H = 160, 8
        BAR_COLORS = {
            'mood':   '#f48fb1',   # 粉
            'hunger': '#80cbc4',   # 青
            'energy': '#ffe082',   # 黄
        }
        stat_rows = [
            ('mood',   '心情', self.stats.mood_label()),
            ('hunger', '饱食', self.stats.hunger_label()),
            ('energy', '精力', self.stats.energy_label()),
        ]
        for key, label_text, desc in stat_rows:
            row = tk.Frame(card, bg=th['BG_CARD'])
            row.pack(fill=tk.X, padx=14, pady=8)
            tk.Label(row, text=label_text, bg=th['BG_CARD'], fg=th['FG_MUTED'],
                     font=('PingFang SC', 11), width=4, anchor='w').pack(side=tk.LEFT)

            bar_canvas = tk.Canvas(row, width=BAR_W, height=BAR_H,
                                   bg=th['BG_HOVER'], highlightthickness=0, bd=0)
            bar_canvas.pack(side=tk.LEFT, padx=(6, 10))
            val = getattr(self.stats, key)
            fill_w = max(4, int(BAR_W * val / 100))
            bar_canvas.create_rectangle(0, 0, fill_w, BAR_H,
                fill=BAR_COLORS[key], outline='', tags='bar')
            self._stat_bars[key] = (bar_canvas, BAR_W, BAR_H, BAR_COLORS[key])

            desc_lbl = tk.Label(row, text=desc, bg=th['BG_CARD'], fg=th['FG_MAIN'],
                                font=('PingFang SC', 11))
            desc_lbl.pack(side=tk.LEFT)
            self._stat_labels[key] = desc_lbl

        tk.Label(right, text='互动记录', bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
                 font=('PingFang SC', 10)).pack(anchor='w', pady=(0, 4))
        self._pet_log = tk.Text(right, bg=th['BG_CARD'], fg=th['FG_MAIN'],
                                font=('PingFang SC', 11),
                                relief=tk.FLAT, padx=10, pady=8,
                                state=tk.DISABLED, wrap=tk.WORD,
                                highlightbackground=th['BORDER'], highlightthickness=1)
        self._pet_log.pack(fill=tk.BOTH, expand=True)
        self._log_pet('宠物醒来了，开始新的一天 ✨')
        return frame

    def _sync_pet_ui(self):
        """刷新宠物 tab 进度条、文字、以及所有 emoji 显示点。"""
        if not (self.win and self.win.winfo_exists()):
            return
        s = self.stats
        mood_em = s.mood_emoji()

        # 宠物 tab emoji 和心情文字
        if hasattr(self, '_pet_emoji_label') and self._pet_emoji_label.winfo_exists():
            self._pet_emoji_label.configure(text=mood_em)
        if hasattr(self, '_pet_mood_lbl') and self._pet_mood_lbl.winfo_exists():
            self._pet_mood_lbl.configure(text=s.mood_label())

        # 进度条 + 文字描述
        labels_map = {
            'mood':   s.mood_label(),
            'hunger': s.hunger_label(),
            'energy': s.energy_label(),
        }
        vals_map = {'mood': s.mood, 'hunger': s.hunger, 'energy': s.energy}
        for key, (bar_canvas, BAR_W, BAR_H, color) in self._stat_bars.items():
            if bar_canvas.winfo_exists():
                fill_w = max(4, int(BAR_W * vals_map[key] / 100))
                bar_canvas.delete('bar')
                bar_canvas.create_rectangle(0, 0, fill_w, BAR_H,
                    fill=color, outline='', tags='bar')
            lbl = self._stat_labels.get(key)
            if lbl and lbl.winfo_exists():
                lbl.configure(text=labels_map[key])

        # 悬浮 emoji（DesktopPet canvas）— 仅当用户没有自定义 emoji 时跟随心情
        # 规则：如果 settings['pet_emoji'] 是基础猫 🐱，则跟随心情；否则保持用户选择
        base_emoji = self.pet.settings.get('pet_emoji', '🐱')
        if base_emoji == '🐱':
            self.pet.set_emoji(mood_em)
            # 主页大 emoji
            if hasattr(self, '_home_emoji') and self._home_emoji.winfo_exists():
                self._home_emoji.configure(text=mood_em)
            # 聊天 topbar emoji
            if hasattr(self, '_chat_topbar_emoji') and self._chat_topbar_emoji.winfo_exists():
                self._chat_topbar_emoji.configure(text=mood_em)

    def _start_stats_decay(self):
        """每 10 分钟衰减一次，循环调度。"""
        def _decay_tick():
            self.stats.decay()
            self._sync_pet_ui()
            if self.win and self.win.winfo_exists():
                self.win.after(PetStats.DECAY_INTERVAL_MS, _decay_tick)
        if self.win and self.win.winfo_exists():
            self.win.after(PetStats.DECAY_INTERVAL_MS, _decay_tick)

    def _log_pet(self, msg):
        ts = time.strftime('%H:%M')
        self._pet_log.configure(state=tk.NORMAL)
        self._pet_log.insert('1.0', f'[{ts}] {msg}\n')
        self._pet_log.configure(state=tk.DISABLED)

    def _feed(self):
        self.stats.feed()
        self._sync_pet_ui()
        self._log_pet('被喂食了，好满足~ 🐟')
        self.pet.trigger_bounce()

    def _play(self):
        self.stats.play()
        self._sync_pet_ui()
        self._log_pet('一起玩了逗猫棒，好快乐！🎾')
        self.pet.trigger_bounce()

    def _sleep(self):
        self.stats.rest()
        self._sync_pet_ui()
        self._log_pet('进入休息状态，充电中... 💤')

    # ══════════════════════════════════════════════════
    #  Tab: 便签
    # ══════════════════════════════════════════════════

    def _build_notes_tab(self, parent):
        th = THEMES[self._theme_mode]
        frame = tk.Frame(parent, bg=th['BG_CONTENT'])

        toolbar = tk.Frame(frame, bg=th['BG_TOOLBAR'], height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        self._notes_title_label = tk.Label(toolbar, text='便签',
                 bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
                 font=('PingFang SC', 13, 'bold'))
        self._notes_title_label.pack(side=tk.LEFT, padx=16)

        self._notes_status = tk.Label(toolbar, text='', bg=th['BG_TOOLBAR'],
                                      fg=th['FG_MUTED'], font=('PingFang SC', 10))
        self._notes_status.pack(side=tk.LEFT, padx=4)

        self._notes_save_btn = tk.Label(toolbar, text='💾 保存', bg=th['BG_TOOLBAR'],
                            fg=th['FG_MAIN'], font=('PingFang SC', 11),
                            cursor='hand2', padx=10)
        self._notes_save_btn.bind('<Button-1>', lambda e: self._save_current_note())
        self._notes_save_btn.bind('<Enter>', lambda e: self._notes_save_btn.configure(fg=th['FG_ACCENT']))
        self._notes_save_btn.bind('<Leave>', lambda e: self._notes_save_btn.configure(fg=th['FG_MAIN']))

        self._notes_back_btn = tk.Label(toolbar, text='← 返回', bg=th['BG_TOOLBAR'],
                            fg=th['FG_MAIN'], font=('PingFang SC', 11),
                            cursor='hand2', padx=10)
        self._notes_back_btn.bind('<Button-1>', lambda e: self._notes_show_list())
        self._notes_back_btn.bind('<Enter>', lambda e: self._notes_back_btn.configure(fg=th['FG_ACCENT']))
        self._notes_back_btn.bind('<Leave>', lambda e: self._notes_back_btn.configure(fg=th['FG_MAIN']))

        tk.Frame(frame, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        self._notes_body = tk.Frame(frame, bg=th['BG_CONTENT'])
        self._notes_body.pack(fill=tk.BOTH, expand=True)

        self._notes_text = tk.Text(self._notes_body, bg=th['BG_CARD'], fg=th['FG_MAIN'],
                                   font=('PingFang SC', 13),
                                   relief=tk.FLAT, padx=20, pady=16,
                                   wrap=tk.WORD,
                                   insertbackground=th['FG_ACCENT'],
                                   selectbackground=th['BG_SEL'],
                                   borderwidth=0)

        self._notes_current_id = None
        self._notes_list_frame = None

        data = load_json(NOTE_FILE, {'notes': []})
        notes = data.get('notes', [])
        if notes:
            self._notes_show_list()
        else:
            self._notes_open_editor(None)

        return frame

    def _notes_load_all(self):
        return load_json(NOTE_FILE, {'notes': []}).get('notes', [])

    def _notes_save_all(self, notes):
        save_json(NOTE_FILE, {'notes': notes})

    def _notes_show_list(self):
        th = THEMES[self._theme_mode]
        self._notes_text.pack_forget()
        self._notes_save_btn.pack_forget()
        self._notes_back_btn.pack_forget()
        self._notes_title_label.configure(text='便签')
        self._notes_status.configure(text='')
        self._notes_current_id = None

        if self._notes_list_frame:
            self._notes_list_frame.destroy()

        notes = self._notes_load_all()

        outer = tk.Frame(self._notes_body, bg=th['BG_CONTENT'])
        outer.pack(fill=tk.BOTH, expand=True)
        self._notes_list_frame = outer

        canvas = tk.Canvas(outer, bg=th['BG_CONTENT'], highlightthickness=0)
        sb = tk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=th['BG_CONTENT'])
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))

        grid = tk.Frame(inner, bg=th['BG_CONTENT'])
        grid.pack(fill=tk.X, padx=16, pady=16)

        CARD_W = 160
        cards_per_row = 4

        def _make_card(parent, note, col, row_i):
            card = tk.Frame(parent, bg=th['BG_CARD'],
                            highlightbackground=th['BORDER'], highlightthickness=1,
                            cursor='hand2', width=CARD_W, height=120)
            card.grid(row=row_i, column=col, padx=6, pady=6, sticky='nsew')
            card.pack_propagate(False)

            title = (note['content'][:20].replace('\n', ' ') + '…') if len(note['content']) > 20 else note['content'].replace('\n', ' ')
            tk.Label(card, text=title or '（空便签）',
                     bg=th['BG_CARD'], fg=th['FG_MAIN'],
                     font=('PingFang SC', 11), wraplength=CARD_W - 16,
                     justify=tk.LEFT, anchor='nw').place(x=8, y=8, width=CARD_W-16, height=64)

            ts = time.strftime('%m/%d %H:%M', time.localtime(note.get('updated', 0)))
            tk.Label(card, text=ts, bg=th['BG_CARD'], fg=th['FG_MUTED'],
                     font=('PingFang SC', 9)).place(x=8, y=94)

            del_btn = tk.Label(card, text='×', bg=th['BG_CARD'], fg=th['FG_MUTED'],
                               font=('PingFang SC', 14, 'bold'), cursor='hand2')
            del_btn.place(x=CARD_W-20, y=2)

            def _open(e, nid=note['id']):
                self._notes_open_editor(nid)
            def _delete(e, nid=note['id']):
                self._notes_delete(nid)
            def _enter(e):
                card.configure(highlightbackground=th['FG_ACCENT'])
            def _leave(e):
                card.configure(highlightbackground=th['BORDER'])

            for w in (card,):
                w.bind('<Button-1>', _open)
                w.bind('<Enter>', _enter)
                w.bind('<Leave>', _leave)
            del_btn.bind('<Button-1>', _delete)
            del_btn.bind('<Enter>', lambda e: del_btn.configure(fg=th['FG_RED']))
            del_btn.bind('<Leave>', lambda e: del_btn.configure(fg=th['FG_MUTED']))

        items = list(notes) + [None]
        for i, item in enumerate(items):
            col = i % cards_per_row
            row_i = i // cards_per_row
            grid.columnconfigure(col, weight=1)
            if item is None:
                add_btn = tk.Frame(grid, bg=th['BG_CONTENT'],
                                   highlightbackground=th['BORDER'], highlightthickness=1,
                                   cursor='hand2', width=CARD_W, height=120)
                add_btn.grid(row=row_i, column=col, padx=6, pady=6, sticky='nsew')
                add_btn.pack_propagate(False)
                plus = tk.Label(add_btn, text='+', bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
                                font=('PingFang SC', 32), cursor='hand2')
                plus.place(relx=0.5, rely=0.5, anchor='center')
                def _new(e):
                    self._notes_open_editor(None)
                def _add_enter(e):
                    add_btn.configure(highlightbackground=th['FG_ACCENT'])
                    plus.configure(fg=th['FG_ACCENT'])
                def _add_leave(e):
                    add_btn.configure(highlightbackground=th['BORDER'])
                    plus.configure(fg=th['FG_MUTED'])
                add_btn.bind('<Button-1>', _new)
                plus.bind('<Button-1>', _new)
                add_btn.bind('<Enter>', _add_enter)
                add_btn.bind('<Leave>', _add_leave)
                plus.bind('<Enter>', _add_enter)
                plus.bind('<Leave>', _add_leave)
            else:
                _make_card(grid, item, col, row_i)

    def _notes_open_editor(self, note_id):
        th = THEMES[self._theme_mode]
        notes = self._notes_load_all()

        if self._notes_list_frame:
            self._notes_list_frame.pack_forget()

        self._notes_current_id = note_id
        content = ''
        if note_id is not None:
            for n in notes:
                if n['id'] == note_id:
                    content = n['content']
                    break
            self._notes_title_label.configure(text='编辑便签')
            self._notes_back_btn.pack(side=tk.LEFT, pady=4)
        else:
            self._notes_title_label.configure(text='新建便签')
            if notes:
                self._notes_back_btn.pack(side=tk.LEFT, pady=4)

        self._notes_save_btn.pack(side=tk.RIGHT, pady=4)
        self._notes_status.configure(text='')

        self._notes_text.configure(state=tk.NORMAL)
        self._notes_text.delete('1.0', tk.END)
        self._notes_text.insert('1.0', content)
        self._notes_text.pack(fill=tk.BOTH, expand=True)
        self._notes_text.focus_set()

    def _save_current_note(self):
        content = self._notes_text.get('1.0', tk.END).rstrip('\n')
        if not content.strip():
            self._notes_status.configure(text='内容为空')
            return
        notes = self._notes_load_all()
        now = int(time.time())
        if self._notes_current_id is not None:
            for n in notes:
                if n['id'] == self._notes_current_id:
                    n['content'] = content
                    n['updated'] = now
                    break
        else:
            new_id = now
            notes.append({'id': new_id, 'content': content, 'updated': now})
            self._notes_current_id = new_id
        self._notes_save_all(notes)
        self._notes_status.configure(text=f'已保存 {time.strftime("%H:%M:%S")}')
        self._notes_show_list()

    def _notes_delete(self, note_id):
        notes = self._notes_load_all()
        notes = [n for n in notes if n['id'] != note_id]
        self._notes_save_all(notes)
        if notes:
            self._notes_show_list()
        else:
            self._notes_open_editor(None)

    # ══════════════════════════════════════════════════
    #  Tab: 设置
    # ══════════════════════════════════════════════════

    def _build_settings_tab(self, parent):
        th = THEMES[self._theme_mode]
        frame = tk.Frame(parent, bg=th['BG_CONTENT'])

        toolbar = tk.Frame(frame, bg=th['BG_TOOLBAR'], height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        tk.Label(toolbar, text='设置', bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
                 font=('PingFang SC', 13, 'bold')).pack(side=tk.LEFT, padx=16)
        tk.Frame(frame, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        canvas = tk.Canvas(frame, bg=th['BG_CONTENT'], highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg=th['BG_CONTENT'])
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))

        def _section(title):
            tk.Label(inner, text=title, bg=th['BG_CONTENT'], fg=th['FG_MUTED'],
                     font=('PingFang SC', 10, 'bold')).pack(
                anchor='w', padx=24, pady=(20, 6))
            card = tk.Frame(inner, bg=th['BG_CARD'],
                            highlightbackground=th['BORDER'], highlightthickness=1)
            card.pack(fill=tk.X, padx=24, pady=0)
            return card

        card1 = _section('宠物形象')
        row = tk.Frame(card1, bg=th['BG_CARD'])
        row.pack(fill=tk.X, padx=16, pady=12)
        tk.Label(row, text='选择形象', bg=th['BG_CARD'], fg=th['FG_MUTED'],
                 font=('PingFang SC', 11), width=8, anchor='w').pack(side=tk.LEFT)
        self._emoji_var = tk.StringVar(value=self.pet.settings.get('pet_emoji', '🐱'))
        emojis = ['🐱', '🐶', '🐼', '🦊', '🐸', '🐨', '🐯', '🦁']
        for e in emojis:
            b = tk.Label(row, text=e, bg=th['BG_CARD'],
                         font=('Apple Color Emoji', 22), cursor='hand2', padx=5)
            b.pack(side=tk.LEFT)
            b.bind('<Button-1>', lambda ev, em=e: self._set_emoji(em))

        card2 = _section('宠物性格')

        # Row A — 宠物名字
        row_name = tk.Frame(card2, bg=th['BG_CARD'])
        row_name.pack(fill=tk.X, padx=16, pady=12)
        tk.Label(row_name, text='名字', bg=th['BG_CARD'], fg=th['FG_MUTED'],
                 font=('PingFang SC', 11), width=8, anchor='w').pack(side=tk.LEFT)
        self._pet_name_var = tk.StringVar(value=self.pet.settings.get('pet_name', '小猫'))
        tk.Entry(row_name, textvariable=self._pet_name_var, width=14,
                 bg=th['BG_HOVER'], fg=th['FG_MAIN'], relief=tk.FLAT,
                 font=('PingFang SC', 11),
                 insertbackground=th['FG_MAIN']).pack(side=tk.LEFT)

        tk.Frame(card2, bg=th['DIVIDER'], height=1).pack(fill=tk.X, padx=16)

        # Row B — 宠物性格（5-option label buttons）
        row_personality = tk.Frame(card2, bg=th['BG_CARD'])
        row_personality.pack(fill=tk.X, padx=16, pady=12)
        tk.Label(row_personality, text='性格', bg=th['BG_CARD'], fg=th['FG_MUTED'],
                 font=('PingFang SC', 11), width=8, anchor='w').pack(side=tk.LEFT)
        self._personality_var = tk.StringVar(
            value=self.pet.settings.get('pet_personality', '温柔'))

        def _update_personality_btns():
            for child in row_personality.winfo_children():
                if isinstance(child, tk.Label) and child.cget('text') in ['温柔', '活泼', '傲娇', '淡定', '搞笑']:
                    if child.cget('text') == self._personality_var.get():
                        child.configure(bg=th['FG_ACCENT'], fg='#ffffff',
                                        highlightbackground=th['FG_ACCENT'])
                    else:
                        child.configure(bg=th['BG_CARD'], fg=th['FG_MAIN'],
                                        highlightbackground=th['BORDER'])

        for opt in ['温柔', '活泼', '傲娇', '淡定', '搞笑']:
            b = tk.Label(row_personality, text=opt,
                         font=('PingFang SC', 11), cursor='hand2',
                         padx=10, pady=4,
                         highlightthickness=1)
            b.pack(side=tk.LEFT, padx=3)

            def _on_personality_click(opt=opt):
                self._personality_var.set(opt)
                _update_personality_btns()

            b.bind('<Button-1>', lambda e, o=opt: _on_personality_click(o))
        _update_personality_btns()

        tk.Frame(card2, bg=th['DIVIDER'], height=1).pack(fill=tk.X, padx=16)

        # Row C — 口头禅
        row_catchphrase = tk.Frame(card2, bg=th['BG_CARD'])
        row_catchphrase.pack(fill=tk.X, padx=16, pady=12)
        tk.Label(row_catchphrase, text='口头禅', bg=th['BG_CARD'], fg=th['FG_MUTED'],
                 font=('PingFang SC', 11), width=8, anchor='w').pack(side=tk.LEFT)
        self._catchphrase_var = tk.StringVar(
            value=self.pet.settings.get('pet_catchphrase', '喵~'))
        tk.Entry(row_catchphrase, textvariable=self._catchphrase_var, width=20,
                 bg=th['BG_HOVER'], fg=th['FG_MAIN'], relief=tk.FLAT,
                 font=('PingFang SC', 11),
                 insertbackground=th['FG_MAIN']).pack(side=tk.LEFT)

        save_btn = tk.Label(inner, text='保存设置',
                            bg=th['BG_BTN'], fg='#ffffff',
                            font=('PingFang SC', 12, 'bold'),
                            cursor='hand2', padx=24, pady=8)
        save_btn.pack(pady=24)
        save_btn.bind('<Button-1>', lambda e: self._save_settings())
        save_btn.bind('<Enter>', lambda e: save_btn.configure(bg=th['FG_ACCENT']))
        save_btn.bind('<Leave>', lambda e: save_btn.configure(bg=th['BG_BTN']))

        self._settings_status = tk.Label(inner, text='', bg=th['BG_CONTENT'],
                                         fg=th['FG_GREEN'], font=('PingFang SC', 11))
        self._settings_status.pack()
        return frame

    def _set_emoji(self, em):
        self._emoji_var.set(em)
        self.pet.set_emoji(em)
        if hasattr(self, '_pet_emoji_label'):
            self._pet_emoji_label.configure(text=em)
        if hasattr(self, '_home_emoji'):
            self._home_emoji.configure(text=em)

    def _save_settings(self):
        s = self.pet.settings
        s['pet_emoji'] = self._emoji_var.get()
        s['pet_name']        = self._pet_name_var.get().strip() or '小猫'
        s['pet_personality'] = self._personality_var.get()
        s['pet_catchphrase'] = self._catchphrase_var.get().strip() or '喵~'
        save_settings(s)
        self.pet.settings = s
        if hasattr(self, '_pet_name_display_lbl'):
            self._pet_name_display_lbl.configure(
                text=s.get('pet_name', '小猫'))
        self._settings_status.configure(text='✅ 已保存')
        def _clear():
            if self.win and self.win.winfo_exists():
                self._settings_status.configure(text='')
        self.win.after(2000, _clear)



# ══════════════════════════════════════════════════════
#  悬浮宠物（永远置顶）
# ══════════════════════════════════════════════════════

class DesktopPet:
    ANIM_INTERVAL = 50

    def __init__(self):
        self.settings = load_settings()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        _TRANS = 'systemTransparent'
        self.root.configure(bg=_TRANS)
        self.root.attributes('-transparent', True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.w = self.h = self.settings.get('pet_size', 76)
        self.x = sw - self.w - 28
        self.y = sh - self.h - 120
        self.root.geometry(f'{self.w}x{self.h}+{self.x}+{self.y}')

        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h,
                                bg=_TRANS, highlightthickness=0)
        self.canvas.pack()

        self.circle = None
        self.emoji_id = self.canvas.create_text(
            self.w//2, self.h//2,
            text=self.settings.get('pet_emoji', '🐱'),
            font=('Apple Color Emoji', 34))

        self._drag_x = self._drag_y = 0
        self._dragging = False
        self._press_time = 0
        self._hovering = False
        self._anim_frame = 0
        self._bouncing = False
        self._bounce_frame = 0

        self.canvas.bind('<ButtonPress-1>',    self._on_press)
        self.canvas.bind('<B1-Motion>',        self._on_drag)
        self.canvas.bind('<ButtonRelease-1>',  self._on_release)
        self.canvas.bind('<Enter>',            lambda e: setattr(self, '_hovering', True))
        self.canvas.bind('<Leave>',            lambda e: setattr(self, '_hovering', False))
        self.canvas.bind('<Button-2>',         self._show_menu)
        self.canvas.bind('<Control-Button-1>', self._show_menu)

        self.panel = MainPanel(self)

        self._menu = tk.Menu(self.root, tearoff=0,
                              bg='#2d2d2d', fg=FG_MAIN,
                              activebackground='#3d3d3d',
                              activeforeground=FG_ACCENT,
                              font=('PingFang SC', 13))
        self._menu.add_command(label='🏠 打开主面板', command=self.panel.open)
        self._menu.add_separator()
        self._menu.add_command(label='❌ 退出',       command=self.root.quit)

        self._animate()

    def set_emoji(self, em):
        self.canvas.itemconfig(self.emoji_id, text=em)

    def trigger_bounce(self):
        self._bouncing = True
        self._bounce_frame = 0

    def _animate(self):
        t = (self._anim_frame % 72) / 72
        cx, cy = self.w // 2, self.h // 2

        if self._bouncing:
            p = self._bounce_frame / 10
            offset_y = int(-16 * math.sin(p * math.pi))
            scale = 1.0 + 0.14 * math.sin(p * math.pi)
            self._bounce_frame += 1
            if self._bounce_frame > 10:
                self._bouncing = False
        elif self._hovering:
            offset_y = -3
            scale = 1.1
        else:
            offset_y = int(-4 * math.sin(2 * math.pi * t))
            scale = 1.0 + 0.03 * math.sin(2 * math.pi * t)

        r = max(20, int(34 * scale))
        self.canvas.coords(self.emoji_id, cx, cy + offset_y)
        self.canvas.itemconfig(self.emoji_id, font=('Apple Color Emoji', r))

        self._anim_frame += 1
        self.root.after(self.ANIM_INTERVAL, self._animate)

    def _on_press(self, e):
        self._drag_x, self._drag_y = e.x, e.y
        self._dragging = False
        self._press_time = time.time()

    def _on_drag(self, e):
        self._dragging = True
        self.x = self.root.winfo_x() + e.x - self._drag_x
        self.y = self.root.winfo_y() + e.y - self._drag_y
        self.root.geometry(f'+{self.x}+{self.y}')

    def _on_release(self, e):
        if not self._dragging and (time.time() - self._press_time) < 0.4:
            self.trigger_bounce()
            self.panel.open()
        self._dragging = False

    def _show_menu(self, e):
        self._menu.tk_popup(e.x_root, e.y_root)

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    DesktopPet().run()
