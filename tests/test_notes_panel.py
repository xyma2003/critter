"""Exercise note buttons and modal editors against isolated offscreen storage."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QLabel, QLineEdit, QPushButton, QTextEdit,
)

from config import Config
from core import state_manager
from core.main_panel import MainPanel
from services import notes
from ui.theme import apply_theme


class NotesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-notes-panel-")
        self.addCleanup(self.temp.cleanup)
        for patcher in (
            patch.object(state_manager, "_STATE_FILE", str(Path(self.temp.name) / "state.json")),
            patch("core.main_panel.CLAUDE_CLI", "/missing/critter-test-claude"),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
            patch("socket.socket.connect", side_effect=AssertionError("No network in note tests")),
            patch("socket.create_connection", side_effect=AssertionError("No network in note tests")),
            patch("subprocess.Popen", side_effect=AssertionError("No model CLI in note tests")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        apply_theme(self.app, "light")
        self.panel = MainPanel(None)
        self.panel._decay_timer.stop()
        self.panel.show()
        self.panel._switch_tab(3)
        self.app.processEvents()
        self.addCleanup(self.close_panel)

    def close_panel(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def _card(self, title):
        # Walk the active layout, excluding old cards awaiting deleteLater().
        layout = self.panel._notes_list_layout
        for index in range(layout.count() - 1):
            card = layout.itemAt(index).widget()
            if any(label.text() == title for label in card.findChildren(QLabel)):
                return card
        self.fail(f"No visible card for {title!r}")

    def _button(self, parent, text):
        return next(button for button in parent.findChildren(QPushButton) if button.text() == text)

    def _save_editor(self, button, title, content, expected_content=""):
        failures = []

        def fill_modal():
            dialog = self.app.activeModalWidget()
            try:
                self.assertIsInstance(dialog, QDialog)
                editor = dialog.findChild(QTextEdit)
                self.assertEqual(editor.toPlainText(), expected_content)
                dialog.findChild(QLineEdit).setText(title)
                editor.setPlainText(content)
                save = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save)
                QTest.mouseClick(save, Qt.MouseButton.LeftButton)
            except BaseException as error:
                # Never let an assertion escape a Qt callback and abort Python.
                failures.append(error)
                if isinstance(dialog, QDialog):
                    dialog.reject()

        QTimer.singleShot(0, fill_modal)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        if failures:
            raise failures[0]

    def test_same_second_notes_and_diary_edit_delete_only_the_selected_card(self):
        new_button = self._button(self.panel._stack.widget(3), "+ 新建")
        with patch("services.notes.time.time", return_value=1700000000):
            self._save_editor(new_button, "第一条", "保留第一条内容")
            self._save_editor(new_button, "第二条", "第二条原内容")
            diary = notes.create_diary("保留日记内容", "2026-10-13")
            self.panel._refresh_notes_list()
            self.app.processEvents()
            original = notes.load_all()
            self.assertEqual(len({note["id"] for note in original}), 3)
            self.assertEqual({note["updated"] for note in original}, {1700000000})

            self._save_editor(self._button(self._card("第二条"), "编辑"),
                              "第二条已编辑", "只改第二条", "第二条原内容")
            edited = notes.load_all()
            self.assertEqual(edited[0], original[0])
            self.assertEqual(edited[1]["id"], original[1]["id"])
            self.assertEqual(edited[1]["content"], "只改第二条")
            self.assertEqual(edited[2], diary)

            QTest.mouseClick(self._button(self._card("第二条已编辑"), "删除"), Qt.MouseButton.LeftButton)
            self.app.processEvents()
            self.assertEqual(notes.load_all(), [original[0], diary])

    def test_legacy_duplicate_cards_get_independent_edit_and_delete_actions(self):
        legacy = [
            {"id": 123, "title": "旧第一条", "content": "第一条不变", "updated": 123},
            {"id": 123, "title": "旧第二条", "content": "第二条原文", "updated": 123},
            {"id": 456, "content": "旧日记不变", "kind": "diary", "date": "2026-10-12", "updated": 456},
        ]
        self.assertTrue(state_manager.save_notes(legacy))
        self.panel._refresh_notes_list()
        self.app.processEvents()
        repaired = notes.load_all()
        self.assertNotEqual(repaired[0]["id"], repaired[1]["id"])
        self.assertTrue(all(note["id"] != 123 for note in repaired))
        self.assertEqual(repaired[2], legacy[2])

        # The diary is first on screen, then the second old note, then the first.
        second_card = self.panel._notes_list_layout.itemAt(1).widget()
        self._save_editor(self._button(second_card, "编辑"),
                          "旧第二条已改", "仅修改第二条", "第二条原文")
        edited = notes.load_all()
        self.assertEqual(edited[0], repaired[0])
        self.assertEqual(edited[1]["content"], "仅修改第二条")
        self.assertEqual(edited[2], repaired[2])
        QTest.mouseClick(self._button(self._card("旧第二条已改"), "删除"), Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertEqual(notes.load_all(), [repaired[0], repaired[2]])

    def test_stale_duplicate_id_does_not_open_a_new_note_dialog(self):
        self.assertTrue(state_manager.save_notes([
            {"id": 999, "title": "甲", "content": "保留甲", "updated": 999},
            {"id": 999, "title": "乙", "content": "保留乙", "updated": 999},
        ]))
        with patch("PyQt6.QtWidgets.QDialog.exec") as dialog_exec:
            self.panel._open_note_editor(999)
        dialog_exec.assert_not_called()
        repaired = notes.load_all()
        self.assertEqual([note["content"] for note in repaired], ["保留甲", "保留乙"])
        self.assertEqual(len({note["id"] for note in repaired}), 2)
        self.assertTrue(all(note["id"] != 999 for note in repaired))
        self.assertIsNotNone(self._card("甲"))
        self.assertIsNotNone(self._card("乙"))


if __name__ == "__main__":
    unittest.main()
