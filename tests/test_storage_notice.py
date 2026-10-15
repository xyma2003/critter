"""Offline Qt acceptance checks for persistent storage feedback."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import tempfile
import threading
import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PyQt6.QtCore import QThread, QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QDialogButtonBox, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QTextEdit,
)

from config import Config
from core.main_panel import MainPanel
from core import state_manager
from ui.theme import apply_theme


class StorageNoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-storage-ui-")
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "数据 <测试>" / "state.json")
        self.status = self.snapshot()
        self.panel = None
        self.api_patchers = []
        for patcher in (
            patch("core.state_manager._STATE_FILE", self.path),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch("core.main_panel.CLAUDE_CLI", "/missing/critter-test-cli"),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.status_mock = self.start_patch(
            "get_storage_status", side_effect=lambda: self.status)
        self.retry_mock = self.start_patch("retry_pending_saves", return_value=False)
        self.acknowledge_mock = self.start_patch("acknowledge_recovery")
        apply_theme(self.app, "light")
        self.addCleanup(self.close_panel)

    def start_patch(self, name, **kwargs):
        patcher = patch(f"ui.storage_notice.state_manager.{name}", create=True, **kwargs)
        mock = patcher.start()
        self.api_patchers.append(patcher)
        self.addCleanup(patcher.stop)
        return mock

    def snapshot(self, pending=(), error=None, backup=None):
        return SimpleNamespace(
            path=self.path, pending_fields=pending, error=error, recovery_backup=backup,
            recovered_from_memory=False)

    def make_panel(self):
        self.panel = MainPanel(None)
        self.panel._decay_timer.stop()
        self.app.processEvents()
        return self.panel._storage_notice

    def close_panel(self):
        if self.panel:
            self.panel._storage_notice.poll_timer.stop()
            self.panel.close()
            self.panel.deleteLater()
            self.app.processEvents()

    def test_initial_unsaved_data_opens_panel_and_names_affected_data(self):
        self.status = self.snapshot(("notes", "settings", "chat_history"), "permission denied")
        notice = self.make_panel()
        self.assertTrue(self.panel.isVisible())
        self.assertTrue(notice.isVisible())
        self.assertIn("便签与日记", notice.title_label.text())
        self.assertIn("设置", notice.title_label.text())
        self.assertIn("聊天记录", notice.title_label.text())
        self.assertIn("退出会丢失", notice.message_label.text())
        self.assertEqual(notice.title_label.textFormat(), Qt.TextFormat.PlainText)

    def test_worker_state_is_displayed_by_gui_poll_without_automatic_retry(self):
        notice = self.make_panel()
        self.assertFalse(self.panel.isVisible())
        threads = []
        set_text = notice.title_label.setText

        def track_set_text(value):
            threads.append(QThread.currentThread())
            set_text(value)

        worker = threading.Thread(target=lambda: setattr(
            self, "status", self.snapshot(("news_cache",), "disk full")))
        worker.start()
        worker.join()
        with patch.object(notice.title_label, "setText", side_effect=track_set_text):
            QTest.qWait(360)
        self.assertTrue(self.panel.isVisible())
        self.assertIn("新闻缓存", notice.title_label.text())
        self.assertTrue(threads)
        self.assertTrue(all(thread == self.app.thread() for thread in threads))
        self.retry_mock.assert_not_called()
        self.acknowledge_mock.assert_not_called()

    def test_retry_keeps_warning_until_all_pending_data_is_saved(self):
        self.status = self.snapshot(("notes", "settings"), "disk full")
        notice = self.make_panel()
        notice.retry_button.click()
        self.assertTrue(notice.isVisible())
        self.assertTrue(notice.retry_button.isEnabled())

        def save_all():
            self.status = self.snapshot()
            return True

        self.retry_mock.side_effect = save_all
        notice.retry_button.click()
        self.assertFalse(notice.isVisible())
        self.assertEqual(self.retry_mock.call_count, 2)

    def inspect_details(self, notice, confirm=False):
        observed = {}

        def inspect():
            dialog = self.app.activeModalWidget()
            try:
                observed["text"] = dialog.findChild(QPlainTextEdit).toPlainText()
                if confirm:
                    button = next(button for button in dialog.findChildren(QPushButton)
                                  if button.text() == "我已查看备份信息")
                    button.click()
                else:
                    dialog.reject()
            except Exception as error:
                observed["error"] = error
                if dialog:
                    dialog.reject()

        QTimer.singleShot(0, inspect)
        notice.details_button.click()
        self.assertNotIn("error", observed)
        return observed["text"]

    def test_backup_notice_requires_confirmation_and_details_are_plain_text(self):
        backup = self.path + ".corrupt-20261010.bak"
        self.status = self.snapshot(backup=backup)
        notice = self.make_panel()
        self.assertFalse(notice.retry_button.isVisible())
        details = self.inspect_details(notice)
        self.assertIn(self.path, details)
        self.assertIn(backup, details)
        self.acknowledge_mock.assert_not_called()
        self.assertTrue(notice.isVisible())

        self.acknowledge_mock.side_effect = lambda: setattr(self, "status", self.snapshot())
        self.inspect_details(notice, confirm=True)
        self.acknowledge_mock.assert_called_once_with()
        self.assertFalse(notice.isVisible())

    def test_error_details_and_pending_data_survive_backup_acknowledgement(self):
        self.status = self.snapshot(("notes",), "<filesystem error>", self.path + ".bak")
        notice = self.make_panel()
        self.acknowledge_mock.side_effect = lambda: setattr(
            self, "status", self.snapshot(("notes",), "<filesystem error>"))
        details = self.inspect_details(notice, confirm=True)
        self.assertIn("<filesystem error>", details)
        self.assertTrue(notice.isVisible())
        self.assertIn("尚未保存", notice.title_label.text())

    def test_minimum_window_keeps_settings_accessible_with_long_notice(self):
        self.status = self.snapshot((
            "chat_history", "chat_sessions", "notes", "settings", "theme",
            "pet_stats", "timer", "news_cache", "window_position", "last_seen",
        ), "disk full")
        notice = self.make_panel()
        self.panel._switch_tab(6)
        self.panel.resize(860, 660)
        for mode in ("light", "dark"):
            apply_theme(self.app, mode)
            self.app.processEvents()
            self.assertEqual((self.panel.width(), self.panel.height()), (860, 660))
            self.assertLessEqual(notice.height(), 180)
            scroll = self.panel._settings_scroll
            self.assertGreater(scroll.viewport().height(), 250)
            scroll.ensureWidgetVisible(self.panel._data_path_label)
            self.app.processEvents()
            point = self.panel._data_path_label.mapTo(scroll.viewport(),
                                                     self.panel._data_path_label.rect().center())
            self.assertTrue(scroll.viewport().rect().contains(point))
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)

    def use_real_storage_api(self):
        for patcher in self.api_patchers:
            patcher.stop()

    def test_actual_failed_writes_keep_note_settings_and_chat_until_ui_retry(self):
        self.use_real_storage_api()
        self.assertTrue(state_manager.initialize_storage())
        notice = self.make_panel()
        original = Path(self.path).read_bytes()
        editor_errors = []

        def fill_note():
            dialog = self.app.activeModalWidget()
            try:
                dialog.findChild(QLineEdit).setText("未保存的便签")
                dialog.findChild(QTextEdit).setPlainText("保留这段草稿，修好存储后再保存。")
                dialog.findChild(QDialogButtonBox).button(
                    QDialogButtonBox.StandardButton.Save).click()
            except Exception as error:
                editor_errors.append(error)
                if dialog:
                    dialog.reject()

        with patch("core.state_manager.os.replace", side_effect=OSError("模拟磁盘空间不足")):
            QTimer.singleShot(0, fill_note)
            self.panel._new_note()
            self.assertFalse(editor_errors)
            self.panel._pet_name_input.setText("保存后的小伙伴")
            self.panel._save_settings()
            self.panel._record_message("待保存的聊天消息", "user")
            self.panel._save_current_session("待保存的聊天消息")
            QTest.qWait(360)
            self.assertTrue(notice.isVisible())
            self.assertTrue(self.panel.isVisible())
            self.assertEqual(set(state_manager.get_storage_status().pending_fields),
                             {"notes", "settings", "chat_history", "chat_sessions", "active_chat_session_id"})
            self.assertTrue(any(label.text() == "未保存的便签"
                                for label in self.panel._notes_list_widget.findChildren(QLabel)))
            self.assertEqual(self.panel._identity_name.text(), "保存后的小伙伴")
            self.assertEqual(Path(self.path).read_bytes(), original)
            notice.retry_button.click()
            self.assertTrue(notice.isVisible())

        notice.retry_button.click()
        self.assertFalse(notice.isVisible())
        self.assertFalse(state_manager.get_storage_status().pending_fields)
        saved = json.loads(Path(self.path).read_text(encoding="utf-8"))
        self.assertEqual(saved["notes"][0]["title"], "未保存的便签")
        self.assertEqual(saved["settings"]["pet_name"], "保存后的小伙伴")
        self.assertEqual(saved["chat_history"][-1]["content"], "待保存的聊天消息")
        self.assertEqual(saved["chat_sessions"][0]["messages"][-1]["content"], "待保存的聊天消息")
        self.assertEqual(saved["active_chat_session_id"], saved["chat_sessions"][0]["id"])

    def test_actual_corrupt_backup_stays_on_disk_after_explicit_confirmation(self):
        self.use_real_storage_api()
        Path(self.path).parent.mkdir(parents=True)
        damaged = b'{"notes": [broken'
        Path(self.path).write_bytes(damaged)
        self.assertTrue(state_manager.initialize_storage())
        backup = Path(state_manager.get_storage_status().recovery_backup)
        notice = self.make_panel()
        self.assertTrue(notice.isVisible())
        self.assertIn("原内容未恢复", notice.message_label.text())
        self.inspect_details(notice, confirm=True)
        self.assertFalse(notice.isVisible())
        self.assertEqual(backup.read_bytes(), damaged)
        self.assertIsNone(state_manager.get_storage_status().recovery_backup)


if __name__ == "__main__":
    unittest.main()
