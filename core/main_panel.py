"""
core/main_panel.py — 合并版主面板（PyQt6 + 7 Tab）

Tab 顺序：主页 | 新闻 | 宠物 | 便签 | 天气 | 日记 | 设置
AI 路由：含触发词 → LangGraph Agent，否则 → Claude CLI 流式聊天
"""
import datetime
import os
import subprocess
import threading
import time

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QLineEdit, QTextEdit, QScrollArea,
    QFrame, QSizePolicy, QProgressBar, QMessageBox,
)
from PyQt6.QtGui import QFont

from config import Config, CLAUDE_CLI
from core.state_manager import (
    load_chat_history, save_chat_history,
    load_chat_sessions, save_chat_sessions,
    load_settings, save_settings,
    load_theme, save_theme,
)
from data.pet import PetStats, FEED_LINES, PLAY_LINES, REST_LINES, PET_LINES
from features.base_feature import BaseFeature
from features.news_push.news_feature import NewsFeature, NewsFetchWorker
from features.timer.timer_feature import TimerFeature
from services.chat_history import load_sessions, save_session
from services.notes import load_all as load_notes, create as create_note, update as update_note, delete as delete_note
from services.weather import fetch_weather
from ui.chat_list import ChatList
from ui.feature_button import FeatureButton
from ui.theme import apply_theme
from langchain_core.messages import HumanMessage

import random


# ─────────────────────────────────────────────────────────
#  Claude CLI 流式聊天线程
# ─────────────────────────────────────────────────────────

class ClaudeCliThread(QThread):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal(str)

    def __init__(self, prompt: str, system: str = ""):
        super().__init__()
        self.prompt = prompt
        self.system = system

    def run(self):
        accumulated = ""
        try:
            cmd = [CLAUDE_CLI, '--print', self.prompt]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True)
            for line in proc.stdout:
                accumulated += line
                self.chunk_received.emit(line)
            proc.wait()
        except Exception as e:
            accumulated = f"呜，出了点小问题：{e}"
        self.finished.emit(accumulated.strip())


class OpenAIChatThread(QThread):
    """SiliconFlow / OpenAI-compatible chat thread — used when OPENAI_API_KEY is set."""
    finished = pyqtSignal(str)

    def __init__(self, prompt: str, system: str = ""):
        super().__init__()
        self.prompt = prompt
        self.system = system

    def run(self):
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                base_url=os.environ.get("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            )
            messages = []
            if self.system:
                messages.append({"role": "system", "content": self.system})
            messages.append({"role": "user", "content": self.prompt})
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "Qwen/Qwen3-32B"),
                messages=messages,
                max_tokens=300,
                temperature=0.8,
            )
            text = resp.choices[0].message.content.strip()
            self.finished.emit(text or "…")
        except Exception as e:
            self.finished.emit(f"呜，出了点小问题：{e}")


# ─────────────────────────────────────────────────────────
#  LangGraph Agent 线程（来自桌面动物园）
# ─────────────────────────────────────────────────────────

class AgentThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, agent_graph, user_input: str):
        super().__init__()
        self.agent_graph = agent_graph
        self.user_input = user_input

    def run(self):
        try:
            initial_state = {
                "messages": [HumanMessage(content=self.user_input)],
                "current_task": "",
                "plan": [],
                "steps_completed": [],
                "tool_results": {},
                "reasoning": "",
                "needs_human_approval": False,
                "status": "planning",
            }
            result = self.agent_graph.invoke(initial_state)
            final = result["messages"][-1].content if result["messages"] else "执行完成"
            self.finished.emit(final)
        except Exception as e:
            self.finished.emit(f"抱歉，执行出错：{e}")


# ─────────────────────────────────────────────────────────
#  天气后台获取线程
# ─────────────────────────────────────────────────────────

class WeatherThread(QThread):
    done = pyqtSignal(object, bool, object)  # data, from_cache, error

    def __init__(self, city: str, force: bool = False):
        super().__init__()
        self.city = city
        self.force = force

    def run(self):
        data, from_cache, error = fetch_weather(self.city, self.force)
        self.done.emit(data, from_cache, error)


# ─────────────────────────────────────────────────────────
#  主面板
# ─────────────────────────────────────────────────────────

