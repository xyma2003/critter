from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt6.QtGui import QMovie, QPainter, QAction
from config import Config, ASSETS_DIR
from .animation_manager import AnimationManager, AnimationState
from .event_handler import EventHandler
from utils.screen_utils import ScreenUtils
from ui.speech_bubble import SpeechBubble


class _PetLabel(QLabel):
    """Paint each original movie frame smoothly at the window's current size."""

    def paintEvent(self, event):
        movie = self.movie()
        if movie is None or movie.currentPixmap().isNull():
            super().paintEvent(event)
            return
        pixmap = movie.currentPixmap()
        fitted = pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRectF((self.width() - fitted.width()) / 2,
                        (self.height() - fitted.height()) / 2,
                        fitted.width(), fitted.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # QPainter applies the destination screen's device-pixel ratio. Keep
        # the original frame instead of repeatedly scaling an already reduced
        # image when the alarm enlarges the window or moves between screens.
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.main_panel = None
        self._movie = None  # Keep the running QMovie alive until replacement.
        self._animation_state = AnimationState.IDLE_SLEEP
        self.animation_error = None
        self._closed = False
        self._suppress_click_release = False
        self.animation_manager = AnimationManager(self)
        self.event_handler = EventHandler(self)
        self.alert_timer = QTimer(self)
        self.alert_timer.setInterval(50)
        self.alert_timer.timeout.connect(self._move_randomly)
        self.alert_position = QPoint(0, 0)
        self.alert_velocity = QPoint(5, 5)
        self.speech_bubble = SpeechBubble()
        self.init_ui()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_animations)

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(*Config.PET_SIZE)
        self.setStyleSheet("background: transparent;")

        self.pet_label = _PetLabel(self)
        self.pet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pet_label.setGeometry(self.rect())
        self.pet_label.setStyleSheet("background: transparent;")
        self.update_animation(AnimationState.IDLE_SLEEP)
        self.animation_manager.start()

    def _stop_movie(self):
        movie = self._movie
        self._movie = None
        if movie is not None:
            # QLabel must release the old movie too; otherwise a late frame or
            # error from that movie can overwrite a newly selected animation.
            self.pet_label.clear()
            try:
                movie.error.disconnect()
            except TypeError:
                pass
            movie.stop()
            movie.deleteLater()

    def _fallback_text(self):
        states = {
            AnimationState.IDLE_SLEEP: ("😴", "休息"),
            AnimationState.IDLE_WALK: ("🐕", "走动"),
            AnimationState.INTERACT_WASH: ("🛁", "洗脸"),
            AnimationState.INTERACT_WAG: ("🐶", "摇尾巴"),
            AnimationState.ALERT_RUN: ("🚨", "提醒"),
        }
        emoji, title = states.get(self._animation_state, ("🐕", "桌宠"))
        size = max(24, int(min(self.width(), self.height()) * 0.36))
        self.pet_label.setText(
            f'<div style="font-size:{size}px">{emoji}</div>'
            f'<div style="font-size:11px">{title} · 动画暂不可用</div>')

    def _show_fallback(self, reason):
        self._stop_movie()
        self.animation_error = reason
        self.pet_label.clear()
        self.pet_label.setToolTip(reason)
        self._fallback_text()

    def _handle_movie_error(self, movie):
        # A signal from an old decoder must not clear the current animation.
        if self._movie is movie:
            self._show_fallback("动画无法继续播放，已显示备用形象。")

    def update_animation(self, state: AnimationState):
        if self._closed:
            return
        self._animation_state = state
        self._stop_movie()
        animation_path = ASSETS_DIR / 'animations' / Config.DEFAULT_PET / f'{state.value}.gif'
        if not animation_path.is_file():
            self._show_fallback("未找到这个动作的动画，已显示备用形象。")
            return

        movie = QMovie(str(animation_path), parent=self)
        movie.setCacheMode(QMovie.CacheMode.CacheAll)
        # Check that the first frame can actually be decoded. A present file
        # alone does not imply a usable GIF, and QLabel must never stay blank.
        if not movie.isValid() or not movie.jumpToFrame(0) or movie.currentPixmap().isNull():
            movie.stop()
            movie.deleteLater()
            self._show_fallback("这个动作的动画无法读取，已显示备用形象。")
            return
        self._movie = movie
        self.animation_error = None
        self.pet_label.clear()
        self.pet_label.setToolTip("")
        self.pet_label.setMovie(movie)
        movie.error.connect(lambda _error, source=movie: self._handle_movie_error(source))
        movie.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "pet_label"):
            self.pet_label.setGeometry(self.rect())
            if self.animation_error is not None:
                self._fallback_text()

    def mousePressEvent(self, event):
        self.event_handler.handle_mouse_press(event)

    def mouseMoveEvent(self, event):
        self.event_handler.handle_mouse_move(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._suppress_click_release:
                self._suppress_click_release = False
                return
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
        quit_action.triggered.connect(QApplication.quit)
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

    def _clamp_position(self):
        screen_width, screen_height = ScreenUtils.get_screen_size()
        self.move(max(0, min(self.x(), max(0, screen_width - self.width()))),
                  max(0, min(self.y(), max(0, screen_height - self.height()))))

    def trigger_alert_animation(self):
        if self._closed:
            return
        self.animation_manager.trigger_alert()
        scale = Config.PET_SCALE_ALERT
        new_size = (int(Config.PET_SIZE[0] * scale), int(Config.PET_SIZE[1] * scale))
        self.resize(*new_size)
        self.pet_label.setGeometry(self.rect())
        self._clamp_position()
        # Reuse one owned timer even when a second reminder arrives.
        self.alert_timer.start()

    def _move_randomly(self):
        screen_width, screen_height = ScreenUtils.get_screen_size()
        max_x = max(0, screen_width - self.width())
        max_y = max(0, screen_height - self.height())
        new_x = self.x() + self.alert_velocity.x()
        new_y = self.y() + self.alert_velocity.y()
        if new_x <= 0 or new_x >= max_x:
            self.alert_velocity.setX(-self.alert_velocity.x())
        if new_y <= 0 or new_y >= max_y:
            self.alert_velocity.setY(-self.alert_velocity.y())
        self.move(max(0, min(new_x, max_x)), max(0, min(new_y, max_y)))
        self.speech_bubble.reposition_to(self)

    def stop_alert_animation(self):
        self.alert_timer.stop()
        self.resize(*Config.PET_SIZE)
        self.pet_label.setGeometry(self.rect())
        self._clamp_position()
        self.animation_manager.stop_alert()

    def show_bubble(self, text: str, duration_ms: int = 4000):
        """在宠物头顶显示气泡对话框"""
        if not self._closed:
            self.speech_bubble.show_message(text, self, duration_ms)

    def mouseDoubleClickEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.animation_manager.current_state == AnimationState.ALERT_RUN):
            # Qt delivers a final release after doubleClick. It must not turn
            # the just-dismissed alarm into a fresh single-click interaction.
            self._suppress_click_release = True
            self.stop_alert_animation()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _shutdown_animations(self):
        if self._closed:
            return
        self._closed = True
        self.animation_manager.stop()
        self.alert_timer.stop()
        self._stop_movie()
        self.speech_bubble._hide_timer.stop()
        self.speech_bubble.close()

    def closeEvent(self, event):
        self._shutdown_animations()
        super().closeEvent(event)
