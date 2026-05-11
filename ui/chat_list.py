from PyQt6.QtWidgets import QTextBrowser
from PyQt6.QtCore import Qt


class ChatList(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setStyleSheet("""
            QTextBrowser {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
        """)

    def add_message(self, message: str, is_user: bool = False):
        if is_user:
            formatted = f'<div style="text-align: right; color: #007AFF; margin: 10px 0;"><b>你:</b> {message}</div>'
        else:
            formatted = f'<div style="text-align: left; color: #333; margin: 10px 0; white-space: pre-wrap;"><b>边牧:</b> {message}</div>'

        self.append(formatted)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_messages(self):
        self.clear()
