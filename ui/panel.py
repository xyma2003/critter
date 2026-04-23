"""
ui/panel.py — MainPanel 主面板（含5个Tab）
"""
import tkinter as tk
import threading
import json
import time
import re
from datetime import datetime as _dt
import subprocess
import random
from config import THEMES, NOTE_FILE, USER_PROFILE_FILE, BOOKMARKS_FILE, CLAUDE_CLI, WEATHER_FILE
from data.settings import load_json, save_json, load_settings, save_settings
from utils.objc import load_objc, get_all_ns_windows, nsstring_to_py, set_collection_behavior, find_ns_window_by_title
from data.storage import StorageRepository
from data.pet import PetStats, FEED_LINES, PLAY_LINES, REST_LINES, PET_LINES
from services.news import get_news, parse_news, send_notification
from services.ai import translate_titles_with_claude
import services.notes as notes_service
import services.chat_history as chat_history_service
from services.weather import fetch_weather, is_cached, last_fetch_time, get_cached_data, code_to_emoji


class MainPanel:
    WIN_W, WIN_H = 1024, 620
    NAV_W = 80
    _NEWS_COL_MIN_W = 280

    GREETINGS = {
        'happy': [
            ('今天也是元气满满的一天！', '有我陪着你，什么都能搞定 😸✨'),
            ('嘿！你来了，我好开心！', '今天有什么有趣的事要分享吗 🎉'),
            ('好久不见，想死你了！', '快来陪我聊天嘛 😻'),
            ('今天天气怎么样？', '不管晴雨，有我在就够啦 🌤'),
            ('有没有让你开心的事？', '快说快说，我也想跟着高兴 🎊'),
        ],
        'neutral': [
            ('今天还开心吗？', '不管怎样，我在这里陪着你 🐱'),
            ('嘿，你回来啦！', '我一直在等你呢 ✨'),
            ('今天吃了什么好吃的？', '记得好好吃饭，不然我要担心了 🍜'),
            ('工作顺利吗？', '休息一下，摸摸我也许会好一点 😸'),
            ('最近睡得好吗？', '睡眠很重要哦，我晚上都在守护你 🌙'),
            ('今天有没有喝够水？', '记得补充水分，身体是最重要的 💧'),
            ('有没有做让自己骄傲的事？', '你已经很棒了，继续加油！⭐'),
            ('今天学到什么新东西了吗？', '每天进步一点点就很好了 📚'),
            ('最近有什么小确幸？', '生活里的小美好值得被记录 🌸'),
            ('今天有没有笑一笑？', '笑一个嘛，你笑起来很好看的 😄'),
        ],
        'bored': [
            ('……你来了啊。', '没什么精神，但还是想陪着你 😔'),
            ('今天有点累了，', '不过有你在好一点了 😐'),
            ('有没有什么烦恼？', '说出来也许会轻松一些，我在听 👂'),
            ('压力大吗？', '深呼吸……一切都会好起来的 🌿'),
            ('今天……感觉怎么样？', '我也不太好，我们互相陪伴吧 😿'),
        ],
    }

    def __init__(self, pet):
        self.pet = pet
        self.win = None
        self._news_loaded = False
        self._theme_mode = 'light'
        self._chat_sessions = chat_history_service.load_sessions()
        self._current_session_id = None
        self._storage = StorageRepository(BOOKMARKS_FILE)
        self._news_current_view = 'feed'   # 'feed' | 'bookmarks' | 'read_later'
        self._news_refresh_job = None
        self._profile_enabled = True       # 本对话是否记录用户画像，默认开
        self.stats = PetStats()            # 心情 / 饱食 / 精力数值
        self._clock_running = False
        self._decay_running = False
        self._home_emoji = None
        self._home_emoji_id = None
        self._pet_emoji_label = None
        self._chat_topbar_emoji = None
        self._picker_frame = None
        self._news_collection_frame = None
        self._news_sections_cache = None
        self._last_user_text = ''
        self._weather_cities = []          # list[str] — loaded from WEATHER_FILE
        self._weather_selected = None      # str | None — currently displayed city
        self._weather_loaded = False       # lazy-load flag (mirrors _news_loaded)
        self._weather_fetching = set()     # set[str] — cities currently being fetched

    # ── 心情问候语 ───────────────────────────────────

    def _mood_greeting(self):
        """根据当前心情选择问候语 tier。"""
        mood = self.stats.mood
        if mood >= 70:
            tier = 'happy'
        elif mood >= 40:
            tier = 'neutral'
        else:
            tier = 'bored'
        return random.choice(self.GREETINGS[tier])

    # ── macOS 窗口层级修复 ────────────────────────────

    def _fix_panel_window_level(self):
        try:
            result = load_objc()
            if not result:
                return
            objc, sel, msg0 = result
            nswin = find_ns_window_by_title(objc, sel, msg0, self.win.title())
            if nswin:
                NSWindowCollectionBehaviorTransient = 1 << 3
                set_collection_behavior(objc, sel, nswin, NSWindowCollectionBehaviorTransient)
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
            if self._home_emoji:
                self._home_emoji.itemconfig(self._home_emoji_id,
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
            ('weather',  '🌤', '天气'),
            ('settings', '⚙️', '设置'),
        ]

        for key, icon, label in tab_defs:
            self._add_nav_btn(key, icon, label)

        self._tab_frames['home']     = self._build_home_tab(self._content_host)
        self._tab_frames['news']     = self._build_news_tab(self._content_host)
        self._tab_frames['pet']      = self._build_pet_tab(self._content_host)
        self._tab_frames['notes']    = self._build_notes_tab(self._content_host)
        self._tab_frames['weather']  = self._build_weather_tab(self._content_host)
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

        if key == 'weather':
            if not self._weather_loaded:
                self._weather_loaded = True
                self._weather_cities = load_json(WEATHER_FILE, [])
                self._weather_selected = self._weather_cities[0] if self._weather_cities else None
                self._rebuild_city_list()
                self._render_current_weather()
                for city in self._weather_cities:
                    self._load_weather_async(city, force=True)
            elif self._weather_selected:
                # 每次切换到天气 tab 强制拉取最新数据
                self._weather_status.configure(text='正在更新...')
                self._load_weather_async(self._weather_selected, force=True)

    # ── 主题切换 ──────────────────────────────────────

    def _apply_theme(self, mode):
        self._theme_mode = mode
        th = THEMES[mode]
        # 预计算颜色映射，避免 _recolor_widget 每次递归都重建
        self._color_bg_map = {}
        self._color_fg_map = {}
        for t in THEMES.values():
            self._color_bg_map[t['BG_WIN']]     = th['BG_WIN']
            self._color_bg_map[t['BG_SIDEBAR']] = th['BG_SIDEBAR']
            self._color_bg_map[t['BG_CONTENT']] = th['BG_CONTENT']
            self._color_bg_map[t['BG_CARD']]    = th['BG_CARD']
            self._color_bg_map[t['BG_TOOLBAR']] = th['BG_TOOLBAR']
            self._color_bg_map[t['BG_HOVER']]   = th['BG_HOVER']
            self._color_bg_map[t['BG_SEL']]     = th['BG_SEL']
            self._color_bg_map[t['BG_BTN']]     = th['BG_BTN']
            self._color_bg_map[t['ACCENT_BAR']] = th['ACCENT_BAR']
            self._color_fg_map[t['FG_MAIN']]    = th['FG_MAIN']
            self._color_fg_map[t['FG_DIM']]     = th['FG_DIM']
            self._color_fg_map[t['FG_MUTED']]   = th['FG_MUTED']
            self._color_fg_map[t['FG_ACCENT']]  = th['FG_ACCENT']
            self._color_fg_map[t['FG_GREEN']]   = th['FG_GREEN']
            self._color_fg_map[t['BORDER']]     = th['BORDER']
            self._color_fg_map[t['DIVIDER']]    = th['DIVIDER']
        self._recolor_widget(self.win, th)
        self._switch_tab(self._active_tab)

    def _recolor_widget(self, widget, th):
        cls = widget.winfo_class()
        try:
            cur_bg = widget.cget('bg')
        except Exception:
            cur_bg = None

        all_bgs = self._color_bg_map
        all_fgs = self._color_fg_map

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

        q, sub = self._mood_greeting()
        self._welcome_greeting = (q, sub)

        _em_size = 90
        self._home_emoji = tk.Canvas(center, width=_em_size, height=_em_size,
            bg=th['BG_CONTENT'], highlightthickness=0, bd=0)
        self._home_emoji.pack(pady=(0, 18))
        self._home_emoji_id = self._home_emoji.create_text(
            _em_size // 2, _em_size // 2,
            text=self.pet.settings.get('pet_emoji', '🐱'),
            font=('Apple Color Emoji', 72), anchor='center')

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

        self._wib, self._welcome_input = self._build_input_bar(
            welcome_input_wrap, th['BG_CONTENT'], th,
            placeholder='说点什么，开始聊天吧…')
        send_w_canvas = self._wib

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
        self._cib, self._chat_input = self._build_input_bar(
            chat_input_bar, th['BG_TOOLBAR'], th,
            pack_kwargs={'padx': 16, 'pady': 10})
        send_c_canvas = self._cib

        self._send_btns = [send_w_canvas, send_c_canvas]

        return frame

    def _build_input_bar(self, parent, bg_color, th, pack_kwargs=None, placeholder=None):
        """Build a pill-shaped Canvas input bar. Returns (canvas, text_widget)."""
        BAR_H      = 44
        BTN_R      = 15
        BTN_MARGIN = 8

        canvas = tk.Canvas(parent, height=BAR_H,
                           bg=bg_color, highlightthickness=0, bd=0)
        canvas.pack(fill=tk.X, **(pack_kwargs or {}))

        def _draw_pill(c, fill_color):
            c.delete('pill')
            w = c.winfo_width() or 600
            h = c.winfo_height() or BAR_H
            # 内缩 1px，避免描边被 canvas 边缘裁掉
            x0, y0, x1, y1 = 1, 1, w - 1, h - 1
            r = (y1 - y0) // 2
            border = th['BORDER']
            # 填充
            c.create_arc(x0, y0, x0+r*2, y0+r*2, start=90, extent=90,
                fill=fill_color, outline='', tags='pill')
            c.create_arc(x1-r*2, y0, x1, y0+r*2, start=0, extent=90,
                fill=fill_color, outline='', tags='pill')
            c.create_arc(x0, y1-r*2, x0+r*2, y1, start=180, extent=90,
                fill=fill_color, outline='', tags='pill')
            c.create_arc(x1-r*2, y1-r*2, x1, y1, start=270, extent=90,
                fill=fill_color, outline='', tags='pill')
            c.create_rectangle(x0+r, y0, x1-r, y1,
                fill=fill_color, outline='', tags='pill')
            c.create_rectangle(x0, y0+r, x1, y1-r,
                fill=fill_color, outline='', tags='pill')
            # 描边（style=ARC 只画弧线，不画弦）
            c.create_arc(x0, y0, x0+r*2, y0+r*2, start=90, extent=90,
                fill='', outline=border, style=tk.ARC, tags='pill')
            c.create_arc(x1-r*2, y0, x1, y0+r*2, start=0, extent=90,
                fill='', outline=border, style=tk.ARC, tags='pill')
            c.create_arc(x0, y1-r*2, x0+r*2, y1, start=180, extent=90,
                fill='', outline=border, style=tk.ARC, tags='pill')
            c.create_arc(x1-r*2, y1-r*2, x1, y1, start=270, extent=90,
                fill='', outline=border, style=tk.ARC, tags='pill')
            c.create_line(x0+r, y0, x1-r, y0, fill=border, tags='pill')
            c.create_line(x0+r, y1, x1-r, y1, fill=border, tags='pill')

        def _draw_send_btn(c, color):
            c.delete('sendbtn')
            w = c.winfo_width() or 600
            h = c.winfo_height() or BAR_H
            cx = w - BTN_R - BTN_MARGIN
            cy = h // 2
            c.create_oval(cx-BTN_R, cy-BTN_R, cx+BTN_R, cy+BTN_R,
                fill=color, outline=color, tags='sendbtn')
            c.create_text(cx, cy, text='↑',
                fill=th['BG_WIN'], font=('PingFang SC', 13, 'bold'), tags='sendbtn')

        txt = tk.Text(canvas,
            bg=th['BG_CARD'], fg=th['FG_MAIN'],
            font=('PingFang SC', 13), relief=tk.FLAT,
            padx=4, pady=0, wrap=tk.WORD, height=1,
            insertbackground=th['FG_ACCENT'],
            selectbackground=th['BG_SEL'],
            borderwidth=0, highlightthickness=0)
        txt_id = canvas.create_window(BAR_H // 2, BAR_H // 2, anchor='w', window=txt)

        def _refresh(e=None):
            w = canvas.winfo_width() or 600
            _draw_pill(canvas, th['BG_CARD'])
            _draw_send_btn(canvas, th['FG_ACCENT'])
            text_w = max(w - BAR_H // 2 - BTN_R * 2 - BTN_MARGIN * 2 - 8, 60)
            canvas.itemconfig(txt_id, width=text_w)
            canvas.tag_raise('sendbtn')

        canvas.bind('<Configure>', _refresh)
        canvas.after(10, _refresh)

        canvas.tag_bind('sendbtn', '<Button-1>', lambda e: self._send_chat())
        canvas.configure(cursor='arrow')
        canvas.tag_bind('sendbtn', '<Enter>', lambda e: canvas.configure(cursor='hand2'))
        canvas.tag_bind('sendbtn', '<Leave>', lambda e: canvas.configure(cursor='arrow'))

        txt.bind('<Return>', self._on_chat_enter)

        if placeholder:
            self._set_placeholder(txt, placeholder, th)

        canvas._refresh      = _refresh
        canvas._draw_sendbtn = _draw_send_btn
        return canvas, txt

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

        q, sub = self._mood_greeting()
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
            chat_history_service.save_session(sess)

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
        if self._clock_running:
            return
        self._clock_running = True

        def _tick():
            if not (self.win and self.win.winfo_exists()):
                self._clock_running = False
                return
            self._home_time_label.configure(text=time.strftime('%H:%M  %m/%d'))
            self.win.after(30000, _tick)

        _tick()

    @staticmethod
    def _make_scrollable_frame(parent, bg):
        """Create a scrollable canvas area. Returns (canvas, inner_frame)."""
        canvas = tk.Canvas(parent, bg=bg, highlightthickness=0)
        sb = tk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg=bg)
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        return canvas, inner

    @staticmethod
    def _draw_rounded_rect(canvas, w, h, r, bg, tag):
        """Draw a filled rounded rectangle on canvas using the given tag."""
        canvas.create_arc(0, 0, r*2, r*2, start=90, extent=90,
            fill=bg, outline=bg, tags=tag)
        canvas.create_arc(w-r*2, 0, w, r*2, start=0, extent=90,
            fill=bg, outline=bg, tags=tag)
        canvas.create_arc(0, h-r*2, r*2, h, start=180, extent=90,
            fill=bg, outline=bg, tags=tag)
        canvas.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90,
            fill=bg, outline=bg, tags=tag)
        canvas.create_rectangle(r, 0, w-r, h, fill=bg, outline=bg, tags=tag)
        canvas.create_rectangle(0, r, w, h-r, fill=bg, outline=bg, tags=tag)

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
            self._draw_rounded_rect(canvas, cw, ch, canvas._bubble_r, canvas._bubble_bg, 'bubble_bg')

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
        self._draw_rounded_rect(canvas, w, h, canvas._bubble_r, canvas._bubble_bg, 'bubble_bg')
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
        self._last_user_text = text

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
                [CLAUDE_CLI, '--print',
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
            last_user = getattr(self, '_last_user_text', '')
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
                [CLAUDE_CLI, '--print',
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
            m = re.search(r'\{.*\}', raw, re.DOTALL)
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
                         bg=th['BG_CARD'], fg=th['FG_MAIN'],
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
            cols = max(1, e.width // self._NEWS_COL_MIN_W)
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
        canvas, inner = self._make_scrollable_frame(frame, th['BG_CONTENT'])

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
                    subprocess.Popen(['open', link])
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
            google_titles = []
            google_refs = []
            for i, sec in enumerate(sections):
                if 'Google' in sec.get('source', '') and sec['items']:
                    for j, it in enumerate(sec['items']):
                        google_titles.append(it['title'])
                        google_refs.append((i, j))
            if google_titles:
                translated = translate_titles_with_claude(google_titles)
                for (i, j), tr in zip(google_refs, translated):
                    sections[i]['items'][j]['title'] = tr
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
            job, self._news_refresh_job = self._news_refresh_job, None
            try:
                self.win.after_cancel(job)
            except Exception:
                pass
        mins = int(self.pet.settings.get('auto_refresh_min', 30))
        if mins > 0 and self.win and self.win.winfo_exists():
            self._news_refresh_job = self.win.after(
                mins * 60 * 1000,
                lambda: self._load_news_async(force=True)
            )

    def _make_toggle_handler(self, collection, icon_off, icon_on):
        """Return a <Button-1> handler that toggles item membership in `collection`."""
        def _handler(e, btn=None, sid=None, iid=None):
            ids = {x['id'] for x in self._storage.list_items(collection)}
            if iid in ids:
                self._storage.remove(collection, iid)
                btn.configure(text=icon_off)
            else:
                self._storage.add(collection, sid)
                btn.configure(text=icon_on)
        return _handler

    def _render_news(self, sections, status, cols=None):
        import hashlib
        th = THEMES[self._theme_mode]
        self._news_status.configure(text=status)
        self._news_sections_cache = sections
        self._news_canvas.delete('loading_win')
        for w in self._news_inner.winfo_children():
            w.destroy()

        if cols is None:
            w = self._news_canvas.winfo_width()
            cols = max(1, w // self._NEWS_COL_MIN_W) if w > 1 else 2

        SOURCE_ICONS = {
            'Google Trends': '🔍',
            '百度热点': '🔥',
            '微博热搜': '💬',
        }
        RANK_COLORS = ['#ef5350', '#ff7043', '#ffa726']

        bm_ids = {x['id'] for x in self._storage.list_items('bookmarks')}
        rl_ids = {x['id'] for x in self._storage.list_items('read_later')}
        canvas_w = self._news_canvas.winfo_width()
        _toggle_bm = self._make_toggle_handler('bookmarks', '🔖', '📌')
        _toggle_rl = self._make_toggle_handler('read_later', '⏰', '✅')

        grid = tk.Frame(self._news_inner, bg=th['BG_CONTENT'])
        grid.pack(fill=tk.X, padx=14, pady=10)
        for c in range(cols):
            grid.columnconfigure(c, weight=1)

        def _make_item_id(item):
            """Stable ID: hash of title + source."""
            return hashlib.md5(
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

                col_w = max(120, (canvas_w - 28) // cols - 120)
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
                    'saved_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                }

                # Check current state (already bookmarked or read-later?)
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

                bm_btn.bind('<Button-1>',
                    lambda e, h=_toggle_bm, btn=bm_btn, sid=saved_item, iid=item_id:
                        h(e, btn=btn, sid=sid, iid=iid))
                rl_btn.bind('<Button-1>',
                    lambda e, h=_toggle_rl, btn=rl_btn, sid=saved_item, iid=item_id:
                        h(e, btn=btn, sid=sid, iid=iid))

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
                              ('🎾 玩耍', self._play),
                              ('🤲 抚摸', self._pet)]:
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
            if self._home_emoji and self._home_emoji.winfo_exists():
                self._home_emoji.itemconfig(self._home_emoji_id, text=mood_em)
            # 聊天 topbar emoji
            if hasattr(self, '_chat_topbar_emoji') and self._chat_topbar_emoji.winfo_exists():
                self._chat_topbar_emoji.configure(text=mood_em)

    def _start_stats_decay(self):
        """每 10 分钟衰减一次，循环调度。"""
        if self._decay_running:
            return
        self._decay_running = True

        def _decay_tick():
            self.stats.decay()
            self._sync_pet_ui()
            if self.win and self.win.winfo_exists():
                self.win.after(PetStats.DECAY_INTERVAL_MS, _decay_tick)
            else:
                self._decay_running = False

        if self.win and self.win.winfo_exists():
            self.win.after(PetStats.DECAY_INTERVAL_MS, _decay_tick)

    def _log_pet(self, msg):
        ts = time.strftime('%H:%M')
        self._pet_log.configure(state=tk.NORMAL)
        self._pet_log.insert('1.0', f'[{ts}] {msg}\n')
        self._pet_log.configure(state=tk.DISABLED)

    def _flash_emoji(self, flash_em, duration_ms=700):
        """短暂显示 flash_em，然后恢复到当前心情 emoji。"""
        def _restore():
            if self.win and self.win.winfo_exists():
                self._sync_pet_ui()
        for attr in ('_pet_emoji_label', '_chat_topbar_emoji'):
            w = getattr(self, attr, None)
            if w and w.winfo_exists():
                w.configure(text=flash_em)
        if self._home_emoji and self._home_emoji.winfo_exists():
            self._home_emoji.itemconfig(self._home_emoji_id, text=flash_em)
        base = self.pet.settings.get('pet_emoji', '🐱')
        if base == '🐱':
            self.pet.set_emoji(flash_em)
        if self.win and self.win.winfo_exists():
            self.win.after(duration_ms, _restore)

    def _feed(self):
        hunger = self.stats.hunger
        if hunger < 30:
            bucket = 'starving'
        elif hunger < 70:
            bucket = 'hungry'
        else:
            bucket = 'full'
        self.stats.feed()
        self._sync_pet_ui()
        self._flash_emoji('😋', 800)
        self._log_pet(random.choice(FEED_LINES[bucket]))
        self.pet.trigger_bounce()

    def _play(self):
        energy = self.stats.energy
        if energy < 30:
            bucket = 'tired'
        elif self.stats.mood < 50:
            bucket = 'bored'
        else:
            bucket = 'normal'
        self.stats.play()
        self._sync_pet_ui()
        self._flash_emoji('😹', 800)
        self._log_pet(random.choice(PLAY_LINES[bucket]))
        self.pet.trigger_bounce()

    def _sleep(self):
        energy = self.stats.energy
        if energy < 25:
            bucket = 'exhausted'
        elif energy > 75:
            bucket = 'energetic'
        else:
            bucket = 'normal'
        self.stats.rest()
        self._sync_pet_ui()
        self._flash_emoji('😴', 1000)
        self._log_pet(random.choice(REST_LINES[bucket]))

    def _pet(self):
        mood = self.stats.mood
        if mood >= 70:
            bucket = 'happy'
        elif mood >= 40:
            bucket = 'normal'
        else:
            bucket = 'bored'
        self.stats.pet()
        self._sync_pet_ui()
        self._flash_emoji('😻', 800)
        self._log_pet(random.choice(PET_LINES[bucket]))
        self.pet.trigger_bounce()

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
        self._notes_mode = 'list'  # 'list' | 'edit'

        if notes_service.load_all():
            self._notes_show_list()
        else:
            self._notes_open_editor(None)

        return frame

    def _notes_show_list(self):
        self._notes_mode = 'list'
        th = THEMES[self._theme_mode]
        self._notes_text.pack_forget()
        self._notes_save_btn.pack_forget()
        self._notes_back_btn.pack_forget()
        self._notes_title_label.configure(text='便签')
        self._notes_status.configure(text='')
        self._notes_current_id = None

        if self._notes_list_frame:
            self._notes_list_frame.destroy()

        notes = notes_service.load_all()

        outer = tk.Frame(self._notes_body, bg=th['BG_CONTENT'])
        outer.pack(fill=tk.BOTH, expand=True)
        self._notes_list_frame = outer

        _, inner = self._make_scrollable_frame(outer, th['BG_CONTENT'])

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
        self._notes_mode = 'edit'
        th = THEMES[self._theme_mode]
        notes = notes_service.load_all()

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
        if self._notes_current_id is not None:
            notes_service.update(self._notes_current_id, content)
        else:
            note = notes_service.create(content)
            self._notes_current_id = note['id']
        self._notes_status.configure(text=f'已保存 {time.strftime("%H:%M:%S")}')
        self._notes_show_list()

    def _notes_delete(self, note_id):
        remaining = notes_service.delete(note_id)
        if remaining:
            self._notes_show_list()
        else:
            self._notes_open_editor(None)

    # ══════════════════════════════════════════════════
    #  Tab: 天气
    # ══════════════════════════════════════════════════

    def _build_weather_tab(self, parent):
        th = THEMES[self._theme_mode]
        frame = tk.Frame(parent, bg=th['BG_CONTENT'])

        # ── 工具栏 ──
        toolbar = tk.Frame(frame, bg=th['BG_TOOLBAR'], height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text='天气', bg=th['BG_TOOLBAR'], fg=th['FG_MAIN'],
                 font=('PingFang SC', 13, 'bold')).pack(side=tk.LEFT, padx=16)

        self._weather_status = tk.Label(toolbar, text='', bg=th['BG_TOOLBAR'],
                                        fg=th['FG_MUTED'], font=('PingFang SC', 10))
        self._weather_status.pack(side=tk.LEFT, padx=4)

        # ── 右侧工具区：刷新按钮 ──
        right_area = tk.Frame(toolbar, bg=th['BG_TOOLBAR'])
        right_area.pack(side=tk.RIGHT, padx=12)

        def _do_refresh():
            city = self._weather_selected
            if not city:
                return
            if city in self._weather_fetching:
                self._weather_status.configure(text='正在刷新...')
                return
            self._weather_status.configure(text='正在刷新...')
            self._load_weather_async(city, force=True)

        refresh_btn = tk.Label(right_area, text='↻  刷新', bg=th['BG_TOOLBAR'],
                               fg=th['FG_ACCENT'], font=('PingFang SC', 12),
                               cursor='hand2', padx=10, pady=4)
        refresh_btn.pack(side=tk.LEFT)
        refresh_btn.bind('<Button-1>', lambda e: _do_refresh())
        refresh_btn.bind('<Enter>', lambda e: refresh_btn.configure(fg=th['FG_MAIN']))
        refresh_btn.bind('<Leave>', lambda e: refresh_btn.configure(fg=th['FG_ACCENT']))
        self._weather_refresh_btn = refresh_btn

        # 分隔线（工具栏下方）
        tk.Frame(frame, bg=th['DIVIDER'], height=1).pack(fill=tk.X)

        # ── 主体：左侧城市列表 + 右侧天气详情 ──
        body = tk.Frame(frame, bg=th['BG_CONTENT'])
        body.pack(fill=tk.BOTH, expand=True)
        self._weather_body = body

        # 左侧城市面板（固定 180px）
        self._weather_left = tk.Frame(body, bg=th['BG_SIDEBAR'], width=180)
        self._weather_left.pack(side=tk.LEFT, fill=tk.Y)
        self._weather_left.pack_propagate(False)

        # 垂直分隔线
        tk.Frame(body, bg=th['DIVIDER'], width=1).pack(side=tk.LEFT, fill=tk.Y)

        # 城市列表 frame（在左侧面板内）
        self._weather_city_list_frame = tk.Frame(self._weather_left, bg=th['BG_SIDEBAR'])
        self._weather_city_list_frame.pack(fill=tk.BOTH, expand=True)

        # 右侧天气详情
        self._weather_right = tk.Frame(body, bg=th['BG_CONTENT'])
        self._weather_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._weather_main_frame = tk.Frame(self._weather_right, bg=th['BG_CONTENT'])
        self._weather_main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        return frame

    def _rebuild_city_list(self):
        th = THEMES[self._theme_mode]
        for w in self._weather_city_list_frame.winfo_children():
            w.destroy()
        if not self._weather_cities:
            return
        for city in self._weather_cities:
            row = tk.Frame(self._weather_city_list_frame, bg=th['BG_SIDEBAR'], cursor='hand2')
            row.pack(fill=tk.X)
            is_sel = (city == self._weather_selected)
            row_bg = th['BG_SEL'] if is_sel else th['BG_SIDEBAR']
            row.configure(bg=row_bg)
            # left accent bar (3px)
            bar = tk.Frame(row, bg=th['ACCENT_BAR'] if is_sel else th['BG_SIDEBAR'], width=3)
            bar.pack(side=tk.LEFT, fill=tk.Y)
            bar.pack_propagate(False)
            name_lbl = tk.Label(row, text=city, bg=row_bg, fg=th['FG_MAIN'],
                                font=('PingFang SC', 11), anchor='w', padx=8, pady=8)
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            del_btn = tk.Label(row, text='×', bg=row_bg, fg=th['FG_MUTED'],
                               font=('PingFang SC', 12), cursor='hand2', padx=6)
            del_btn.pack(side=tk.RIGHT)
            # click row → select city
            def _click_city(e, c=city):
                self._weather_selected = c
                self._rebuild_city_list()
                self._render_current_weather()
            for w in (row, name_lbl):
                w.bind('<Button-1>', _click_city)
            # click × → delete
            def _del(e, c=city):
                self._weather_delete_city(c)
            del_btn.bind('<Button-1>', _del)
            # hover
            def _enter(e, r=row, b=bar, n=name_lbl, d=del_btn, c=city):
                if c != self._weather_selected:
                    for w in (r, n, d): w.configure(bg=th['BG_HOVER'])
            def _leave(e, r=row, b=bar, n=name_lbl, d=del_btn, c=city):
                if c != self._weather_selected:
                    for w in (r, n, d): w.configure(bg=th['BG_SIDEBAR'])
            for w in (row, name_lbl, del_btn):
                w.bind('<Enter>', _enter)
                w.bind('<Leave>', _leave)

        # 底部"＋ 添加城市"按钮
        add_row = tk.Frame(self._weather_city_list_frame, bg=th['BG_SIDEBAR'], cursor='hand2')
        add_row.pack(fill=tk.X, side=tk.BOTTOM)
        add_lbl = tk.Label(add_row, text='＋  添加城市', bg=th['BG_SIDEBAR'], fg=th['FG_ACCENT'],
                           font=('PingFang SC', 11), anchor='w', padx=14, pady=8)
        add_lbl.pack(fill=tk.X)
        def _show_add_input(e=None):
            self._weather_selected = None
            self._render_current_weather()
        for w in (add_row, add_lbl):
            w.bind('<Button-1>', _show_add_input)
            w.bind('<Enter>', lambda e: add_lbl.configure(fg=th['FG_MAIN']))
            w.bind('<Leave>', lambda e: add_lbl.configure(fg=th['FG_ACCENT']))

    def _weather_add_city(self, city):
        city = city.strip()
        if not city or city in self._weather_cities:
            return
        self._weather_cities.append(city)
        save_json(WEATHER_FILE, self._weather_cities)
        self._weather_selected = city
        self._rebuild_city_list()
        self._render_current_weather()
        self._weather_status.configure(text='正在加载...')
        self._load_weather_async(city)

    def _weather_delete_city(self, city):
        if city in self._weather_cities:
            self._weather_cities.remove(city)
        save_json(WEATHER_FILE, self._weather_cities)
        if self._weather_selected == city:
            self._weather_selected = self._weather_cities[0] if self._weather_cities else None
        self._rebuild_city_list()
        self._render_current_weather()

    def _load_weather_async(self, city, force=False):
        if city in self._weather_fetching:
            return
        self._weather_fetching.add(city)
        def run():
            try:
                data, from_cache, err = fetch_weather(city, force=force)
            finally:
                self._weather_fetching.discard(city)
            if self.win and self.win.winfo_exists():
                self.win.after(0, lambda: self._on_weather_loaded(city, data, err))
        threading.Thread(target=run, daemon=True).start()

    def _on_weather_loaded(self, city, data, err):
        if err:
            if city == self._weather_selected:
                self._weather_status.configure(text=f'⚠️ {err}')
            return
        ts = last_fetch_time(city)
        tstr = time.strftime('%H:%M', time.localtime(ts)) if ts else ''
        self._weather_status.configure(text=f'{tstr} 已更新' if tstr else '已更新')
        if city == self._weather_selected:
            self._render_current_weather()

    def _render_weather_loading(self):
        """在右侧主区域显示旋转加载动画，数据到达后会被 _render_current_weather 替换。"""
        th = THEMES[self._theme_mode]
        bg = th['BG_CONTENT']
        _FRAMES = ('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏')

        holder = tk.Frame(self._weather_main_frame, bg=bg)
        holder.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(holder, bg=bg)

        spinner_lbl = tk.Label(inner, text=_FRAMES[0], bg=bg,
                               fg=th['FG_ACCENT'], font=('PingFang SC', 22))
        spinner_lbl.pack(pady=(0, 6))
        tk.Label(inner, text='正在获取天气...', bg=bg,
                 fg=th['FG_MUTED'], font=('PingFang SC', 12)).pack()

        def _place_center(e=None, h=holder, i=inner):
            i.place(in_=h, relx=0.5, rely=0.5, anchor='center')
        holder.bind('<Configure>', _place_center)

        frame_idx = [0]
        def _tick():
            if not (spinner_lbl.winfo_exists() and self._weather_main_frame.winfo_exists()):
                return
            frame_idx[0] = (frame_idx[0] + 1) % len(_FRAMES)
            spinner_lbl.configure(text=_FRAMES[frame_idx[0]])
            spinner_lbl.after(100, _tick)
        _tick()

    def _render_current_weather(self):
        th = THEMES[self._theme_mode]
        for w in self._weather_main_frame.winfo_children():
            w.destroy()
        if not self._weather_selected:
            # 撑满容器，然后用 place 在其中居中
            bg = th['BG_CONTENT']
            holder = tk.Frame(self._weather_main_frame, bg=bg)
            holder.pack(fill=tk.BOTH, expand=True)
            inner = tk.Frame(holder, bg=bg)

            tk.Label(inner, text='☁️', bg=bg,
                     font=('Apple Color Emoji', 40)).pack(pady=(0, 6))
            tk.Label(inner, text='输入城市名，查看天气', bg=bg,
                     fg=th['FG_MUTED'], font=('PingFang SC', 13)).pack(pady=(0, 16))
            row = tk.Frame(inner, bg=bg)
            row.pack()
            search_bg = th['BG_SIDEBAR']
            SW, SH, SR = 260, 42, 10
            # Canvas 画圆角背景
            sc = tk.Canvas(row, width=SW, height=SH, bg=bg, highlightthickness=0)
            sc.pack(side=tk.LEFT, padx=(0, 10))
            self._draw_rounded_rect(sc, SW, SH, SR, search_bg, 'search_bg')
            # sf 用 place 叠在 Canvas 上，背景同色，不用 create_window
            sf = tk.Frame(sc, bg=search_bg, bd=0)
            sf.place(x=0, y=0, width=SW, height=SH)
            tk.Label(sf, text='🔍', bg=search_bg,
                     font=('Apple Color Emoji', 13)).pack(side=tk.LEFT, padx=(12, 2))
            center_entry = tk.Entry(sf, width=15, bg=search_bg, fg=th['FG_MAIN'],
                                    insertbackground=th['FG_MAIN'], relief=tk.FLAT,
                                    font=('PingFang SC', 14), bd=0, highlightthickness=0)
            center_entry.pack(side=tk.LEFT, padx=(0, 12), fill=tk.X, expand=True)

            # 添加按钮
            BW, BH, BR = 76, 38, 10
            bc = tk.Canvas(row, width=BW, height=BH, bg=bg, highlightthickness=0, cursor='hand2')
            bc.pack(side=tk.LEFT)

            def _draw_add_bg(fill, c=bc, w=BW, h=BH, r=BR):
                c.delete('all')
                self._draw_rounded_rect(c, w, h, r, fill, 'btn_bg')
                c.create_text(w//2, h//2, text='＋ 添加', fill='#ffffff',
                              font=('PingFang SC', 12, 'bold'))

            _draw_add_bg(th['BG_BTN'])

            def _center_add(e=None):
                self._weather_add_city(center_entry.get())

            center_entry.bind('<Return>', _center_add)
            bc.bind('<Button-1>', _center_add)
            bc.bind('<Enter>', lambda e: _draw_add_bg(th['FG_ACCENT']))
            bc.bind('<Leave>', lambda e: _draw_add_bg(th['BG_BTN']))

            # 等 holder 布局完成后再 place inner 居中
            def _place_center(e=None, h=holder, i=inner):
                i.place(in_=h, relx=0.5, rely=0.5, anchor='center')
            holder.bind('<Configure>', _place_center)
            center_entry.focus_set()
            return
        city = self._weather_selected
        data = get_cached_data(city)
        if not data:
            self._render_weather_loading()
            return
        emoji = code_to_emoji(data['code'])
        # Current conditions card
        card = tk.Frame(self._weather_main_frame, bg=th['BG_CARD'],
                        highlightthickness=1, highlightbackground=th['BORDER'])
        card.pack(fill=tk.X, padx=20, pady=(20, 10))
        # Top row: emoji + temp + desc
        top = tk.Frame(card, bg=th['BG_CARD'])
        top.pack(fill=tk.X, padx=16, pady=(14, 4))
        tk.Label(top, text=emoji, bg=th['BG_CARD'],
                 font=('Apple Color Emoji', 36)).pack(side=tk.LEFT, padx=(0, 12))
        info = tk.Frame(top, bg=th['BG_CARD'])
        info.pack(side=tk.LEFT)
        tk.Label(info, text=f"{data['temp_C']}°C", bg=th['BG_CARD'],
                 fg=th['FG_MAIN'], font=('PingFang SC', 28, 'bold')).pack(anchor='w')
        tk.Label(info, text=data['desc_zh'], bg=th['BG_CARD'],
                 fg=th['FG_MUTED'], font=('PingFang SC', 12)).pack(anchor='w')
        # Feels like
        tk.Label(card, text=f"体感 {data['feels_like_C']}°C", bg=th['BG_CARD'],
                 fg=th['FG_DIM'], font=('PingFang SC', 11),
                 anchor='w').pack(fill=tk.X, padx=16, pady=(0, 14))
        # City label
        tk.Label(self._weather_main_frame, text=city, bg=th['BG_CONTENT'],
                 fg=th['FG_MUTED'], font=('PingFang SC', 10)).pack(anchor='w', padx=20)
        self._render_forecast(data)

    def _render_forecast(self, data):
        """Render 3-day forecast cards below current conditions. Called from _render_current_weather."""
        th = THEMES[self._theme_mode]
        if not data.get('forecast'):
            return
        # Section header
        tk.Label(self._weather_main_frame, text='3天预报', bg=th['BG_CONTENT'],
                 fg=th['FG_MUTED'], font=('PingFang SC', 10),
                 anchor='w').pack(fill=tk.X, padx=20, pady=(12, 4))
        # Row of 3 forecast cards
        row = tk.Frame(self._weather_main_frame, bg=th['BG_CONTENT'])
        row.pack(fill=tk.X, padx=20, pady=(0, 16))
        for i, day in enumerate(data['forecast'][:3]):
            card = tk.Frame(row, bg=th['BG_CARD'],
                            highlightthickness=1, highlightbackground=th['BORDER'])
            card.pack(side=tk.LEFT, fill=tk.X, expand=True,
                      padx=(0, 8) if i < 2 else 0, pady=0)
            # Date label: 今天 / 明天 / formatted date
            date_label = self._fmt_forecast_date(day['date'], i)
            tk.Label(card, text=date_label, bg=th['BG_CARD'],
                     fg=th['FG_MUTED'], font=('PingFang SC', 10)).pack(pady=(10, 2))
            # Emoji — use the day's actual weather code (per WTHR-05)
            emoji = code_to_emoji(day.get('code', 0))
            tk.Label(card, text=emoji, bg=th['BG_CARD'],
                     font=('Apple Color Emoji', 22)).pack(pady=2)
            # Condition description
            tk.Label(card, text=day.get('desc', ''), bg=th['BG_CARD'],
                     fg=th['FG_DIM'], font=('PingFang SC', 9)).pack(pady=1)
            # High / Low temps
            tk.Label(card, text=f"{day['max_C']}° / {day['min_C']}°",
                     bg=th['BG_CARD'], fg=th['FG_MAIN'],
                     font=('PingFang SC', 11, 'bold')).pack(pady=(2, 10))

    def _fmt_forecast_date(self, iso_date, index):
        """Format ISO date string for forecast display.
        index 0 → '今天', index 1 → '明天', index 2+ → 'M/D' format.
        """
        if index == 0:
            return '今天'
        if index == 1:
            return '明天'
        try:
            d = _dt.strptime(iso_date, '%Y-%m-%d')
            return d.strftime('%-m/%-d')
        except ValueError:
            return iso_date[5:]  # fallback: 'MM-DD'

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
        if hasattr(self, '_home_emoji') and self._home_emoji:
            self._home_emoji.itemconfig(self._home_emoji_id, text=em)

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