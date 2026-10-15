"""Offline Qt checks for choosing, resuming and deleting saved conversations."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from config import Config
from core import state_manager
from core.main_panel import MainPanel
from services.chat_history import load_sessions
from tests.test_chat_flow import DeferredChat
from ui.theme import apply_theme


class ChatSessionsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-session-ui-")
        self.addCleanup(self.temp.cleanup)
        self.state_file = Path(self.temp.name) / "state.json"
        self.workers = []
        self.panel = None
        for patcher in (
            patch.object(state_manager, "_STATE_FILE", str(self.state_file)),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch("core.main_panel.CLAUDE_CLI", "/missing/offline-test-claude"),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
            patch("socket.socket.connect", side_effect=AssertionError("No network in session tests")),
            patch("socket.create_connection", side_effect=AssertionError("No network in session tests")),
            patch("subprocess.Popen", side_effect=AssertionError("No real CLI in session tests")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        for name in ("ClaudeCliThread", "OpenAIChatThread", "AgentThread"):
            patcher = patch(f"core.main_panel.{name}", side_effect=self.worker_factory)
            patcher.start()
            self.addCleanup(patcher.stop)
        apply_theme(self.app, "light")
        self.addCleanup(self.close_panel)

    def worker_factory(self, *args):
        graph, request = (args if len(args) == 2 else (None, args[0]))
        worker = DeferredChat(request, graph)
        self.workers.append(worker)
        return worker

    def make_panel(self):
        self.panel = MainPanel(None)
        self.panel._decay_timer.stop()
        self.panel.show()
        self.app.processEvents()
        return self.panel

    def close_panel(self):
        for worker in self.workers:
            if not worker.completed:
                worker.finish()
        self.app.processEvents()
        if self.panel is not None:
            self.panel._storage_notice.poll_timer.stop()
            self.panel.close()
            self.panel.deleteLater()
            self.app.processEvents()
            self.panel = None

    def reopen_panel(self):
        self.close_panel()
        return self.make_panel()

    def send(self, text):
        self.panel.input_box.setText(text)
        self.panel.input_box.returnPressed.emit()
        return self.workers[-1]

    def reply(self, worker, text, success=True, *, finish=True):
        worker.reply_ready.emit(text, success)
        self.app.processEvents()
        if finish:
            worker.finish()
            self.app.processEvents()

    def complete(self, text, reply):
        worker = self.send(text)
        self.reply(worker, reply)
        return self.panel._current_session["id"]

    def select(self, session_id):
        index = self.panel.session_selector.findData(session_id)
        self.assertGreaterEqual(index, 0, f"Session {session_id} absent from selector")
        self.panel.session_selector.setCurrentIndex(index)
        self.app.processEvents()
        self.assertEqual(self.panel.session_selector.currentData(), session_id)
        self.assertEqual(self.panel._current_session["id"], session_id)

    def bubble_texts(self):
        return [bubble._label.text() for bubble in self.panel.chat_list._bubbles]

    def request_pairs(self, worker):
        return [(message.role, message.content) for message in worker.request.messages]

    def stored_ids(self):
        return {session["id"] for session in load_sessions()}

    def delete_current(self, confirm=True):
        with patch.object(self.panel, "_confirm_delete_session", return_value=confirm) as question:
            self.panel.delete_session_btn.click()
            self.app.processEvents()
        return question

    def test_same_title_choices_restore_only_their_own_context(self):
        self.make_panel()
        shared_title = "相同的会话标题" * 4
        first_question = shared_title + "：我叫小林"
        second_question = shared_title + "：我叫小周"
        first_id = self.complete(first_question, "你好，小林")
        self.panel._new_chat_session()
        second_id = self.complete(second_question, "你好，小周")
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len({session["title"] for session in load_sessions()}), 1)

        self.select(first_id)
        self.assertIn("你好，小林", self.bubble_texts())
        self.assertNotIn("你好，小周", self.bubble_texts())
        followup = self.send("我叫什么？")
        self.assertEqual(self.request_pairs(followup), [
            ("user", first_question), ("assistant", "你好，小林"), ("user", "我叫什么？")])
        self.reply(followup, "你叫小林")
        self.assertEqual(self.panel._current_session["id"], first_id)
        self.assertEqual(self.stored_ids(), {first_id, second_id})
        self.select(second_id)
        self.assertIn("你好，小周", self.bubble_texts())
        self.assertNotIn("你叫小林", self.bubble_texts())

    def test_selected_session_survives_restart_and_followup_keeps_its_id(self):
        self.make_panel()
        first_id = self.complete("第一场问题", "第一场回答")
        self.panel._new_chat_session()
        second_id = self.complete("第二场问题", "第二场回答")
        self.select(first_id)
        self.reopen_panel()
        self.assertEqual(self.panel.session_selector.currentData(), first_id)
        self.assertEqual(self.panel._current_session["id"], first_id)
        self.assertIn("第一场回答", self.bubble_texts())
        self.assertNotIn("第二场回答", self.bubble_texts())
        worker = self.send("接着聊第一场")
        self.assertEqual(self.request_pairs(worker), [
            ("user", "第一场问题"), ("assistant", "第一场回答"), ("user", "接着聊第一场")])
        self.reply(worker, "继续第一场")
        self.assertEqual(self.panel._current_session["id"], first_id)
        self.assertEqual(self.stored_ids(), {first_id, second_id})

    def test_switching_sessions_keeps_unsent_drafts_with_their_own_conversation(self):
        self.make_panel()
        first_id = self.complete("会话甲问题", "会话甲回答")
        self.panel.input_box.setText("会话甲未发送的草稿")
        self.panel._new_chat_session()
        self.assertEqual(self.panel.input_box.text(), "")
        second_id = self.complete("会话乙问题", "会话乙回答")
        self.panel.input_box.setText("会话乙未发送的草稿")
        self.select(first_id)
        self.assertEqual(self.panel.input_box.text(), "会话甲未发送的草稿")
        self.select(second_id)
        self.assertEqual(self.panel.input_box.text(), "会话乙未发送的草稿")
        self.assertFalse(any("未发送的草稿" in str(session) for session in load_sessions()))

    def test_restored_welcome_and_failed_reply_remain_visible_but_not_context(self):
        self.make_panel()
        welcome = self.bubble_texts()[0]
        failed = self.send("请记住我是小林")
        self.reply(failed, "离线模拟连接失败", success=False)
        session_id = self.panel._current_session["id"]
        self.panel._new_chat_session()
        self.select(session_id)
        self.reopen_panel()
        self.assertIn(welcome, self.bubble_texts())
        self.assertIn("离线模拟连接失败", self.bubble_texts())
        display_only = [message for message in self.panel._chat_history
                        if message["content"] in (welcome, "离线模拟连接失败")]
        self.assertEqual(len(display_only), 2)
        self.assertTrue(all(message["include_in_context"] is False for message in display_only))
        followup = self.send("再试一次")
        self.assertEqual(self.request_pairs(followup), [
            ("user", "请记住我是小林"), ("user", "再试一次")])

    def test_cancel_delete_keeps_file_transcript_selection_and_input(self):
        self.make_panel()
        session_id = self.complete("保留这一场", "原来的回答")
        self.panel.input_box.setText("还没发送的草稿")
        before = self.state_file.read_bytes()
        history = deepcopy(self.panel._chat_history)
        bubbles = self.bubble_texts()
        question = self.delete_current(False)
        question.assert_called_once()
        self.assertEqual(question.call_args.args[0]["id"], session_id)
        self.assertEqual(self.state_file.read_bytes(), before)
        self.assertEqual(self.panel._chat_history, history)
        self.assertEqual(self.bubble_texts(), bubbles)
        self.assertEqual(self.panel.session_selector.currentData(), session_id)
        self.assertEqual(self.panel.input_box.text(), "还没发送的草稿")

    def test_delete_current_keeps_other_session_and_restart_does_not_restore_deleted_text(self):
        self.make_panel()
        survivor = self.complete("保留另一场", "保留另一场回答")
        self.panel._new_chat_session()
        deleted = self.complete("删除本场问题", "删除本场回答")
        self.delete_current()
        self.assertEqual(self.stored_ids(), {survivor})
        self.assertNotIn("删除本场回答", self.bubble_texts())
        self.assertNotEqual(self.panel.session_selector.currentData(), deleted)
        self.reopen_panel()
        self.assertEqual(self.stored_ids(), {survivor})
        self.assertNotIn("删除本场回答", self.bubble_texts())
        self.assertNotIn("删除本场问题", str(self.panel._chat_history))
        self.select(survivor)
        self.assertIn("保留另一场回答", self.bubble_texts())

    def test_delete_last_session_leaves_empty_history_and_disabled_delete_after_restart(self):
        self.make_panel()
        self.complete("最后一场问题", "最后一场回答")
        self.delete_current()
        self.assertFalse(self.stored_ids())
        self.assertIsNone(self.panel.session_selector.currentData())
        self.assertFalse(self.panel.delete_session_btn.isEnabled())
        self.reopen_panel()
        self.assertFalse(self.stored_ids())
        self.assertIsNone(self.panel.session_selector.currentData())
        self.assertFalse(self.panel.delete_session_btn.isEnabled())
        self.assertNotIn("最后一场回答", self.bubble_texts())
        self.assertNotIn("最后一场问题", str(self.panel._chat_history))

    def test_switch_away_and_back_rejects_old_reply_before_accessing_deleted_placeholder(self):
        self.make_panel()
        old = self.send("会话甲尚未完成的问题")
        first_id = self.panel._current_session["id"]
        self.panel._new_chat_session()
        second_id = self.complete("会话乙问题", "会话乙回答")
        self.select(first_id)
        before = self.state_file.read_bytes()
        history = deepcopy(self.panel._chat_history)
        self.reply(old, "会话甲已经过期的回复", finish=False)
        self.assertNotIn("会话甲已经过期的回复", self.bubble_texts())
        self.assertEqual(self.panel._chat_history, history)
        self.assertEqual(self.state_file.read_bytes(), before)
        self.assertIn(old, self.panel._chat_threads)
        self.assertEqual(self.stored_ids(), {first_id, second_id})
        old.finish()
        self.app.processEvents()
        self.assertNotIn(old, self.panel._chat_threads)

    def test_deleted_inflight_conversation_cannot_be_resurrected_by_late_reply(self):
        self.make_panel()
        old = self.send("即将删除的在途问题")
        old_id = self.panel._current_session["id"]
        self.delete_current()
        self.assertNotIn(old_id, self.stored_ids())
        before = self.state_file.read_bytes()
        self.reply(old, "删除后到达的回复", finish=False)
        self.assertEqual(self.state_file.read_bytes(), before)
        self.assertNotIn("删除后到达的回复", self.bubble_texts())
        self.assertNotIn(old_id, self.stored_ids())
        self.assertIn(old, self.panel._chat_threads)
        old.finish()
        self.app.processEvents()
        self.reopen_panel()
        self.assertNotIn(old_id, self.stored_ids())
        self.assertNotIn("即将删除的在途问题", str(self.panel._chat_history))
        self.assertNotIn("删除后到达的回复", self.bubble_texts())

    def test_empty_new_conversations_do_not_accumulate_saved_sessions(self):
        self.make_panel()
        for _ in range(3):
            self.panel._new_chat_session()
            self.app.processEvents()
            self.assertFalse(self.stored_ids())
            self.assertIsNone(self.panel.session_selector.currentData())
            self.assertFalse(self.panel.delete_session_btn.isEnabled())
        self.reopen_panel()
        self.assertFalse(self.stored_ids())
        self.assertFalse(self.panel.delete_session_btn.isEnabled())

    def test_failed_delete_stays_pending_until_retry_without_losing_unrelated_state(self):
        self.make_panel()
        session_id = self.complete("删除需要重试", "待删除的回复")
        self.assertTrue(state_manager.save_field("session_test_unrelated", {"keep": "保留"}))
        before = self.state_file.read_bytes()
        with patch("core.state_manager.os.replace", side_effect=OSError("模拟磁盘空间不足")):
            self.delete_current()
            self.panel._storage_notice.refresh()
            self.assertEqual(self.state_file.read_bytes(), before)
            self.assertNotIn(session_id, self.stored_ids())
            self.assertIn("chat_sessions", state_manager.get_storage_status().pending_fields)
            self.assertTrue(self.panel._storage_notice.isVisible())
            self.assertNotIn("待删除的回复", self.bubble_texts())
        self.assertTrue(state_manager.retry_pending_saves())
        stored = json.loads(self.state_file.read_text())
        self.assertFalse(stored["chat_sessions"])
        self.assertEqual(stored["session_test_unrelated"], {"keep": "保留"})
        self.assertFalse(state_manager.get_storage_status().pending_fields)
        self.reopen_panel()
        self.assertNotIn("待删除的回复", self.bubble_texts())
        self.assertFalse(self.stored_ids())

    def test_confirmation_uses_plain_text_and_defaults_to_cancel(self):
        self.make_panel()
        self.complete("<b>原样标题</b> 要保留", "回答")
        expected_title = self.panel._current_session["title"]
        before = self.state_file.read_bytes()
        observations = {}
        errors = []

        def inspect_and_cancel():
            dialog = self.app.activeModalWidget()
            try:
                self.assertIsInstance(dialog, QMessageBox)
                observations["text"] = dialog.text()
                observations["format"] = dialog.textFormat()
                observations["default"] = dialog.standardButton(dialog.defaultButton())
                observations["escape"] = dialog.standardButton(dialog.escapeButton())
                QTest.mouseClick(dialog.button(QMessageBox.StandardButton.Cancel), Qt.MouseButton.LeftButton)
            except BaseException as error:
                errors.append(error)
                if dialog is not None:
                    dialog.reject()

        QTimer.singleShot(0, inspect_and_cancel)
        self.panel.delete_session_btn.click()
        self.app.processEvents()
        if errors:
            raise errors[0]
        # macOS does not expose QMessageBox titles consistently; inspect the
        # actual confirmation body and safe defaults instead.
        self.assertIn(expected_title, observations["text"])
        self.assertIn("不可恢复", observations["text"])
        self.assertEqual(observations["format"], Qt.TextFormat.PlainText)
        self.assertEqual(observations["default"], QMessageBox.StandardButton.Cancel)
        self.assertEqual(observations["escape"], QMessageBox.StandardButton.Cancel)
        self.assertEqual(self.state_file.read_bytes(), before)

    def test_long_title_and_minimum_window_keep_session_actions_visible_in_both_themes(self):
        self.make_panel()
        session_id = self.complete("长标题布局验收", "布局验收回答")
        self.panel._current_session["title"] = "<b>原样的长标题</b> " + "中文内容" * 80
        self.panel._save_current_session("布局验收回答")
        for mode in ("light", "dark"):
            apply_theme(self.app, mode)
            self.panel.resize(860, 660)
            self.app.processEvents()
            self.app.processEvents()
            self.assertEqual((self.panel.width(), self.panel.height()), (860, 660))
            self.assertEqual(self.panel.session_selector.currentData(), session_id)
            self.assertEqual(self.panel._session_info.textFormat(), Qt.TextFormat.PlainText)
            for control in (self.panel.session_selector, self.panel.delete_session_btn, self.panel.input_box):
                self.assertTrue(control.isVisible())
                for corner in (control.rect().topLeft(), control.rect().bottomRight()):
                    self.assertTrue(self.panel.rect().contains(control.mapTo(self.panel, corner)))
                self.assertGreater(control.width(), 20)
            self.assertEqual(self.panel.chat_list.horizontalScrollBar().maximum(), 0)
            self.assertFalse(self.panel.grab().isNull())


if __name__ == "__main__":
    unittest.main()
