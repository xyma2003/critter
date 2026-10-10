"""Offline component checks. Render only an isolated Qt offscreen surface."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import Qt, qInstallMessageHandler
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

from config import Config
from core.main_panel import MainPanel
from ui.theme import apply_theme, current


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-panel-test-")
        self.addCleanup(self.temp.cleanup)
        for patcher in (
            patch("core.state_manager._STATE_FILE", str(Path(self.temp.name) / "state.json")),
            patch("core.main_panel.CLAUDE_CLI", "/missing/critter-test-claude"),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.qt_messages = []
        previous = qInstallMessageHandler(lambda _kind, _context, message: self.qt_messages.append(message))
        self.addCleanup(qInstallMessageHandler, previous)
        apply_theme(self.app, "light")
        self.panel = MainPanel(None)
        self.panel._decay_timer.stop()
        self.panel.show()
        self.app.processEvents()
        self.addCleanup(self.close_panel)

    def close_panel(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def test_offline_pages_render_at_minimum_size_without_zero_font_warning(self):
        self.panel.resize(860, 660)
        for idx in range(7):
            self.panel._switch_tab(idx)
            self.app.processEvents()
            self.assertEqual(self.panel._stack.currentIndex(), idx)
            self.assertFalse(self.panel.grab().isNull())
        self.assertFalse(any("Pixel size <= 0" in m for m in self.qt_messages), self.qt_messages)
        self.assertEqual((self.panel.width(), self.panel.height()), (860, 660))

    def test_configuration_summary_is_not_a_connection_claim_or_secret(self):
        chat, agent = self.panel._configuration_summary()
        self.assertIn("尚未配置", chat)
        self.assertIn("未启用", agent)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret-never-show"}):
            self.panel.agent_graph = object()
            chat, agent = self.panel._configuration_summary()
            self.assertIn("尚未测试", chat)
            self.assertIn("尚未测试", agent)
            self.assertNotIn("test-secret", chat + agent)
        with patch("core.main_panel.os.path.isfile", return_value=True), patch("core.main_panel.os.access", return_value=True):
            self.assertIn("登录状态尚未验证", self.panel._configuration_summary()[0])

    def test_settings_displays_active_state_file_for_backup(self):
        self.panel._switch_tab(6)
        self.panel.resize(860, 660)
        self.app.processEvents()
        label = self.panel._data_path_label
        self.assertIn(str(Path(self.temp.name) / "state.json"), label.text())
        self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)
        self.assertTrue(label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse)
        self.assertLessEqual(label.geometry().bottom(), label.parentWidget().height())

    def test_existing_and_new_bubbles_follow_both_themes_and_keep_plain_text(self):
        original = self.panel.chat_list.add_message("<b>按原文显示</b>")
        for mode in ("dark", "light"):
            self.panel._apply_theme(mode)
            new = self.panel.chat_list.add_message("新的测试消息")
            user = self.panel.chat_list.add_message("这是一条用户消息", is_user=True)
            self.app.processEvents()
            for bubble, color in ((original, "text_pet"), (new, "text_pet"), (user, "text_user")):
                self.assertEqual(bubble._label.textFormat(), Qt.TextFormat.PlainText)
                self.assertEqual(bubble._label.palette().color(QPalette.ColorRole.WindowText).name(), current()[color].lower())
            self.assertTrue(self.panel._theme_buttons[mode].isChecked())

    def test_long_messages_fit_when_window_is_narrowed(self):
        bubble = self.panel.chat_list.add_message("很长的中文消息需要换行。" * 30 + "verylongword" * 25)
        for width in (1100, 860, 1000):
            self.panel.resize(width, 760)
            self.app.processEvents()
            self.app.processEvents()
            self.assertLessEqual(bubble._label.width(), bubble.width())
            self.assertEqual(self.panel.chat_list.horizontalScrollBar().maximum(), 0)
            self.assertGreater(bubble._label.height(), 35)

    def test_chat_completion_refreshes_pet_status(self):
        for callback in (self.panel._on_cli_done, self.panel._on_agent_done):
            self.panel._identity_mood.setText("outdated")
            callback("静态测试回复，不调用模型")
            self.assertEqual(self.panel._identity_mood.text(), self.panel.stats.mood_label())


if __name__ == "__main__":
    unittest.main()
