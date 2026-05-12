"""
ui/chat_list.py — 聊天列表，气泡风格，跟随主题色
"""
from PyQt6.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath


class BubbleLabel(QWidget):
    """单条消息气泡"""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(0)

        # 气泡内容标签
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if is_user:
            self._label.setStyleSheet("""
                QLabel {
                    background-color: #FF8C42;
                    color: #FFFFFF;
                    border-radius: 14px;
                    padding: 10px 14px;
                    font-size: 13px;
                }
            """)
            self._label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
            outer.addStretch()
            outer.addWidget(self._label)
        else:
            self._label.setStyleSheet("""
                QLabel {
                    background-color: #FFFFFF;
                    color: #3D2B1F;
                    border-radius: 14px;
                    border: 1px solid #F0D8C0;
                    padding: 10px 14px;
                    font-size: 13px;
                }
            """)
            self._label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
            outer.addWidget(self._label)
            outer.addStretch()

    def update_text(self, text: str):
        self._label.setText(text)

    def apply_dark(self):
        if self.is_user:
            self._label.setStyleSheet("""
                QLabel {
                    background-color: #E07535;
                    color: #FFFFFF;
                    border-radius: 14px;
                    padding: 10px 14px;
                    font-size: 13px;
                }
            """)
        else:
            self._label.setStyleSheet("""
                QLabel {
                    background-color: #3D3530;
                    color: #F5E8DC;
                    border-radius: 14px;
                    border: 1px solid #4A3C30;
                    padding: 10px 14px;
                    font-size: 13px;
                }
            """)


class ChatList(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 12, 8, 12)
        self._layout.setSpacing(4)
        self._layout.addStretch()

        self.setWidget(self._container)
        self._bubbles: list[BubbleLabel] = []

    def add_message(self, message: str, is_user: bool = False) -> BubbleLabel:
        bubble = BubbleLabel(message, is_user)
        # 插入到 stretch 前面
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def replace_last_pet_message(self, text: str):
        """替换最后一条宠物消息（用于流式输出占位替换）"""
        for bubble in reversed(self._bubbles):
            if not bubble.is_user:
                bubble.update_text(text)
                self._scroll_to_bottom()
                return
        # 没找到就新增
        self.add_message(text, is_user=False)

    def clear_messages(self):
        for bubble in self._bubbles:
            self._layout.removeWidget(bubble)
            bubble.deleteLater()
        self._bubbles.clear()

    def _scroll_to_bottom(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))
