"""
core/main_panel.py — 合并版主面板（PyQt6 + 7 Tab）

Tab 顺序：主页 | 新闻 | 宠物 | 便签 | 天气 | 日记 | 设置
AI 路由：含触发词 → LangGraph Agent，否则 → OpenAI-compatible API 或 Claude CLI
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

from config import Config, CLAUDE_CLI
from core.state_manager import (
    load_chat_history, save_chat_history,
    load_chat_sessions, save_chat_sessions,
    load_settings, save_settings,
    load_theme, save_theme,
    load_pet_interaction_counts,
    get_state_file,
)
from data.pet import PetStats, FEED_LINES, PLAY_LINES, REST_LINES, PET_LINES
from features.base_feature import BaseFeature
from features.news_push.news_feature import NewsFeature, NewsFetchWorker
from features.timer.timer_feature import TimerFeature
from services.chat_history import load_sessions, save_session
from services.chat_context import ChatRequest, build_chat_request, api_messages, cli_prompt
from services.notes import load_all as load_notes, create as create_note, update as update_note, delete as delete_note
from services.weather import fetch_weather
from ui.chat_list import ChatList
from ui.feature_button import FeatureButton
from ui.theme import apply_theme
from ui.storage_notice import StorageNotice
from langchain_core.messages import HumanMessage, AIMessage

import random


# ─────────────────────────────────────────────────────────
#  Claude CLI 聊天线程
# ─────────────────────────────────────────────────────────

class ClaudeCliThread(QThread):
    reply_ready = pyqtSignal(str, bool)

    def __init__(self, request: ChatRequest):
        super().__init__()
        self.request = request

    def run(self):
        try:
            system = self.request.system + (
                "\n输入是按时间排列的 JSON 对话记录。role=user 是用户，"
                "role=assistant 是你先前的回复。请结合记录，只回复最后一条 user 消息。"
            )
            cmd = [CLAUDE_CLI, '--print', '--system-prompt', system,
                   '--no-session-persistence', '--tools', '', '--strict-mcp-config']
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            output, error = proc.communicate(input=cli_prompt(self.request))
            if proc.returncode:
                raise RuntimeError(f"CLI 退出码 {proc.returncode}：{error.strip()[:500]}")
            if not output.strip():
                raise RuntimeError("CLI 没有返回回复")
            self.reply_ready.emit(output.strip(), True)
        except Exception as e:
            self.reply_ready.emit(f"呜，出了点小问题：{e}", False)


class OpenAIChatThread(QThread):
    """SiliconFlow / OpenAI-compatible chat thread — used when OPENAI_API_KEY is set."""
    reply_ready = pyqtSignal(str, bool)

    def __init__(self, request: ChatRequest):
        super().__init__()
        self.request = request

    def run(self):
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                base_url=os.environ.get("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            )
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "Qwen/Qwen3-32B"),
                messages=api_messages(self.request),
                max_tokens=300,
                temperature=0.8,
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text:
                raise RuntimeError("模型没有返回回复")
            self.reply_ready.emit(text, True)
        except Exception as e:
            self.reply_ready.emit(f"呜，出了点小问题：{e}", False)


# ─────────────────────────────────────────────────────────
#  LangGraph Agent 线程（来自桌面动物园）
# ─────────────────────────────────────────────────────────

class AgentThread(QThread):
    reply_ready = pyqtSignal(str, bool)

    def __init__(self, agent_graph, request: ChatRequest):
        super().__init__()
        self.agent_graph = agent_graph
        self.request = request

    def run(self):
        try:
            initial_state = {
                "messages": [],
                "conversation": [
                    (HumanMessage if message.role == "user" else AIMessage)(content=message.content)
                    for message in self.request.messages
                ],
                "system_prompt": self.request.system,
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
            self.reply_ready.emit(final, True)
        except Exception as e:
            self.reply_ready.emit(f"抱歉，执行出错：{e}", False)


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
    NAV_W = 200

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
        self._last_session_id = max(
            (s['id'] for s in self._sessions if isinstance(s.get('id'), int)), default=0)
        self._current_session: dict | None = None
        self._chat_history: list = []
        self._chat_generation = 0

        # AI
        self.agent_graph = None
        self._ai_thread = None
        self._chat_threads = set()
        self._diary_worker = None
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
        self._storage_notice.refresh()

    # ─── 初始化 UI ───────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("Critter · 你的桌面伙伴")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1040, 760)
        self.setMinimumSize(860, 660)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧导航
        self._nav = QWidget(objectName="nav_bar")
        self._nav.setFixedWidth(self.NAV_W)
        nav_layout = QVBoxLayout(self._nav)
        nav_layout.setContentsMargins(16, 20, 16, 16)
        nav_layout.setSpacing(4)
        nav_layout.addWidget(QLabel("critter", objectName="brand"))
        nav_layout.addWidget(QLabel("桌面上的小伙伴", objectName="nav_caption"))
        nav_layout.addSpacing(20)

        identity = QFrame(objectName="pet_identity")
        identity_layout = QHBoxLayout(identity)
        identity_layout.setContentsMargins(12, 14, 12, 14)
        identity_layout.addWidget(QLabel("🐕", objectName="pet_avatar"))
        identity_text = QVBoxLayout()
        self._identity_name = QLabel(objectName="pet_name")
        self._identity_name.setTextFormat(Qt.TextFormat.PlainText)
        self._identity_name.setText(self._app_settings.get('pet_name', '边牧'))
        self._identity_name.setWordWrap(True)
        identity_text.addWidget(self._identity_name)
        self._identity_mood = QLabel(self.stats.mood_label(), objectName="subtitle")
        self._identity_mood.setWordWrap(True)
        identity_text.addWidget(self._identity_mood)
        identity_layout.addLayout(identity_text, 1)
        nav_layout.addWidget(identity)
        nav_layout.addSpacing(12)

        self._stack = QStackedWidget(objectName="content_area")

        tabs = [
            ("◌", "聊天",  self._build_home_tab),
            ("📰", "新闻",  self._build_news_tab),
            ("🐾", "宠物",  self._build_pet_tab),
            ("📝", "便签",  self._build_notes_tab),
            ("🌤", "天气",  self._build_weather_tab),
            ("📖", "日记",  self._build_diary_tab),
            ("⚙️", "设置",  self._build_settings_tab),
        ]

        self._nav_btns: list[QPushButton] = []
        for emoji, label, builder in tabs:
            btn = QPushButton(f"{emoji}   {label}", objectName="nav_btn")
            btn.setCheckable(True)
            btn.setMinimumHeight(42)
            self._nav_btns.append(btn)

            page = QWidget()
            builder(page)
            self._stack.addWidget(page)

        nav_layout.addWidget(QLabel("陪伴", objectName="nav_caption"))
        for idx in (0, 2, 5):
            nav_layout.addWidget(self._nav_btns[idx])
        nav_layout.addSpacing(8)
        nav_layout.addWidget(QLabel("日常", objectName="nav_caption"))
        for idx in (3, 4, 1):
            nav_layout.addWidget(self._nav_btns[idx])
        nav_layout.addStretch()
        nav_layout.addWidget(self._nav_btns[6])

        for i, btn in enumerate(self._nav_btns):
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))

        self._nav_btns[0].setChecked(True)

        root.addWidget(self._nav)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self._storage_notice = StorageNotice(content)
        self._storage_notice.attention_required.connect(self._show_storage_problem)
        content_layout.addWidget(self._storage_notice)
        content_layout.addWidget(self._stack, 1)
        root.addWidget(content, 1)

    def _show_storage_problem(self):
        # The app normally starts with only the pet visible. Never hide a
        # persistence problem in a panel the user has not opened yet.
        self.show()
        self.raise_()
        self.activateWindow()

    def _page_header(self, title: str, description: str, action=None, padding=24):
        header = QWidget(objectName="toolbar")
        row = QHBoxLayout(header)
        row.setContentsMargins(padding, 22, padding, 18)
        text = QVBoxLayout()
        text.setSpacing(6)
        text.addWidget(QLabel(title, objectName="title"))
        subtitle = QLabel(description, objectName="subtitle")
        subtitle.setWordWrap(True)
        text.addWidget(subtitle)
        row.addLayout(text, 1)
        if action is not None:
            row.addSpacing(16)
            row.addWidget(action)
        return header

    def _configuration_summary(self) -> tuple[str, str]:
        """Report detected configuration only; this does not test a connection."""
        api_present = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        cli_present = os.path.isfile(CLAUDE_CLI) and os.access(CLAUDE_CLI, os.X_OK)
        if api_present:
            chat = "聊天：已检测到 API 配置，连接尚未测试。"
        elif cli_present:
            chat = "聊天：已找到 Claude CLI，登录状态尚未验证。"
        else:
            chat = "聊天：尚未配置。可以先照顾宠物、记录便签。"
        agent_key = api_present or bool(
            os.environ.get("ANTHROPIC_API_KEY", "").strip() or Config.ANTHROPIC_API_KEY
        )
        if self.agent_graph is None:
            agent = "Agent：当前未启用或初始化未完成。"
        elif agent_key:
            agent = "Agent：已检测到 API 配置，连接尚未测试。"
        else:
            agent = "Agent：需要配置 API 凭据后使用。"
        return chat, agent

    def _switch_tab(self, idx: int):
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
        self._stack.setCurrentIndex(idx)
        if idx == 5:
            self._refresh_diary_evidence()

    # ─── Tab 1: 主页（聊天）────────────────────────────

    def _build_home_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        new_chat_btn = QPushButton("+ 新对话", objectName="secondary_btn")
        new_chat_btn.clicked.connect(self._new_chat_session)
        layout.addWidget(self._page_header("聊天", "说说今天，也留下一点灵感。", new_chat_btn))

        intro = QFrame(objectName="intro_card")
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(20, 16, 20, 16)
        intro_layout.setSpacing(10)
        intro_layout.addWidget(QLabel("今天，从一件小事开始", objectName="section_title"))
        status = QLabel(self._configuration_summary()[0], objectName="status_label")
        status.setWordWrap(True)
        intro_layout.addWidget(status)
        shortcuts = QHBoxLayout()
        for label, idx in (("照顾宠物", 2), ("记录便签", 3), ("AI 配置说明", 6)):
            button = QPushButton(label, objectName="secondary_btn")
            button.clicked.connect(lambda _, target=idx: self._switch_tab(target))
            shortcuts.addWidget(button)
        shortcuts.addStretch()
        intro_layout.addLayout(shortcuts)
        intro_row = QHBoxLayout()
        intro_row.setContentsMargins(24, 18, 24, 8)
        intro_row.addWidget(intro)
        layout.addLayout(intro_row)

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
            self._record_message(welcome, "pet", include_in_context=False)

        # 输入区
        input_frame = QWidget()
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(24, 12, 24, 22)
        input_layout.setSpacing(8)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("想聊些什么？按 Enter 发送")
        self.input_box.returnPressed.connect(self._on_send)

        send_btn = QPushButton("发送")
        send_btn.setMinimumWidth(80)
        send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self.input_box, 1)
        input_layout.addWidget(send_btn)
        layout.addWidget(input_frame)

    def _on_send(self):
        text = self.input_box.text().strip()
        if not text:
            return
        try:
            request = build_chat_request(
                [*self._chat_history, {"role": "user", "content": text}],
                self._app_settings, self.stats.system_prompt_hint())
        except ValueError as error:
            QMessageBox.information(self, "暂时无法发送", str(error))
            return
        self.input_box.clear()
        self.chat_list.add_message(text, is_user=True)
        self._record_message(text, "user")
        self._save_current_session(text)

        # AI 路由
        if self.agent_graph and any(kw in text for kw in Config.AGENT_TRIGGER_KEYWORDS):
            placeholder = self.chat_list.add_message("让我想想… 🤔")
            thread = AgentThread(self.agent_graph, request)
        else:
            placeholder = self.chat_list.add_message("…")
            if os.environ.get("OPENAI_API_KEY"):
                thread = OpenAIChatThread(request)
            else:
                thread = ClaudeCliThread(request)
        generation = self._chat_generation
        self._ai_thread = thread
        # Switching conversations must not destroy an in-flight QThread. Keep
        # it alive until Qt's actual finished signal, separate from reply_ready.
        self._chat_threads.add(thread)
        thread.reply_ready.connect(
            lambda response, success, g=generation, bubble=placeholder:
                self._receive_chat_reply(g, bubble, response, success),
            Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(lambda worker=thread: self._release_chat_thread(worker))
        thread.start()

    def _release_chat_thread(self, thread):
        self._chat_threads.discard(thread)
        if self._ai_thread is thread:
            self._ai_thread = None
        thread.deleteLater()

    def _receive_chat_reply(self, generation, placeholder, response, success):
        if generation != self._chat_generation:
            return
        placeholder.update_text(response)
        self.chat_list._scroll_to_bottom()
        self._record_reply(response, success)

    def _record_reply(self, response, success=True):
        self._record_message(response, "pet", include_in_context=success)
        if success:
            self.stats.on_chat()
            self._update_pet_stats_ui()
        self._save_current_session(response)

    def _on_cli_done(self, response: str):
        # 替换占位 "…"
        self.chat_list.replace_last_pet_message(response)
        self._record_reply(response)

    def _on_agent_done(self, response: str):
        self.chat_list.replace_last_pet_message(response)
        self._record_reply(response)

    def _record_message(self, content: str, role: str, include_in_context=True):
        self._chat_history.append({
            "role": role,
            "content": content,
            "ts": datetime.datetime.now().isoformat(),
            "include_in_context": include_in_context,
        })
        if len(self._chat_history) > 200:
            self._chat_history = self._chat_history[-200:]
        save_chat_history(self._chat_history[-50:])

    def _new_chat_session(self):
        if self._current_session and self._current_session.get('bubbles'):
            save_session(self._current_session)
        self._chat_generation += 1
        self._current_session = self._empty_chat_session()
        self.chat_list.clear_messages()
        self._chat_history = []
        # Add welcome message to new session
        welcome = f"你好！我是你的桌面边牧，叫{self._app_settings.get('pet_name', '边牧')}~ {self._app_settings.get('pet_catchphrase', '汪~')}"
        self.chat_list.add_message(welcome)
        self._record_message(welcome, "pet", include_in_context=False)

    def _empty_chat_session(self):
        self._last_session_id = max(int(time.time() * 1000), self._last_session_id + 1)
        return {'id': self._last_session_id, 'title': '', 'bubbles': []}

    def _save_current_session(self, last_response: str):
        if self._current_session is None:
            # Lazily create a session so the first chat (without clicking "+ 新对话") persists
            self._current_session = self._empty_chat_session()
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

        refresh_btn = QPushButton("刷新", objectName="secondary_btn")
        refresh_btn.clicked.connect(self._refresh_news)
        layout.addWidget(self._page_header("热点新闻", "有空时，看看外面正在发生什么。", refresh_btn))

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
                link_btn.setMinimumHeight(36)
                link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                link_btn.clicked.connect(lambda _, url=link: subprocess.Popen(['open', url]))
                card_layout.addWidget(link_btn)

            self._news_layout.addWidget(card)

        self._news_layout.addStretch()

    # ─── Tab 3: 宠物 ────────────────────────────────────

    def _build_pet_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(24, 0, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(self._page_header("照顾宠物", "吃饱、玩耍、休息，一起过好平常的一天。", padding=0))

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
        self._identity_mood.setText(self.stats.mood_label())
        self._hunger_bar.setValue(int(self.stats.hunger))
        self._energy_bar.setValue(int(self.stats.energy))
        self._mood_bar.setValue(int(self.stats.mood))

    def _log_pet(self, text: str):
        ts = datetime.datetime.now().strftime("%H:%M")
        self._pet_log.append(f"[{ts}] {text}")
        self._refresh_diary_evidence()

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

        new_btn = QPushButton("+ 新建", objectName="secondary_btn")
        new_btn.clicked.connect(self._new_note)
        layout.addWidget(self._page_header("便签", "把稍纵即逝的想法，放在这里。", new_btn))

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
        if not notes:
            empty = QLabel("还没有便签\n\n点右上角「新建」，记下一个想法或一件小事。", objectName="subtitle")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(180)
            empty.setWordWrap(True)
            self._notes_list_layout.insertWidget(0, empty)
        for note in reversed(notes):
            card = QFrame(objectName="card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            title_text = note.get('title') or note.get('content', '')[:30]
            title_lbl = QLabel(title_text, objectName="subtitle")
            title_lbl.setWordWrap(True)

            btn_row = QHBoxLayout()
            edit_btn = QPushButton("编辑", objectName="secondary_btn")
            edit_btn.setMinimumWidth(76)
            del_btn = QPushButton("删除", objectName="secondary_btn")
            del_btn.setMinimumWidth(76)
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
        if note_id is not None and note is None:
            # A repaired duplicate ID or a removed note must never turn an
            # edit request into creating an unrelated new note.
            self._refresh_notes_list()
            return

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

        layout.addWidget(self._page_header("天气", "为出门做一点准备。查询需要联网。"))

        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)

        # 左：城市列表
        city_frame = QFrame(objectName="card")
        city_frame.setFixedWidth(180)
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
        self._weather_detail = QLabel("想看看哪里的天气？\n\n在左侧输入城市并按 Enter，或选择已经添加的城市。", objectName="subtitle")
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

        self._diary_generate_btn = QPushButton("生成今日日记", objectName="secondary_btn")
        self._diary_generate_btn.clicked.connect(self._generate_diary)
        layout.addWidget(self._page_header("宠物日记", "用伙伴的视角，写下今天。生成需要 AI 配置。", self._diary_generate_btn))

        self._diary_evidence_label = QLabel(objectName="subtitle")
        self._diary_evidence_label.setTextFormat(Qt.TextFormat.PlainText)
        self._diary_evidence_label.setWordWrap(True)
        self._diary_evidence_label.setContentsMargins(24, 12, 24, 12)
        layout.addWidget(self._diary_evidence_label)
        self._refresh_diary_evidence()

        self._diary_source_label = QLabel(objectName="subtitle")
        self._diary_source_label.setTextFormat(Qt.TextFormat.PlainText)
        self._diary_source_label.setWordWrap(True)
        self._diary_source_label.setContentsMargins(24, 0, 24, 8)
        layout.addWidget(self._diary_source_label)

        self._diary_date_timer = QTimer(self)
        self._diary_date_timer.setInterval(30_000)
        self._diary_date_timer.timeout.connect(
            lambda: self._refresh_diary_evidence() if self._stack.currentIndex() == 5 else None)
        self._diary_date_timer.start()

        self._diary_text = QTextEdit()
        self._diary_text.setReadOnly(True)
        self._diary_text.setPlaceholderText('本页显示本次生成的日记。\n\n配置 AI 后，点击右上角生成；已经保存的日记可在「便签」中回看。')
        layout.addWidget(self._diary_text, 1)

    @staticmethod
    def _diary_counts_text(counts):
        return " · ".join(f"{label} {counts.get(kind, 0)} 次" for kind, label in (
            ("feed", "喂食"), ("play", "玩耍"), ("pet", "抚摸"), ("rest", "休息")))

    def _refresh_diary_evidence(self, date_str=None, counts=None):
        date_str = date_str or datetime.date.today().isoformat()
        if counts is None:
            counts = load_pet_interaction_counts(date_str)
        summary = self._diary_counts_text(counts)
        explanation = "仅统计已记录的四类互动；旧版未保存的记录无法补回。"
        if not any(counts.values()):
            explanation = "当天未记录到这四类互动，不代表没有发生；不会补造旧记录。"
        self._diary_evidence_label.setText(f"{date_str} 已记录：{summary}\n{explanation}")
        return counts

    def _generate_diary(self):
        if self._diary_worker is not None:
            return
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
        counts = self._refresh_diary_evidence(date_str)
        self._diary_source_label.setText(
            f"本次生成依据：{date_str} · {self._diary_counts_text(counts)}")
        self._diary_text.setPlainText("正在生成日记…")
        self._diary_generate_btn.setEnabled(False)

        def on_diary_ready(text):
            self._diary_text.setPlainText(text)
            # Persist the generated diary as a note with kind='diary'
            create_diary(text, date_str)
            self._refresh_notes_list()

        self._diary_worker = DiaryWorker(
            stats_snap, counts,
            settings.get('pet_name', '边牧'),
            settings.get('pet_personality', '活泼'),
            settings.get('pet_catchphrase', '汪~'),
            date_str,
        )
        self._diary_worker.result_ready.connect(on_diary_ready, Qt.ConnectionType.QueuedConnection)
        self._diary_worker.error_occurred.connect(
            lambda msg: self._diary_text.setPlainText(msg), Qt.ConnectionType.QueuedConnection
        )
        self._diary_worker.finished.connect(self._finish_diary_generation)
        self._diary_worker.start()

    def _finish_diary_generation(self):
        worker = self._diary_worker
        self._diary_worker = None
        self._diary_generate_btn.setEnabled(True)
        if worker is not None:
            worker.deleteLater()

    # ─── Tab 7: 设置 ────────────────────────────────────

    def _build_settings_tab(self, parent: QWidget):
        page_layout = QVBoxLayout(parent)
        page_layout.setContentsMargins(0, 0, 0, 0)
        self._settings_scroll = QScrollArea()
        self._settings_scroll.setWidgetResizable(True)
        self._settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self._settings_scroll.setWidget(content)
        page_layout.addWidget(self._settings_scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 0, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(self._page_header("设置", "让这个小伙伴，更像你喜欢的样子。", padding=0))

        setup = QFrame(objectName="card")
        setup_layout = QVBoxLayout(setup)
        setup_layout.setContentsMargins(16, 14, 16, 14)
        setup_layout.addWidget(QLabel("AI 配置", objectName="section_title"))
        for summary in self._configuration_summary():
            summary_label = QLabel(summary, objectName="status_label")
            summary_label.setWordWrap(True)
            setup_layout.addWidget(summary_label)
        guide = QLabel(
            "首次配置时，在项目目录将 .env.example 复制为 .env；已有 .env 时直接编辑。"
            "按 README 填写一个后端的凭据，再重启 Critter。"
            "这些状态只检查本机配置，不代表连接成功；宠物互动和便签无需 AI。",
            objectName="subtitle",
        )
        guide.setWordWrap(True)
        setup_layout.addWidget(guide)
        layout.addWidget(setup)

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
        self._theme_buttons = {'light': light_btn, 'dark': dark_btn}
        for mode, button in self._theme_buttons.items():
            button.setCheckable(True)
            button.setChecked(self._theme_mode == mode)
        light_btn.clicked.connect(lambda: self._apply_theme('light'))
        dark_btn.clicked.connect(lambda: self._apply_theme('dark'))
        theme_layout.addWidget(light_btn)
        theme_layout.addWidget(dark_btn)
        layout.addWidget(theme_frame)

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        self._data_path_label = QLabel(f"本地数据：{get_state_file()}\n备份前请先退出 Critter。", objectName="subtitle")
        self._data_path_label.setTextFormat(Qt.TextFormat.PlainText)
        self._data_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._data_path_label.setWordWrap(True)
        layout.addWidget(self._data_path_label)
        layout.addStretch()

    def _save_settings(self):
        self._app_settings['pet_name'] = self._pet_name_input.text().strip() or '边牧'
        self._app_settings['pet_personality'] = self._pet_personality_input.text().strip() or '活泼'
        self._app_settings['pet_catchphrase'] = self._pet_catchphrase_input.text().strip() or '汪~'
        save_settings(self._app_settings)
        self._identity_name.setText(self._app_settings['pet_name'])

    def _apply_theme(self, mode: str):
        from PyQt6.QtWidgets import QApplication
        self._theme_mode = mode
        save_theme(mode)
        apply_theme(QApplication.instance(), mode)
        for theme, button in self._theme_buttons.items():
            button.setChecked(theme == mode)
