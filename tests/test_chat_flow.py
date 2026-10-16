"""Offline adapter and Qt conversation tests; never invoke a model or CLI."""

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QPushButton
from langchain_core.messages import AIMessage, HumanMessage

from config import Config
from core.main_panel import AgentThread, ClaudeCliThread, MainPanel, OpenAIChatThread
from services.chat_context import MAX_CONTEXT_CHARS, api_messages, build_chat_request


class DeferredChat(QObject):
    """A controllable worker with distinct result and lifecycle signals."""

    reply_ready = pyqtSignal(str, bool)
    finished = pyqtSignal()

    def __init__(self, request, graph=None):
        super().__init__()
        self.request = request
        self.graph = graph
        self.started = False
        self.completed = False

    def start(self):
        self.started = True

    def finish(self):
        self.completed = True
        self.finished.emit()


class ChatFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-chat-flow-")
        self.addCleanup(self.temp.cleanup)
        self.state_file = Path(self.temp.name) / "state.json"
        self.workers = []
        self.panel = None
        for patcher in (
            patch("core.state_manager._STATE_FILE", str(self.state_file)),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch("core.main_panel.CLAUDE_CLI", "/missing/offline-test-claude"),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in chat test")),
            patch("socket.create_connection", side_effect=AssertionError("Network forbidden in chat test")),
            patch("core.main_panel.subprocess.Popen", side_effect=AssertionError("Real CLI forbidden in chat test")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.close_panel)
        self.request = build_chat_request(
            [{"role": "user", "content": "我叫小林"},
             {"role": "pet", "content": "小林，你好"},
             {"role": "user", "content": "我叫什么？"}],
            {"pet_name": "团团", "pet_personality": "耐心", "pet_catchphrase": "慢慢来"},
        )

    def close_panel(self):
        for worker in self.workers:
            if not worker.completed:
                worker.finish()
        self.app.processEvents()
        if self.panel is not None:
            self.panel.close()
            self.panel.deleteLater()
            self.app.processEvents()

    def make_panel(self):
        self.panel = MainPanel(None)
        self.panel._decay_timer.stop()
        return self.panel

    def worker_factory(self, *args):
        graph, request = (args if len(args) == 2 else (None, args[0]))
        worker = DeferredChat(request, graph)
        self.workers.append(worker)
        return worker

    def mock_workers(self):
        for name in ("ClaudeCliThread", "OpenAIChatThread", "AgentThread"):
            patcher = patch(f"core.main_panel.{name}", side_effect=self.worker_factory)
            patcher.start()
            self.addCleanup(patcher.stop)

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

    def pairs(self, request):
        return [(message.role, message.content) for message in request.messages]

    def bubble_texts(self):
        return [bubble._label.text() for bubble in self.panel.chat_list._bubbles]

    def test_cli_receives_persona_in_argv_and_exact_transcript_via_stdin(self):
        process = Mock(returncode=0)
        process.communicate.return_value = ("  你叫小林。\n", "")
        worker = ClaudeCliThread(self.request)
        replies = []
        worker.reply_ready.connect(lambda *args: replies.append(args))
        with patch("core.main_panel.subprocess.Popen", return_value=process) as popen:
            worker.run()
        command = popen.call_args.args[0]
        system = command[command.index("--system-prompt") + 1]
        self.assertIn(self.request.system, system)
        self.assertIn("耐心", system)
        self.assertIn("--no-session-persistence", command)
        self.assertNotIn("--resume", command)
        self.assertNotIn("--continue", command)
        self.assertNotIn("我叫什么？", command)
        self.assertIsNotNone(popen.call_args.kwargs["stdin"])
        self.assertEqual(json.loads(process.communicate.call_args.kwargs["input"]),
                         api_messages(self.request)[1:])
        self.assertEqual(process.communicate.call_args.kwargs["timeout"], 120)
        self.assertEqual(replies, [("你叫小林。", True)])

    def test_cli_failure_is_marked_unsuccessful(self):
        process = Mock(returncode=2)
        process.communicate.return_value = ("partial stdout must not count as success", "offline test failure")
        worker = ClaudeCliThread(self.request)
        replies = []
        worker.reply_ready.connect(lambda *args: replies.append(args))
        with patch("core.main_panel.subprocess.Popen", return_value=process):
            worker.run()
        self.assertEqual(len(replies), 1)
        self.assertFalse(replies[0][1])
        self.assertIn("退出码 2", replies[0][0])

    def test_cli_empty_output_and_missing_binary_are_failures(self):
        process = Mock(returncode=0)
        process.communicate.return_value = (" \n", "")
        for outcome in (process, FileNotFoundError("offline missing CLI")):
            with self.subTest(outcome=type(outcome).__name__):
                worker = ClaudeCliThread(self.request)
                replies = []
                worker.reply_ready.connect(lambda *args: replies.append(args))
                with patch("core.main_panel.subprocess.Popen") as popen:
                    if isinstance(outcome, Exception):
                        popen.side_effect = outcome
                    else:
                        popen.return_value = outcome
                    worker.run()
                self.assertEqual(len(replies), 1)
                self.assertFalse(replies[0][1])
                self.assertTrue(replies[0][0].strip())

    def test_cli_timeout_kills_reaps_and_closes_pipes_with_bounded_cleanup(self):
        for cleanup_timeout in (False, True):
            with self.subTest(cleanup_timeout=cleanup_timeout):
                process = Mock(returncode=None)
                process.communicate.side_effect = [
                    subprocess.TimeoutExpired("offline-cli", 120),
                    subprocess.TimeoutExpired("offline-cli", 5) if cleanup_timeout else ("", ""),
                ]
                worker = ClaudeCliThread(self.request)
                replies = []
                worker.reply_ready.connect(lambda *args: replies.append(args))
                with patch("core.main_panel.subprocess.Popen", return_value=process):
                    worker.run()
                self.assertEqual(process.communicate.call_args_list, [
                    call(input=json.dumps(api_messages(self.request)[1:], ensure_ascii=False), timeout=120),
                    call(timeout=5),
                ])
                process.kill.assert_called_once_with()
                if cleanup_timeout:
                    process.wait.assert_called_once_with(timeout=5)
                else:
                    process.wait.assert_not_called()
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close.assert_called_once_with()
                self.assertEqual(len(replies), 1)
                self.assertFalse(replies[0][1])
                self.assertIn("超时", replies[0][0])

    def test_cli_communication_exception_also_cleans_up_process(self):
        process = Mock()
        process.communicate.side_effect = [OSError("offline broken pipe"), ("", "")]
        worker = ClaudeCliThread(self.request)
        replies = []
        worker.reply_ready.connect(lambda *args: replies.append(args))
        with patch("core.main_panel.subprocess.Popen", return_value=process):
            worker.run()
        process.kill.assert_called_once_with()
        self.assertEqual(process.communicate.call_args_list[-1], call(timeout=5))
        self.assertEqual(len(replies), 1)
        self.assertFalse(replies[0][1])
        self.assertIn("offline broken pipe", replies[0][0])

    def test_openai_receives_structured_roles_and_persona(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="你叫小林。"))])
        worker = OpenAIChatThread(self.request)
        replies = []
        worker.reply_ready.connect(lambda *args: replies.append(args))
        with patch("openai.OpenAI", return_value=client):
            worker.run()
        self.assertEqual(client.chat.completions.create.call_args.kwargs["messages"],
                         api_messages(self.request))
        self.assertEqual(replies, [("你叫小林。", True)])

    def test_openai_empty_and_exception_results_are_failures(self):
        for outcome in (None, " \n", RuntimeError("offline API failure")):
            with self.subTest(outcome=outcome):
                client = Mock()
                if isinstance(outcome, Exception):
                    client.chat.completions.create.side_effect = outcome
                else:
                    client.chat.completions.create.return_value = SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=outcome))])
                worker = OpenAIChatThread(self.request)
                replies = []
                worker.reply_ready.connect(lambda *args: replies.append(args))
                with patch("openai.OpenAI", return_value=client):
                    worker.run()
                self.assertEqual(len(replies), 1)
                self.assertFalse(replies[0][1])
                self.assertTrue(replies[0][0].strip())

    def test_agent_receives_separate_clean_execution_state_and_conversation(self):
        graph = Mock()
        graph.invoke.return_value = {"messages": [AIMessage(content="你叫小林。")]}
        worker = AgentThread(graph, self.request)
        replies = []
        worker.reply_ready.connect(lambda *args: replies.append(args))
        worker.run()
        state = graph.invoke.call_args.args[0]
        self.assertEqual(state["messages"], [])
        self.assertEqual(state["system_prompt"], self.request.system)
        self.assertEqual([type(message) for message in state["conversation"]],
                         [HumanMessage, AIMessage, HumanMessage])
        self.assertEqual([message.content for message in state["conversation"]],
                         ["我叫小林", "小林，你好", "我叫什么？"])
        self.assertEqual(state["tool_results"], {})
        self.assertEqual(state["steps_completed"], [])
        self.assertEqual(replies, [("你叫小林。", True)])

    def test_agent_empty_and_exception_results_are_failures(self):
        for outcome in ({"messages": []}, {"messages": [AIMessage(content=" \n")]},
                        RuntimeError("offline Agent failure")):
            with self.subTest(outcome=outcome):
                graph = Mock()
                if isinstance(outcome, Exception):
                    graph.invoke.side_effect = outcome
                else:
                    graph.invoke.return_value = outcome
                worker = AgentThread(graph, self.request)
                replies = []
                worker.reply_ready.connect(lambda *args: replies.append(args))
                worker.run()
                self.assertEqual(len(replies), 1)
                self.assertFalse(replies[0][1])
                self.assertTrue(replies[0][0].strip())
                self.assertNotIn("执行完成", replies[0][0])

    def test_second_normal_request_contains_first_answer_and_current_user_once(self):
        self.mock_workers()
        self.make_panel()
        first = self.send("我叫小林")
        self.reply(first, "小林，你好")
        second = self.send("我叫什么？")
        self.assertEqual(self.pairs(second.request), [
            ("user", "我叫小林"), ("assistant", "小林，你好"), ("user", "我叫什么？")])
        self.assertEqual(self.pairs(first.request), [("user", "我叫小林")])
        self.assertTrue(first.started)

    def test_agent_followup_retains_prior_normal_chat_and_agent_answer(self):
        self.mock_workers()
        self.make_panel()
        self.panel.agent_graph = object()
        first = self.send("我叫小林")
        self.assertIsNone(first.graph)
        self.reply(first, "小林，你好")
        second = self.send("帮我记住这个名字")
        self.assertIs(second.graph, self.panel.agent_graph)
        self.assertEqual(self.pairs(second.request), [
            ("user", "我叫小林"), ("assistant", "小林，你好"), ("user", "帮我记住这个名字")])
        self.reply(second, "已经记住小林")
        third = self.send("帮我再说一遍名字")
        self.assertEqual(self.pairs(third.request)[-3:], [
            ("user", "帮我记住这个名字"), ("assistant", "已经记住小林"),
            ("user", "帮我再说一遍名字")])

    def test_saved_persona_changes_next_request_without_mutating_inflight_snapshot(self):
        self.mock_workers()
        self.make_panel()
        first = self.send("你好")
        original_system = first.request.system
        self.panel._pet_name_input.setText("团团")
        self.panel._pet_personality_input.setText("耐心")
        self.panel._pet_catchphrase_input.setText("慢慢来")
        self.panel._save_settings()
        self.assertEqual(first.request.system, original_system)
        self.reply(first, "你好")
        second = self.send("现在呢")
        for phrase in ("团团", "耐心", "慢慢来"):
            self.assertIn(phrase, second.request.system)
        self.assertEqual(first.request.system, original_system)
        self.assertNotEqual(second.request.system, original_system)
        self.assertEqual(json.loads(self.state_file.read_text())["settings"]["pet_name"], "团团")

    def test_old_reply_cannot_enter_new_conversation_and_worker_survives_until_finished(self):
        self.mock_workers()
        self.make_panel()
        old = self.send("上一场问题")
        old_id = self.panel._current_session["id"]
        next(button for button in self.panel.findChildren(QPushButton)
             if button.text() == "+ 新对话").click()
        new = self.send("这一场问题")
        self.assertFalse(self.panel.send_btn.isEnabled())
        self.assertNotEqual(self.panel._current_session["id"], old_id)
        self.assertEqual(self.pairs(new.request), [("user", "这一场问题")])
        before = self.state_file.read_bytes()
        self.reply(old, "过期的回复", finish=False)
        self.assertNotIn("过期的回复", self.bubble_texts())
        self.assertNotIn("过期的回复", str(self.panel._chat_history))
        self.assertEqual(self.state_file.read_bytes(), before)
        self.assertIn(old, self.panel._chat_threads)
        self.assertIn(new, self.panel._chat_threads)
        self.assertIs(self.panel._ai_thread, new)
        self.assertFalse(self.panel.send_btn.isEnabled())
        old.finish()
        self.app.processEvents()
        self.assertNotIn(old, self.panel._chat_threads)
        self.assertIn(new, self.panel._chat_threads)
        self.assertFalse(self.panel.send_btn.isEnabled())
        self.reply(new, "本场回复")
        self.assertIn("本场回复", self.bubble_texts())
        self.assertIn("本场回复", self.state_file.read_text())
        self.assertFalse(self.panel._chat_threads)
        self.assertIsNone(self.panel._ai_thread)
        self.assertTrue(self.panel.send_btn.isEnabled())

    def test_busy_button_enter_and_direct_send_preserve_draft_without_extra_request(self):
        self.mock_workers()
        self.make_panel()
        first = self.send("第一问")
        before = self.state_file.read_bytes()
        self.assertFalse(self.panel.send_btn.isEnabled())
        self.assertTrue(self.panel.input_box.isEnabled())
        self.panel.input_box.setText("  第二问草稿  ")
        self.panel.send_btn.click()
        self.panel.input_box.returnPressed.emit()
        self.panel._on_send()
        self.assertEqual(len(self.workers), 1)
        self.assertEqual(self.panel.input_box.text(), "  第二问草稿  ")
        self.assertEqual(self.state_file.read_bytes(), before)
        self.assertEqual(self.bubble_texts()[-2:], ["第一问", "…"])
        self.reply(first, "第一答")
        self.assertTrue(self.panel.send_btn.isEnabled())
        self.assertEqual(self.panel.input_box.text(), "  第二问草稿  ")
        self.panel.send_btn.click()
        second = self.workers[-1]
        self.assertEqual(len(self.workers), 2)
        self.assertEqual(self.pairs(second.request), [
            ("user", "第一问"), ("assistant", "第一答"), ("user", "第二问草稿")])

    def test_duplicate_reply_and_old_finished_do_not_release_next_request(self):
        self.mock_workers()
        self.make_panel()
        first = self.send("第一问")
        with patch.object(self.panel.stats, "on_chat") as on_chat:
            self.reply(first, "第一答", finish=False)
            before = self.state_file.read_bytes()
            self.reply(first, "重复回复", finish=False)
            self.assertEqual(self.state_file.read_bytes(), before)
            on_chat.assert_called_once_with()
            second = self.send("第二问")
            self.reply(first, "更晚的重复回复")
            self.assertFalse(self.panel.send_btn.isEnabled())
            self.assertIs(self.panel._ai_thread, second)
            self.assertEqual(self.bubble_texts()[-2:], ["第二问", "…"])
            self.reply(second, "第二答")
            self.assertTrue(self.panel.send_btn.isEnabled())
            self.assertEqual(on_chat.call_count, 2)

    def test_worker_finished_without_reply_resolves_placeholder_as_failure(self):
        self.mock_workers()
        self.make_panel()
        worker = self.send("没有回包")
        with patch.object(self.panel.stats, "on_chat") as on_chat:
            worker.finish()
            self.app.processEvents()
            on_chat.assert_not_called()
        self.assertIn("未收到回复", self.bubble_texts()[-1])
        self.assertFalse(self.panel._chat_history[-1]["include_in_context"])
        self.assertTrue(self.panel.send_btn.isEnabled())
        self.assertFalse(self.panel._chat_threads)
        self.assertIsNone(self.panel._ai_thread)
        self.assertIsNot(self.send("再试一次"), worker)

    def test_empty_success_signal_is_visible_failure_and_allows_retry(self):
        self.mock_workers()
        self.make_panel()
        worker = self.send("空回复")
        with patch.object(self.panel.stats, "on_chat") as on_chat:
            self.reply(worker, " \n", True)
            on_chat.assert_not_called()
        self.assertIn("未收到回复", self.bubble_texts()[-1])
        self.assertFalse(self.panel._chat_history[-1]["include_in_context"])
        self.assertTrue(self.panel.send_btn.isEnabled())
        retry = self.send("重试")
        self.assertEqual(self.pairs(retry.request), [("user", "空回复"), ("user", "重试")])

    def test_constructor_failure_resolves_placeholder_and_allows_retry(self):
        self.make_panel()
        with patch("core.main_panel.ClaudeCliThread", side_effect=RuntimeError("offline construction failed")), \
                patch.object(self.panel.stats, "on_chat") as on_chat:
            self.panel.input_box.setText("创建失败")
            self.panel._on_send()
            on_chat.assert_not_called()
        self.assertIn("offline construction failed", self.bubble_texts()[-1])
        self.assertFalse(self.panel._chat_history[-1]["include_in_context"])
        self.assertTrue(self.panel.send_btn.isEnabled())
        self.assertFalse(self.panel._chat_threads)
        self.mock_workers()
        self.assertTrue(self.send("重试创建").started)

    def test_start_failure_resolves_placeholder_and_releases_unstarted_worker(self):
        self.make_panel()
        failed = DeferredChat(self.request)
        with patch("core.main_panel.ClaudeCliThread", return_value=failed), \
                patch.object(failed, "start", side_effect=RuntimeError("offline start failed")), \
                patch.object(self.panel.stats, "on_chat") as on_chat:
            self.panel.input_box.setText("启动失败")
            self.panel._on_send()
            on_chat.assert_not_called()
        self.assertIn("offline start failed", self.bubble_texts()[-1])
        self.assertFalse(self.panel._chat_history[-1]["include_in_context"])
        self.assertTrue(self.panel.send_btn.isEnabled())
        self.assertFalse(self.panel._chat_threads)
        self.assertIsNone(self.panel._ai_thread)
        self.mock_workers()
        self.assertTrue(self.send("重试启动").started)

    def test_new_sessions_created_in_same_millisecond_do_not_replace_each_other(self):
        self.mock_workers()
        self.make_panel()
        with patch("core.main_panel.time.time", return_value=1234567.0):
            first = self.send("第一场")
            self.reply(first, "第一答")
            first_id = self.panel._current_session["id"]
            self.panel._new_chat_session()
            second = self.send("第二场")
            self.reply(second, "第二答")
            second_id = self.panel._current_session["id"]
        self.assertGreater(second_id, first_id)
        sessions = json.loads(self.state_file.read_text())["chat_sessions"]
        self.assertEqual({session["id"] for session in sessions}, {first_id, second_id})
        self.assertEqual({session["title"] for session in sessions}, {"第一场", "第二场"})

    def test_oversized_input_is_preserved_and_neither_saved_nor_sent(self):
        self.mock_workers()
        self.make_panel()
        text = "很" * (MAX_CONTEXT_CHARS + 1)
        self.panel.input_box.setText(text)
        before = self.state_file.read_bytes()
        before_bubbles = self.bubble_texts()
        with patch("core.main_panel.QMessageBox.information") as warning:
            self.panel.input_box.returnPressed.emit()
        warning.assert_called_once()
        self.assertEqual(self.panel.input_box.text(), text)
        self.assertEqual(self.state_file.read_bytes(), before)
        self.assertEqual(self.bubble_texts(), before_bubbles)
        self.assertFalse(self.workers)

    def test_failed_reply_is_visible_but_not_model_context_on_next_request(self):
        self.mock_workers()
        self.make_panel()
        first = self.send("第一问")
        self.reply(first, "模拟连接失败", False)
        self.assertIn("模拟连接失败", self.bubble_texts())
        saved = json.loads(self.state_file.read_text())["chat_history"]
        self.assertFalse(saved[-1]["include_in_context"])
        second = self.send("再试试")
        self.assertEqual(self.pairs(second.request), [("user", "第一问"), ("user", "再试试")])

    def test_real_qthread_reply_runs_ui_callback_on_application_thread(self):
        self.make_panel()
        work_threads = []
        callback_threads = []
        client = Mock()

        def complete(**kwargs):
            work_threads.append(QThread.currentThread())
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="离线线程回复"))])

        client.chat.completions.create.side_effect = complete
        receive = self.panel._receive_chat_reply

        def receive_on_main(*args):
            callback_threads.append(QThread.currentThread())
            receive(*args)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-fake-key"}), \
                patch("openai.OpenAI", return_value=client), \
                patch.object(self.panel, "_receive_chat_reply", side_effect=receive_on_main):
            self.panel.input_box.setText("线程验收")
            self.panel.input_box.returnPressed.emit()
            worker = self.panel._ai_thread
            try:
                deadline = time.monotonic() + 5
                while self.panel._chat_threads and time.monotonic() < deadline:
                    self.app.processEvents()
                    QThread.msleep(1)
                self.assertFalse(self.panel._chat_threads, "Worker did not finish within five seconds")
            finally:
                # If an assertion fails, never destroy a still-running QThread.
                worker.wait(5000)
        self.assertEqual(callback_threads, [self.app.thread()])
        self.assertEqual(len(work_threads), 1)
        self.assertIsNot(work_threads[0], self.app.thread())
        self.assertIn("离线线程回复", self.bubble_texts())


if __name__ == "__main__":
    unittest.main()
