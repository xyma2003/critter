"""Offline diary evidence, adapter, and real Qt worker acceptance tests."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import datetime
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from config import Config
from core import state_manager
from core.main_panel import MainPanel
from services import diary, notes


ZERO_COUNTS = {"feed": 0, "play": 0, "rest": 0, "pet": 0}
STATS = {"mood": 70, "hunger": 65, "energy": 60, "mood_label": "还不错"}


class DeferredDiary(QObject):
    """A worker whose result and thread completion can arrive separately."""

    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, *args):
        super().__init__()
        self.args = args
        self.running = False
        self.starts = 0

    def start(self):
        self.running = True
        self.starts += 1

    def isRunning(self):
        return self.running

    def finish(self):
        self.running = False
        self.finished.emit()


class DiaryFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-diary-flow-")
        self.addCleanup(self.temp.cleanup)
        self.state_file = Path(self.temp.name) / "state.json"
        self.panels = []
        self.workers = []
        for patcher in (
            patch.object(state_manager, "_STATE_FILE", str(self.state_file)),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch("core.main_panel.CLAUDE_CLI", "/missing/offline-test-claude"),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in diary tests")),
            patch("socket.create_connection", side_effect=AssertionError("Network forbidden in diary tests")),
            patch("subprocess.Popen", side_effect=AssertionError("Real CLI forbidden in diary tests")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.close_panels)

    def close_panels(self):
        for worker in self.workers:
            try:
                if isinstance(worker, DeferredDiary):
                    if worker.running:
                        worker.finish()
                else:
                    worker.wait(3000)
            except RuntimeError:
                pass  # Qt may already have processed the worker's deleteLater.
        self.app.processEvents()
        for panel in self.panels:
            panel.close()
            panel.deleteLater()
        self.app.processEvents()

    def make_panel(self):
        panel = MainPanel(None)
        panel._decay_timer.stop()
        panel.show()
        self.panels.append(panel)
        self.app.processEvents()
        return panel

    def click_action(self, panel, text):
        panel._switch_tab(2)
        self.app.processEvents()
        button = next(button for button in panel._stack.widget(2).findChildren(QPushButton)
                      if button.text().endswith(text))
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def mock_workers(self):
        def factory(*args):
            worker = DeferredDiary(*args)
            self.workers.append(worker)
            return worker

        patcher = patch.object(diary, "DiaryWorker", side_effect=factory)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    def click_generate(self, panel):
        panel._switch_tab(5)
        self.app.processEvents()
        QTest.mouseClick(panel._diary_generate_btn, Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def wait_for(self, condition):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            QTest.qWait(5)
        self.fail("Timed out waiting for the offline Qt worker")

    def test_real_pet_buttons_supply_exact_evidence_and_survive_panel_restart(self):
        self.mock_workers()
        panel = self.make_panel()
        for action in ("喂食", "喂食", "玩耍"):
            self.click_action(panel, action)
        expected = {"feed": 2, "play": 1, "rest": 0, "pet": 0}
        today = datetime.date.today().isoformat()
        self.assertEqual(state_manager.load_pet_interaction_counts(today), expected)
        self.assertEqual(panel._refresh_diary_evidence(today), expected)
        label = panel._diary_evidence_label.text()
        self.assertIn(today, label)
        self.assertRegex(label, r"喂食\D*2")
        self.assertRegex(label, r"玩耍\D*1")

        panel.close()
        state_manager._runtimes.pop(str(self.state_file), None)
        restarted = self.make_panel()
        self.click_generate(restarted)
        self.assertEqual(self.workers[-1].args[1], expected)
        self.assertEqual(self.workers[-1].args[-1], today)

    def test_new_day_has_zero_evidence_without_erasing_previous_day(self):
        panel = self.make_panel()
        self.click_action(panel, "喂食")
        today = datetime.date.today()
        tomorrow = (today + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(panel._refresh_diary_evidence(tomorrow), ZERO_COUNTS)
        label = panel._diary_evidence_label.text()
        self.assertIn(tomorrow, label)
        self.assertTrue(any(word in label for word in ("未记录", "暂无", "没有记录")), label)
        self.assertEqual(state_manager.load_pet_interaction_counts(today.isoformat())["feed"], 1)

    def test_request_snapshot_and_saved_date_survive_actions_settings_and_midnight(self):
        mocked = self.mock_workers()
        panel = self.make_panel()
        self.click_action(panel, "喂食")
        panel._app_settings.update(pet_name="团团", pet_personality="耐心", pet_catchphrase="慢慢来")
        original_date = datetime.date.today()

        class ControlledDate(datetime.date):
            current = original_date

            @classmethod
            def today(cls):
                return cls.current

        with patch("core.main_panel.datetime.date", ControlledDate):
            self.click_generate(panel)
            worker = self.workers[-1]
            stats_before = dict(worker.args[0])
            self.assertEqual(worker.args[1], {"feed": 1, "play": 0, "rest": 0, "pet": 0})
            self.assertEqual(worker.args[2:5], ("团团", "耐心", "慢慢来"))
            self.assertEqual(worker.args[-1], original_date.isoformat())
            source_before = panel._diary_source_label.text()
            self.assertIn(original_date.isoformat(), source_before)
            self.assertRegex(source_before, r"玩耍\D*0")

            self.click_action(panel, "玩耍")
            panel._app_settings.update(pet_name="豆豆", pet_personality="活泼", pet_catchphrase="汪")
            ControlledDate.current = original_date + datetime.timedelta(days=1)
            panel._refresh_diary_evidence()
            self.assertIn(ControlledDate.current.isoformat(), panel._diary_evidence_label.text())
            self.assertEqual(panel._diary_source_label.text(), source_before)
            self.assertEqual(worker.args[0], stats_before)
            self.assertEqual(worker.args[1], {"feed": 1, "play": 0, "rest": 0, "pet": 0})
            self.assertEqual(worker.args[2:5], ("团团", "耐心", "慢慢来"))

            worker.result_ready.emit("[离线模拟] 这篇日记属于点击时的日期。")
            self.app.processEvents()
            self.assertFalse(panel._diary_generate_btn.isEnabled())
            worker.finish()
            self.app.processEvents()

        self.assertEqual(mocked.call_count, 1)
        saved = notes.load_all()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["kind"], "diary")
        self.assertEqual(saved[0]["date"], original_date.isoformat())
        self.assertEqual(saved[0]["content"], panel._diary_text.toPlainText())
        self.assertTrue(panel._diary_generate_btn.isEnabled())

    def test_duplicate_generation_is_blocked_until_thread_finishes(self):
        mocked = self.mock_workers()
        panel = self.make_panel()
        self.click_generate(panel)
        worker = self.workers[-1]
        self.assertTrue(worker.isRunning())
        self.assertFalse(panel._diary_generate_btn.isEnabled())
        self.click_generate(panel)
        panel._generate_diary()  # Also guard programmatic entry, not only the disabled button.
        self.assertEqual(mocked.call_count, 1)
        worker.result_ready.emit("[离线模拟] 一次生成。")
        self.app.processEvents()
        self.assertFalse(panel._diary_generate_btn.isEnabled())
        worker.finish()
        self.app.processEvents()
        self.assertTrue(panel._diary_generate_btn.isEnabled())
        self.click_generate(panel)
        self.assertEqual(mocked.call_count, 2)

    def test_failure_keeps_existing_diary_and_allows_retry_only_after_finish(self):
        self.mock_workers()
        existing = notes.create_diary("已保存的旧日记", "2026-01-01")
        panel = self.make_panel()
        self.click_generate(panel)
        worker = self.workers[-1]
        worker.error_occurred.emit("生成失败：离线测试错误")
        self.app.processEvents()
        self.assertIn("离线测试错误", panel._diary_text.toPlainText())
        self.assertEqual(notes.load_all(), [existing])
        self.assertFalse(panel._diary_generate_btn.isEnabled())
        worker.finish()
        self.app.processEvents()
        self.assertTrue(panel._diary_generate_btn.isEnabled())

    def test_real_qthread_success_updates_widgets_and_persists_one_diary(self):
        panel = self.make_panel()
        self.click_action(panel, "抚摸")
        self.click_action(panel, "休息")
        worker_class = diary.DiaryWorker

        def factory(*args):
            worker = worker_class(*args)
            self.workers.append(worker)
            return worker

        with patch.object(diary, "generate_diary", return_value="[离线模拟] 摸摸之后休息。") as generate, \
             patch.object(diary, "DiaryWorker", side_effect=factory):
            self.click_generate(panel)
            self.wait_for(lambda: panel._diary_generate_btn.isEnabled())
        self.assertEqual(generate.call_args.args[1], {"feed": 0, "play": 0, "rest": 1, "pet": 1})
        self.assertEqual(panel._diary_text.toPlainText(), "[离线模拟] 摸摸之后休息。")
        saved = notes.load_all()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["date"], datetime.date.today().isoformat())

    def test_real_qthread_exception_does_not_create_diary(self):
        panel = self.make_panel()
        worker_class = diary.DiaryWorker

        def factory(*args):
            worker = worker_class(*args)
            self.workers.append(worker)
            return worker

        with patch.object(diary, "generate_diary", side_effect=RuntimeError("离线模拟服务失败")), \
             patch.object(diary, "DiaryWorker", side_effect=factory):
            self.click_generate(panel)
            self.wait_for(lambda: panel._diary_generate_btn.isEnabled())
        self.assertIn("离线模拟服务失败", panel._diary_text.toPlainText())
        self.assertEqual(notes.load_all(), [])


class DiaryPromptTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in diary tests")),
            patch("subprocess.Popen", side_effect=AssertionError("Real CLI forbidden in diary tests")),
            patch.dict(os.environ, {"OPENAI_API_KEY": ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def prompt(self, counts):
        return diary.build_diary_prompt(STATS, counts, "团团", "耐心", "慢慢来", "2026-10-13")

    def test_prompt_marks_recorded_counts_and_current_mood_as_limited_evidence(self):
        prompt = self.prompt({"feed": 2, "play": 1, "rest": 0, "pet": 3})
        for label, count in (("喂食", 2), ("玩耍", 1), ("休息", 0), ("抚摸", 3)):
            self.assertRegex(prompt, rf"{label}[^\n]{{0,15}}{count}")
        for phrase in ("团团", "耐心", "慢慢来", "本地", "记录", "生成时", "快照"):
            self.assertIn(phrase, prompt)
        self.assertTrue(any(word in prompt for word in ("不能", "不代表", "不等于")), prompt)
        self.assertNotIn("今天好像没有太多互动", prompt)

    def test_empty_evidence_prompt_never_equates_no_record_with_no_interaction(self):
        prompt = self.prompt(ZERO_COUNTS)
        self.assertTrue(any(word in prompt for word in ("未记录", "暂无", "没有记录")), prompt)
        self.assertTrue(any(word in prompt for word in ("编造", "虚构", "臆造")), prompt)
        self.assertTrue(any(word in prompt for word in ("未发生", "没发生", "没有发生")), prompt)
        self.assertNotIn("今天好像没有太多互动", prompt)

    def test_api_and_cli_receive_same_prompt_for_counts_and_empty_day(self):
        for counts in ({"feed": 2, "play": 1, "rest": 0, "pet": 0}, ZERO_COUNTS):
            with self.subTest(counts=counts):
                expected = self.prompt(counts)
                client = Mock()
                client.chat.completions.create.return_value = SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="  离线日记。  "))])
                with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-key"}), \
                     patch("openai.OpenAI", return_value=client):
                    result = diary.generate_diary(STATS, counts, "团团", "耐心", "慢慢来", "2026-10-13")
                self.assertEqual(result, "离线日记。")
                messages = client.chat.completions.create.call_args.kwargs["messages"]
                self.assertIn(expected, [message["content"] for message in messages])

                process = SimpleNamespace(returncode=0, stdout="  离线日记。  ", stderr="")
                with patch.object(diary.subprocess, "run", return_value=process) as run:
                    result = diary.generate_diary(STATS, counts, "团团", "耐心", "慢慢来", "2026-10-13")
                self.assertEqual(result, "离线日记。")
                self.assertTrue(expected in run.call_args.args[0]
                                or expected == run.call_args.kwargs.get("input"))

    def test_worker_copies_input_dictionaries_before_generation(self):
        stats = dict(STATS)
        counts = {"feed": 2, "play": 1, "rest": 0, "pet": 0}
        worker = diary.DiaryWorker(stats, counts, "团团", "耐心", "慢慢来", "2026-10-13")
        stats["mood_label"] = "随后改变的心情"
        counts["feed"] = 99
        with patch.object(diary, "generate_diary", return_value="离线日记") as generate:
            worker.run()
        self.assertEqual(generate.call_args.args[0], STATS)
        self.assertEqual(generate.call_args.args[1], {"feed": 2, "play": 1, "rest": 0, "pet": 0})

    def test_failed_cli_output_is_not_mistaken_for_a_diary(self):
        process = SimpleNamespace(returncode=1, stdout="诊断输出，不是日记", stderr="offline error")
        with patch.object(diary.subprocess, "run", return_value=process):
            result = diary.generate_diary(STATS, ZERO_COUNTS, "团团", "耐心", "慢慢来", "2026-10-13")
        self.assertIsNone(result)

    def test_empty_provider_response_emits_error_instead_of_success(self):
        worker = diary.DiaryWorker(STATS, ZERO_COUNTS, "团团", "耐心", "慢慢来", "2026-10-13")
        results, errors = [], []
        worker.result_ready.connect(results.append)
        worker.error_occurred.connect(errors.append)
        with patch.object(diary, "generate_diary", return_value=None):
            worker.run()
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("生成失败", errors[0])


if __name__ == "__main__":
    unittest.main()
