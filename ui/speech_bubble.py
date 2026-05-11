from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont


class SpeechBubble(QWidget):
    """宠物头顶的对话气泡，显示一段时间后自动消失"""

    BUBBLE_BG = QColor(255, 255, 255, 230)
    BUBBLE_BORDER = QColor(180, 180, 180)
    TAIL_HEIGHT = 10  # 气泡下方三角形的高度

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        font = QFont()
        font.setPointSize(12)
        self._label.setFont(font)
        self._label.setStyleSheet("color: #333333; background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10 + self.TAIL_HEIGHT)
        layout.addWidget(self._label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_message(self, text: str, anchor_widget: QWidget, duration_ms: int = 4000):
        """在 anchor_widget 正上方显示气泡，duration_ms 后自动隐藏"""
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()

        # 限制最大宽度
        max_w = 220
        if self.width() > max_w:
            self._label.setFixedWidth(max_w - 24)
            self._label.adjustSize()
            self.adjustSize()

        # 计算气泡应出现的屏幕坐标（宠物窗口正上方居中）
        anchor_pos = anchor_widget.mapToGlobal(QPoint(0, 0))
        anchor_center_x = anchor_pos.x() + anchor_widget.width() // 2
        bubble_x = anchor_center_x - self.width() // 2
        bubble_y = anchor_pos.y() - self.height()

        self.move(bubble_x, bubble_y)
        self.show()
        self.raise_()

        self._hide_timer.stop()
        self._hide_timer.start(duration_ms)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height() - self.TAIL_HEIGHT
        r = 8  # 圆角半径
        tail_w = 14
        tail_x = w // 2 - tail_w // 2  # 三角形底边中心对齐气泡中心

        path = QPainterPath()
        path.moveTo(r, 0)
        path.lineTo(w - r, 0)
        path.quadTo(w, 0, w, r)
        path.lineTo(w, h - r)
        path.quadTo(w, h, w - r, h)
        path.lineTo(tail_x + tail_w, h)
        path.lineTo(w // 2, h + self.TAIL_HEIGHT)  # 三角尖
        path.lineTo(tail_x, h)
        path.lineTo(r, h)
        path.quadTo(0, h, 0, h - r)
        path.lineTo(0, r)
        path.quadTo(0, 0, r, 0)
        path.closeSubpath()

        painter.fillPath(path, self.BUBBLE_BG)
        painter.setPen(self.BUBBLE_BORDER)
        painter.drawPath(path)