class MainPanel(QWidget):
    NAV_W = 80

    def __init__(self, pet_window):
        super().__init__()
        self.pet_window = pet_window

        # 宠物状态
        self.stats = PetStats()

        # 设置
        self._app_settings = load_settings()
        self._theme_mode = load_theme()

        # 聊天 session
        self._sessions = load_sessions()
        self._current_session: dict | None = None
        self._chat_history: list = []

        # AI
        self.agent_graph = None
        self._ai_thread = None
        if Config.ENABLE_AI_AGENT:
            try:
                from agent import create_agent_graph
                self.agent_graph = create_agent_graph()
            except Exception as e:
                print(f"LangGraph Agent 初始化失败: {e}")

        # 功能插件
        self._features: list[BaseFeature] = []
        self._news_feature = NewsFeature()
        self._timer_feature = TimerFeature()
        self._timer_feature.pet_window_ref = pet_window
        self._features.append(self._news_feature)
        self._features.append(self._timer_feature)

        # Inject live instances into agent/tools.py so the AI agent's set_timer
        # tool uses the SAME TimerFeature (with pet_window_ref set) — otherwise
        # the alarm animation would never fire when set via chat.
        try:
            from agent.tools import set_features
            set_features(self._news_feature, self._timer_feature)
        except Exception:
            pass

        # 天气
        self._weather_cities: list[str] = self._app_settings.get('weather_cities', [])
        self._weather_selected: str | None = (
            self._weather_cities[0] if self._weather_cities else None
        )
        self._weather_data: dict = {}

        # 状态衰减定时器
        self._decay_timer = QTimer(self)
        self._decay_timer.timeout.connect(self._on_decay_tick)
        self._decay_timer.start(PetStats.DECAY_INTERVAL_MS)

        self._init_ui()

    # ─── 初始化 UI ───────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("桌面宠物")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(Config.MAIN_PANEL_WIDTH, Config.MAIN_PANEL_HEIGHT)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧导航
        self._nav = QWidget(objectName="nav_bar")
        self._nav.setFixedWidth(self.NAV_W)
        nav_layout = QVBoxLayout(self._nav)
        nav_layout.setContentsMargins(4, 12, 4, 12)
        nav_layout.setSpacing(4)

        self._stack = QStackedWidget(objectName="content_area")

        tabs = [
            ("🏠", "主页",  self._build_home_tab),
            ("📰", "新闻",  self._build_news_tab),
            ("🐾", "宠物",  self._build_pet_tab),
            ("📝", "便签",  self._build_notes_tab),
            ("🌤", "天气",  self._build_weather_tab),
            ("📖", "日记",  self._build_diary_tab),
            ("⚙️", "设置",  self._build_settings_tab),
        ]

        self._nav_btns: list[QPushButton] = []
        for emoji, label, builder in tabs:
            btn = QPushButton(f"{emoji}\n{label}", objectName="nav_btn")
            btn.setCheckable(True)
            btn.setFixedHeight(64)
            # emoji 行大，文字行小
            f = QFont("PingFang SC", 10)
            btn.setFont(f)
            nav_layout.addWidget(btn)
            self._nav_btns.append(btn)

            page = QWidget()
            builder(page)
            self._stack.addWidget(page)

        nav_layout.addStretch()

        for i, btn in enumerate(self._nav_btns):
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))

        self._nav_btns[0].setChecked(True)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)

        root.addWidget(self._nav)
        root.addWidget(line)
        root.addWidget(self._stack, 1)

    def _switch_tab(self, idx: int):
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
        self._stack.setCurrentIndex(idx)

    # ─── Tab 1: 主页（聊天）────────────────────────────

    def _build_home_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QWidget(objectName="toolbar")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)
        title = QLabel("🏠 主页", objectName="title")
        tb_layout.addWidget(title)
        tb_layout.addStretch()
        new_chat_btn = QPushButton("+ 新对话", objectName="secondary_btn")
        new_chat_btn.clicked.connect(self._new_chat_session)
        tb_layout.addWidget(new_chat_btn)
        layout.addWidget(toolbar)

        # 聊天列表
        self.chat_list = ChatList()
        layout.addWidget(self.chat_list, 1)

        # 恢复历史消息
        saved = load_chat_history(50)
        if saved:
            self._chat_history = list(saved)
            for msg in saved:
                self.chat_list.add_message(msg["content"], is_user=(msg["role"] == "user"))
        else:
            welcome = f"你好！我是你的桌面边牧，叫{self._app_settings.get('pet_name', '边牧')}~ {self._app_settings.get('pet_catchphrase', '汪~')}"
            self.chat_list.add_message(welcome)
            self._record_message(welcome, "pet")

        # 输入区
        input_frame = QWidget()
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(8)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("说点什么……")
        self.input_box.returnPressed.connect(self._on_send)

        send_btn = QPushButton("发送")
        send_btn.setFixedWidth(72)
        send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self.input_box, 1)
        input_layout.addWidget(send_btn)
        layout.addWidget(input_frame)

    def _on_send(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        self.chat_list.add_message(text, is_user=True)
        self._record_message(text, "user")

        # AI 路由
        if self.agent_graph and any(kw in text for kw in Config.AGENT_TRIGGER_KEYWORDS):
            self.chat_list.add_message("让我想想… 🤔")
            self._ai_thread = AgentThread(self.agent_graph, text)
            self._ai_thread.finished.connect(self._on_agent_done)
            self._ai_thread.start()
        else:
            settings = self._app_settings
            catchphrase = settings.get('pet_catchphrase', '汪~')
            system = (
                f"你是一只可爱的桌面宠物边牧，名字叫{settings.get('pet_name','边牧')}，"
                f"性格{settings.get('pet_personality','活泼')}，"
                f"口头禅是\"{catchphrase}\"，"
                "说话简短可爱，回复 2-3 句，不要用 Markdown。"
                + self.stats.system_prompt_hint()
            )
            self.chat_list.add_message("…")
            if os.environ.get("OPENAI_API_KEY"):
                self._ai_thread = OpenAIChatThread(text, system)
            else:
                self._ai_thread = ClaudeCliThread(text, system)
            self._ai_thread.finished.connect(self._on_cli_done)
            self._ai_thread.start()

    def _on_cli_done(self, response: str):
        # 替换占位 "…"
        self.chat_list.replace_last_pet_message(response)
        self._record_message(response, "pet")
        self.stats.on_chat()
        self._save_current_session(response)

    def _on_agent_done(self, response: str):
        self.chat_list.add_message(response)
        self._record_message(response, "pet")
        self.stats.on_chat()

    def _record_message(self, content: str, role: str):
        self._chat_history.append({
            "role": role,
            "content": content,
            "ts": datetime.datetime.now().isoformat(),
        })
        if len(self._chat_history) > 200:
            self._chat_history = self._chat_history[-200:]
        save_chat_history(self._chat_history[-50:])

    def _new_chat_session(self):
        if self._current_session and self._current_session.get('bubbles'):
            save_session(self._current_session)
        self._current_session = {
            'id': int(time.time() * 1000),
            'title': '',
            'bubbles': [],
        }
        self.chat_list.clear_messages()
        self._chat_history = []
        # Add welcome message to new session
        welcome = f"你好！我是你的桌面边牧，叫{self._app_settings.get('pet_name', '边牧')}~ {self._app_settings.get('pet_catchphrase', '汪~')}"
        self.chat_list.add_message(welcome)
        self._record_message(welcome, "pet")

    def _save_current_session(self, last_response: str):
        if self._current_session is None:
            # Lazily create a session so the first chat (without clicking "+ 新对话") persists
            self._current_session = {
                'id': int(time.time() * 1000),
                'title': '',
                'bubbles': [],
            }
        if not self._current_session.get('title') and self._chat_history:
            for msg in self._chat_history:
                if msg['role'] == 'user':
                    self._current_session['title'] = msg['content'][:20]
                    break
        if self._chat_history:
            self._current_session['bubbles'] = [
                [m['role'], m['content']] for m in self._chat_history
            ]
            save_session(self._current_session)

    # ─── Tab 2: 新闻 ────────────────────────────────────

    def _build_news_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget(objectName="toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.addWidget(QLabel("📰 热点新闻", objectName="title"))
        tb.addStretch()
        refresh_btn = QPushButton("刷新", objectName="secondary_btn")
        refresh_btn.clicked.connect(self._refresh_news)
        tb.addWidget(refresh_btn)
        layout.addWidget(toolbar)

        # 滚动区域放新闻卡片
        self._news_scroll = QScrollArea()
        self._news_scroll.setWidgetResizable(True)
        self._news_scroll.setStyleSheet("QScrollArea { border: none; }")
        self._news_container = QWidget()
        self._news_layout = QVBoxLayout(self._news_container)
        self._news_layout.setContentsMargins(12, 12, 12, 12)
        self._news_layout.setSpacing(8)
        self._news_layout.addWidget(QLabel("点击刷新获取今日热点…", objectName="subtitle"))
        self._news_layout.addStretch()
        self._news_scroll.setWidget(self._news_container)
        layout.addWidget(self._news_scroll, 1)

    def _refresh_news(self):
        # 清空
        while self._news_layout.count():
            item = self._news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        loading = QLabel("获取中…", objectName="subtitle")
        self._news_layout.addWidget(loading)
        self._news_layout.addStretch()

        # 后台获取 — must use QThread + pyqtSignal, NOT threading.Thread + QTimer.singleShot
        # (QTimer from a bg thread without event loop never fires)
        self._news_worker = NewsFetchWorker(self._news_feature)
        self._news_worker.result_ready.connect(
            lambda result: self._render_news_cards(result.get('data', []), result.get('success', False))
        )
        self._news_worker.error_occurred.connect(self._render_news_error)
        self._news_worker.start()

    def _render_news_error(self, msg: str):
        """Show an error message in the news panel when fetch fails."""
        while self._news_layout.count():
            item = self._news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        err = QLabel(msg, objectName="subtitle")
        err.setStyleSheet("color: #ef5350; padding: 20px;")
        self._news_layout.addWidget(err)
        self._news_layout.addStretch()

    def _render_news_cards(self, items: list, success: bool):
        # 清空
        while self._news_layout.count():
            item = self._news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not items:
            self._news_layout.addWidget(QLabel("暂无新闻，请检查网络后重试", objectName="subtitle"))
            self._news_layout.addStretch()
            return

        for news_item in items:
            card = QFrame(objectName="card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(4)

            # 来源标签
            source = news_item.get('source', '')
            if source:
                src_lbl = QLabel(source, objectName="subtitle")
                card_layout.addWidget(src_lbl)

            # 标题
            title = news_item.get('title', '')
            title_lbl = QLabel(title)
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet("font-size: 13px; font-weight: 500;")
            card_layout.addWidget(title_lbl)

            # 链接按钮（只有有链接才显示）
            link = news_item.get('link', '').strip()
            if link:
                link_btn = QPushButton("🔗 查看原文", objectName="secondary_btn")
                link_btn.setFixedHeight(28)
                link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                link_btn.clicked.connect(lambda _, url=link: subprocess.Popen(['open', url]))
                card_layout.addWidget(link_btn)

            self._news_layout.addWidget(card)

        self._news_layout.addStretch()

    # ─── Tab 3: 宠物 ────────────────────────────────────

    def _build_pet_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("🐾 我的宠物", objectName="title"))

        # 状态栏
        stats_frame = QFrame(objectName="card")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(12, 12, 12, 12)
        stats_layout.setSpacing(8)

        self._mood_label = QLabel(objectName="subtitle")
        self._hunger_bar = QProgressBar()
        self._energy_bar = QProgressBar()
        self._mood_bar = QProgressBar()

        for bar in (self._hunger_bar, self._energy_bar, self._mood_bar):
            bar.setRange(0, 100)
            bar.setTextVisible(False)

        stats_layout.addWidget(self._mood_label)
        stats_layout.addWidget(QLabel("🍚 饱食度"))
        stats_layout.addWidget(self._hunger_bar)
        stats_layout.addWidget(QLabel("⚡ 精力"))
        stats_layout.addWidget(self._energy_bar)
        stats_layout.addWidget(QLabel("😊 心情"))
        stats_layout.addWidget(self._mood_bar)
        layout.addWidget(stats_frame)

        self._update_pet_stats_ui()

        # 互动按钮
        btn_frame = QFrame(objectName="card")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(12, 12, 12, 12)
        btn_layout.setSpacing(8)

        for label, slot in [
            ("🍚 喂食", self._pet_feed),
            ("🎾 玩耍", self._pet_play),
            ("🤲 抚摸", self._pet_pet),
            ("💤 休息", self._pet_rest),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_layout.addWidget(btn)

        layout.addWidget(btn_frame)

        # 互动日志
        self._pet_log = QTextEdit()
        self._pet_log.setReadOnly(True)
        self._pet_log.setMaximumHeight(150)
        self._pet_log.setPlaceholderText("互动记录…")
        layout.addWidget(self._pet_log)
        layout.addStretch()

    def _update_pet_stats_ui(self):
        if not hasattr(self, '_mood_label'):
            return
        self._mood_label.setText(self.stats.mood_label())
        self._hunger_bar.setValue(int(self.stats.hunger))
        self._energy_bar.setValue(int(self.stats.energy))
        self._mood_bar.setValue(int(self.stats.mood))

    def _log_pet(self, text: str):
        ts = datetime.datetime.now().strftime("%H:%M")
        self._pet_log.append(f"[{ts}] {text}")

    def _pet_feed(self):
        lines = FEED_LINES['starving'] if self.stats.hunger < 30 else (
            FEED_LINES['hungry'] if self.stats.hunger < 70 else FEED_LINES['full'])
        self.stats.feed()
        self._update_pet_stats_ui()
        msg = random.choice(lines)
        self._log_pet(msg)

    def _pet_play(self):
        lines = PLAY_LINES['bored'] if self.stats.mood < 40 else (
            PLAY_LINES['tired'] if self.stats.energy < 30 else PLAY_LINES['normal'])
        self.stats.play()
        self._update_pet_stats_ui()
        self._log_pet(random.choice(lines))

    def _pet_pet(self):
        lines = PET_LINES['happy'] if self.stats.mood >= 60 else (
            PET_LINES['bored'] if self.stats.mood < 30 else PET_LINES['normal'])
        self.stats.pet()
        self._update_pet_stats_ui()
        self._log_pet(random.choice(lines))

    def _pet_rest(self):
        lines = REST_LINES['exhausted'] if self.stats.energy < 30 else (
            REST_LINES['energetic'] if self.stats.energy > 70 else REST_LINES['normal'])
        self.stats.rest()
        self._update_pet_stats_ui()
        self._log_pet(random.choice(lines))

    def _on_decay_tick(self):
        self.stats.decay()
        self._update_pet_stats_ui()

    # ─── Tab 4: 便签 ────────────────────────────────────

    def _build_notes_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QWidget(objectName="toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.addWidget(QLabel("📝 便签", objectName="title"))
        tb.addStretch()
        new_btn = QPushButton("+ 新建", objectName="secondary_btn")
        new_btn.clicked.connect(self._new_note)
        tb.addWidget(new_btn)
        layout.addWidget(toolbar)

        # 便签列表
        self._notes_list_widget = QWidget()
        notes_scroll = QScrollArea()
        notes_scroll.setWidgetResizable(True)
        notes_scroll.setWidget(self._notes_list_widget)
        self._notes_list_layout = QVBoxLayout(self._notes_list_widget)
        self._notes_list_layout.setContentsMargins(12, 12, 12, 12)
        self._notes_list_layout.setSpacing(8)
        self._notes_list_layout.addStretch()
        layout.addWidget(notes_scroll, 1)

        self._refresh_notes_list()

    def _refresh_notes_list(self):
        # 清空
        while self._notes_list_layout.count() > 1:
            item = self._notes_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        notes = load_notes()
        for note in reversed(notes):
            card = QFrame(objectName="card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            title_text = note.get('title') or note.get('content', '')[:30]
            title_lbl = QLabel(title_text, objectName="subtitle")
            title_lbl.setWordWrap(True)

            btn_row = QHBoxLayout()
            edit_btn = QPushButton("编辑", objectName="secondary_btn")
            edit_btn.setFixedWidth(50)
            del_btn = QPushButton("删除", objectName="secondary_btn")
            del_btn.setFixedWidth(50)
            note_id = note['id']
            edit_btn.clicked.connect(lambda _, nid=note_id: self._edit_note(nid))
            del_btn.clicked.connect(lambda _, nid=note_id: self._delete_note(nid))
            btn_row.addWidget(edit_btn)
            btn_row.addWidget(del_btn)
            btn_row.addStretch()

            card_layout.addWidget(title_lbl)
            card_layout.addLayout(btn_row)
            self._notes_list_layout.insertWidget(
                self._notes_list_layout.count() - 1, card)

    def _new_note(self):
        self._open_note_editor(None)

    def _edit_note(self, note_id):
        self._open_note_editor(note_id)

    def _open_note_editor(self, note_id):
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        notes = load_notes()
        note = next((n for n in notes if n['id'] == note_id), None)

        dlg = QDialog(self)
        dlg.setWindowTitle("编辑便签" if note else "新建便签")
        dlg.resize(500, 400)
        dlg_layout = QVBoxLayout(dlg)

        title_input = QLineEdit()
        title_input.setPlaceholderText("标题（选填）")
        if note:
            title_input.setText(note.get('title', ''))

        content_input = QTextEdit()
        content_input.setPlaceholderText("内容…")
        if note:
            content_input.setPlainText(note.get('content', ''))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        dlg_layout.addWidget(title_input)
        dlg_layout.addWidget(content_input, 1)
        dlg_layout.addWidget(buttons)

        if dlg.exec():
            title = title_input.text().strip()
            content = content_input.toPlainText().strip()
            if content:
                if note:
                    update_note(note_id, content, title)
                else:
                    create_note(content, title)
                self._refresh_notes_list()

    def _delete_note(self, note_id):
        delete_note(note_id)
        self._refresh_notes_list()

    # ─── Tab 5: 天气 ────────────────────────────────────

    def _build_weather_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QWidget(objectName="toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.addWidget(QLabel("🌤 天气", objectName="title"))
        tb.addStretch()
        layout.addWidget(toolbar)

        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)

        # 左：城市列表
        city_frame = QFrame(objectName="card")
        city_frame.setFixedWidth(130)
        city_layout = QVBoxLayout(city_frame)
        city_layout.setContentsMargins(8, 8, 8, 8)
        city_layout.setSpacing(4)

        self._city_list_layout = city_layout

        add_city_input = QLineEdit()
        add_city_input.setPlaceholderText("添加城市…")
        add_city_input.returnPressed.connect(lambda: self._add_city(add_city_input.text()))
        city_layout.addWidget(add_city_input)
        city_layout.addStretch()
        self._city_add_input = add_city_input

        # 右：天气详情
        self._weather_detail = QLabel("← 选择或添加城市")
        self._weather_detail.setWordWrap(True)
        self._weather_detail.setAlignment(Qt.AlignmentFlag.AlignTop)

        body.addWidget(city_frame)
        body.addWidget(self._weather_detail, 1)
        layout.addLayout(body, 1)

        self._rebuild_city_list()

    def _rebuild_city_list(self):
        layout = self._city_list_layout
        # 清除旧按钮（保留输入框和 stretch）
        while layout.count() > 2:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        for city in self._weather_cities:
            btn = QPushButton(city, objectName="secondary_btn")
            btn.clicked.connect(lambda _, c=city: self._select_city(c))
            layout.insertWidget(layout.count() - 1, btn)

    def _add_city(self, city: str):
        city = city.strip()
        if city and city not in self._weather_cities:
            self._weather_cities.append(city)
            settings = self._app_settings
            settings['weather_cities'] = self._weather_cities
            save_settings(settings)
            self._city_add_input.clear()
            self._rebuild_city_list()
            self._select_city(city)

    def _select_city(self, city: str):
        self._weather_selected = city
        self._weather_detail.setText(f"⏳ 获取 {city} 天气中…")
        self._weather_thread = WeatherThread(city)  # 保存引用防止被 GC
        self._weather_thread.done.connect(self._on_weather_loaded)
        self._weather_thread.start()

    def _on_weather_loaded(self, data, from_cache, error):
        if error:
            self._weather_detail.setText(f"❌ {error}")
            return
        if not data:
            self._weather_detail.setText("暂无数据")
            return

        lines = [
            f"📍 {self._weather_selected}",
            f"{data.get('desc_zh','--')}  {data.get('temp_C','--')}°C",
            f"体感 {data.get('feels_like_C','--')}°C",
            "",
        ]
        for day in data.get('forecast', []):
            lines.append(f"{day['date']}  {day.get('desc','')}  "
                         f"{day.get('min_C','--')}~{day.get('max_C','--')}°C")
        self._weather_detail.setText("\n".join(lines))

    # ─── Tab 6: 日记 ────────────────────────────────────

    def _build_diary_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QWidget(objectName="toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.addWidget(QLabel("📖 宠物日记", objectName="title"))
        tb.addStretch()
        gen_btn = QPushButton("生成今日日记", objectName="secondary_btn")
        gen_btn.clicked.connect(self._generate_diary)
        tb.addWidget(gen_btn)
        layout.addWidget(toolbar)

        self._diary_text = QTextEdit()
        self._diary_text.setReadOnly(True)
        self._diary_text.setPlaceholderText('点击\u201c生成今日日记\u201d，Claude 会以宠物视角记录今天\u2026')
        layout.addWidget(self._diary_text, 1)

    def _generate_diary(self):
        from services.diary import DiaryWorker
        from services.notes import create_diary
        settings = self._app_settings
        stats_snap = {
            'mood':       self.stats.mood,
            'hunger':     self.stats.hunger,
            'energy':     self.stats.energy,
            'mood_label': self.stats.mood_label(),
        }
        date_str = datetime.date.today().isoformat()
        self._diary_text.setPlainText("正在生成日记…")

        def on_diary_ready(text):
            self._diary_text.setPlainText(text)
            # Persist the generated diary as a note with kind='diary'
            try:
                create_diary(text, date_str)
            except Exception:
                pass  # persistence is best-effort; display still works

        self._diary_worker = DiaryWorker(
            stats_snap, {},
            settings.get('pet_name', '边牧'),
            settings.get('pet_personality', '活泼'),
            settings.get('pet_catchphrase', '汪~'),
            date_str,
        )
        self._diary_worker.result_ready.connect(on_diary_ready)
        self._diary_worker.error_occurred.connect(
            lambda msg: self._diary_text.setPlainText(msg)
        )
        self._diary_worker.start()

    # ─── Tab 7: 设置 ────────────────────────────────────

    def _build_settings_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("⚙️ 设置", objectName="title"))

        settings = self._app_settings

        # 宠物人设
        pet_frame = QFrame(objectName="card")
        pet_layout = QVBoxLayout(pet_frame)
        pet_layout.setContentsMargins(12, 12, 12, 12)
        pet_layout.setSpacing(8)
        pet_layout.addWidget(QLabel("宠物人设"))

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名字"))
        self._pet_name_input = QLineEdit(settings.get('pet_name', '边牧'))
        name_row.addWidget(self._pet_name_input)
        pet_layout.addLayout(name_row)

        personality_row = QHBoxLayout()
        personality_row.addWidget(QLabel("性格"))
        self._pet_personality_input = QLineEdit(settings.get('pet_personality', '活泼'))
        personality_row.addWidget(self._pet_personality_input)
        pet_layout.addLayout(personality_row)

        catchphrase_row = QHBoxLayout()
        catchphrase_row.addWidget(QLabel("口头禅"))
        self._pet_catchphrase_input = QLineEdit(settings.get('pet_catchphrase', '汪~'))
        catchphrase_row.addWidget(self._pet_catchphrase_input)
        pet_layout.addLayout(catchphrase_row)

        layout.addWidget(pet_frame)

        # 主题
        theme_frame = QFrame(objectName="card")
        theme_layout = QHBoxLayout(theme_frame)
        theme_layout.setContentsMargins(12, 12, 12, 12)
        theme_layout.addWidget(QLabel("主题"))
        theme_layout.addStretch()

        light_btn = QPushButton("☀️ 浅色")
        dark_btn = QPushButton("🌙 深色")
        light_btn.setObjectName("secondary_btn")
        dark_btn.setObjectName("secondary_btn")
        light_btn.clicked.connect(lambda: self._apply_theme('light'))
        dark_btn.clicked.connect(lambda: self._apply_theme('dark'))
        theme_layout.addWidget(light_btn)
        theme_layout.addWidget(dark_btn)
        layout.addWidget(theme_frame)

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()

    def _save_settings(self):
        self._app_settings['pet_name'] = self._pet_name_input.text().strip() or '边牧'
        self._app_settings['pet_personality'] = self._pet_personality_input.text().strip() or '活泼'
        self._app_settings['pet_catchphrase'] = self._pet_catchphrase_input.text().strip() or '汪~'
        save_settings(self._app_settings)

    def _apply_theme(self, mode: str):
        from PyQt6.QtWidgets import QApplication
        self._theme_mode = mode
        save_theme(mode)
        apply_theme(QApplication.instance(), mode)
