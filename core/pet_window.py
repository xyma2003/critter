from PyQt6.QtWidgets import QWidget, QLabel, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QAction
from config import Config
from .animation_manager import AnimationManager, AnimationState
from .event_handler import EventHandler
from utils.screen_utils import ScreenUtils
from ui.speech_bubble import SpeechBubble
import random
import os


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.main_panel = None
        self.animation_manager = AnimationManager(self)
        self.event_handler = EventHandler(self)
        self.alert_timer = None
        self.alert_position = QPoint(0, 0)
        self.alert_velocity = QPoint(5, 5)
        self.speech_bubble = SpeechBubble()
        self.init_ui()

    def init_ui(self):
        # 无边框、置顶、透明背景
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置窗口大小
        self.resize(*Config.PET_SIZE)

        # 透明背景
        self.setStyleSheet("background: transparent;")

        # 显示宠物图片
        self.pet_label = QLabel(self)
        self.pet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pet_label.resize(*Config.PET_SIZE)
        self.pet_label.setStyleSheet("background: transparent;")

        # 加载默认动画
        self.update_animation(AnimationState.IDLE_SLEEP)

        # 启动动画管理器
        self.animation_manager.start()

    def update_animation(self, state: AnimationState):
        # 加载对应的动画资源
        animation_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'assets', 'animations', Config.DEFAULT_PET, f'{state.value}.gif'
        )

        if os.path.exists(animation_path):
            pixmap = QPixmap(animation_path)
            self.pet_label.setPixmap(pixmap.scaled(
                *Config.PET_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            # No GIF assets shipped — fall back to per-state emoji so the
            # AnimationManager state switching is still visible to the user.
            # Ship assets/animations/<pet>/<state>.gif to enable real animations.
            state_emoji = {
                AnimationState.IDLE_SLEEP: "😴",
                AnimationState.IDLE_WALK: "🐕",
                AnimationState.INTERACT_WASH: "🛁",
                AnimationState.INTERACT_WAG: "🐶",
                AnimationState.ALERT_RUN: "🚨",
            }
            self.pet_label.setText(state_emoji.get(state, "🐕"))

    def mousePressEvent(self, event):
        self.event_handler.handle_mouse_press(event)

    def mouseMoveEvent(self, event):
        self.event_handler.handle_mouse_move(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            moved = (event.globalPosition().toPoint() - self.event_handler.drag_position - self.pos()).manhattanLength()
            if moved < 5:
                self.event_handler.handle_single_click()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        open_action = QAction("打开面板", self)
        open_action.triggered.connect(self.show_main_panel)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(lambda: __import__('sys').exit(0))
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(pos)

    def show_main_panel(self):
        if self.main_panel:
            self.main_panel.show()
            self.main_panel.raise_()
            self.main_panel.activateWindow()

    def set_main_panel(self, panel):
        self.main_panel = panel

    def trigger_alert_animation(self):
        # 放大并全屏跑动
        self.animation_manager.trigger_alert()
        scale = Config.PET_SCALE_ALERT
        new_size = (int(Config.PET_SIZE[0] * scale), int(Config.PET_SIZE[1] * scale))
        self.resize(*new_size)
        self.pet_label.resize(*new_size)

        # 开始随机移动
        self.alert_timer = QTimer()
        self.alert_timer.timeout.connect(self._move_randomly)
        self.alert_timer.start(50)

    def _move_randomly(self):
        screen_width, screen_height = ScreenUtils.get_screen_size()
        current_pos = self.pos()

        # 更新位置
        new_x = current_pos.x() + self.alert_velocity.x()
        new_y = current_pos.y() + self.alert_velocity.y()

        # 边界检测和反弹
        if new_x <= 0 or new_x >= screen_width - self.width():
            self.alert_velocity.setX(-self.alert_velocity.x())
        if new_y <= 0 or new_y >= screen_height - self.height():
            self.alert_velocity.setY(-self.alert_velocity.y())

        self.move(new_x, new_y)

    def stop_alert_animation(self):
        if self.alert_timer:
            self.alert_timer.stop()
            self.alert_timer = None

        # 恢复正常大小
        self.resize(*Config.PET_SIZE)
        self.pet_label.resize(*Config.PET_SIZE)
        self.animation_manager.set_state(AnimationState.IDLE_SLEEP)

    def show_bubble(self, text: str, duration_ms: int = 4000):
        """在宠物头顶显示气泡对话框"""
        self.speech_bubble.show_message(text, self, duration_ms)

    def mouseDoubleClickEvent(self, event):
        # 如果在闹钟模式，双击停止
        if self.alert_timer:
            self.stop_alert_animation()
