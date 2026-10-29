"""Plain-text conversation bubbles styled by the application theme."""
from PyQt6.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QTimer


class BubbleLabel(QWidget):
    """A message with a readable line length at both wide and narrow sizes."""

    MAX_CONTENT_WIDTH = 580

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_bubble_row")
        self.is_user = is_user
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(0)

        self._label = QLabel(objectName="chat_bubble")
        self._label.setProperty("role", "user" if is_user else "pet")
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setText(text)
        self._label.setWordWrap(True)
        self._label.setMinimumWidth(0)
        self._label.setMaximumWidth(self.MAX_CONTENT_WIDTH)
        self._label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if is_user:
            outer.addStretch()
            outer.addWidget(self._label)
        else:
            outer.addWidget(self._label)
            outer.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep room opposite each message, without forcing a minimum bubble
        # width that could clip text when the conversation becomes narrower.
        available = max(1, self.contentsRect().width())
        self._label.setMaximumWidth(min(self.MAX_CONTENT_WIDTH, max(1, int(available * 0.88))))

    def update_text(self, text: str):
        self._label.setText(text)


class ChatList(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chat_list")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget(objectName="chat_container")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setSpacing(8)
        self._layout.addStretch()

        self.setWidget(self._container)
        self._bubbles: list[BubbleLabel] = []
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(50)
        self._scroll_timer.timeout.connect(self._apply_scroll)

    def add_message(self, message: str, is_user: bool = False) -> BubbleLabel:
        bubble = BubbleLabel(message, is_user)
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def replace_last_pet_message(self, text: str):
        """Replace the latest reply placeholder, preserving the public API."""
        for bubble in reversed(self._bubbles):
            if not bubble.is_user:
                bubble.update_text(text)
                self._scroll_to_bottom()
                return
        self.add_message(text, is_user=False)

    def clear_messages(self):
        for bubble in self._bubbles:
            self._layout.removeWidget(bubble)
            bubble.deleteLater()
        self._bubbles.clear()

    def _scroll_to_bottom(self):
        self._scroll_timer.start()

    def _apply_scroll(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())
