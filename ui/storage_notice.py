"""Persistent, main-thread feedback for local storage problems."""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from core import state_manager


FIELD_LABELS = {
    "chat_history": "聊天记录",
    "chat_sessions": "聊天会话",
    "notes": "便签与日记",
    "settings": "设置",
    "theme": "主题",
    "pet_stats": "宠物状态",
    "timer": "倒计时",
    "news_cache": "新闻缓存",
    "window_position": "窗口位置",
    "last_seen": "离开时间",
}


class StorageNotice(QFrame):
    """Poll storage snapshots without performing I/O or touching worker widgets."""

    attention_required = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, objectName="storage_notice")
        self._last_status = None
        self._had_issue = False
        self.hide()

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 12, 18, 12)
        row.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(4)
        self.title_label = QLabel(objectName="storage_notice_title")
        self.message_label = QLabel(objectName="storage_notice_message")
        for label in (self.title_label, self.message_label):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
        text.addWidget(self.title_label)
        text.addWidget(self.message_label)
        row.addLayout(text, 1)

        actions = QVBoxLayout()
        actions.setSpacing(6)
        self.retry_button = QPushButton("重试保存", objectName="secondary_btn")
        self.retry_button.clicked.connect(self._retry)
        self.details_button = QPushButton("查看详情", objectName="secondary_btn")
        self.details_button.clicked.connect(self._show_details)
        actions.addWidget(self.retry_button)
        actions.addWidget(self.details_button)
        row.addLayout(actions)

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(300)
        self.poll_timer.timeout.connect(self.refresh)
        self.poll_timer.start()

    def refresh(self):
        status = state_manager.get_storage_status()
        has_issue = bool(status.pending_fields or status.error or status.recovery_backup)
        if status != self._last_status:
            self._last_status = status
            if status.pending_fields:
                labels = [FIELD_LABELS.get(field, field) for field in status.pending_fields]
                self.title_label.setText("尚未保存：" + "、".join(labels))
                message = "修改仅保留在当前会话，退出会丢失。请重试保存。"
                if status.recovery_backup:
                    message += " 另有损坏数据备份，请查看详情。"
            elif status.error:
                self.title_label.setText("本地数据暂时无法保存")
                message = "请查看文件位置与错误详情，处理后重试。"
            else:
                self.title_label.setText("已保留损坏数据的备份")
                if status.recovered_from_memory:
                    message = "继续使用本次会话中最后读到的数据。请查看备份信息并确认。"
                else:
                    message = "原内容未恢复，应用已从空状态继续。请查看备份位置并确认。"
            self.message_label.setText(message)
            self.retry_button.setVisible(bool(status.pending_fields or status.error))
            self.setVisible(has_issue)
        if has_issue and not self._had_issue:
            self._had_issue = True
            self.attention_required.emit()
        elif not has_issue:
            self._had_issue = False

    def _retry(self):
        self.retry_button.setEnabled(False)
        try:
            state_manager.retry_pending_saves()
        finally:
            self.retry_button.setEnabled(True)
            self.refresh()

    def _show_details(self):
        status = state_manager.get_storage_status()
        dialog = QDialog(self)
        dialog.setWindowTitle("本地数据状态")
        dialog.resize(580, 360)
        layout = QVBoxLayout(dialog)
        details = [f"保存位置：\n{status.path}"]
        if status.pending_fields:
            fields = "、".join(FIELD_LABELS.get(field, field) for field in status.pending_fields)
            details.append(f"尚未保存：{fields}\n修改仅保留在当前会话，退出会丢失。")
        if status.error:
            details.append(f"错误：\n{status.error}")
        if status.recovery_backup:
            recovery = ("已保留本次会话中最后读到的数据，损坏文件中的其他内容未恢复。"
                        if status.recovered_from_memory else "原内容未恢复，应用从空状态继续。")
            details.append(
                f"损坏文件的原始备份：\n{status.recovery_backup}\n"
                f"{recovery}\n"
                "此备份不会因确认提示而删除。如需恢复，请先退出应用并保留现有文件。"
            )
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n\n".join(details))
        layout.addWidget(text, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        if status.recovery_backup:
            acknowledge = buttons.addButton("我已查看备份信息", QDialogButtonBox.ButtonRole.AcceptRole)
            acknowledge.clicked.connect(lambda: self._acknowledge_recovery(dialog))
        layout.addWidget(buttons)
        dialog.exec()

    def _acknowledge_recovery(self, dialog):
        state_manager.acknowledge_recovery()
        self.refresh()
        dialog.accept()
