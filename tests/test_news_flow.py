"""Offline news refresh races and worker lifetime checks; no live requests."""

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from config import Config
from core.main_panel import MainPanel
from features.news_push.news_feature import NewsFetchWorker


def news(title):
    return {"success": True, "data": [{"title": title, "source": "离线新闻", "link": ""}]}


class DeferredNews(QObject):
    """Deliver a result separately from finished, as a real worker can."""

    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, feature):
        super().__init__()
        self.feature = feature
        self.started = False
        self.completed = False

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started and not self.completed

    def finish(self):
        self.completed = True
        self.finished.emit()


class NewsFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-news-flow-")
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
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in news test")),
            patch("socket.create_connection", side_effect=AssertionError("Network forbidden in news test")),
            patch("core.main_panel.subprocess.Popen", side_effect=AssertionError("Real CLI forbidden in news test")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.close_panel)

    def close_panel(self):
        for worker in self.workers:
            if worker.started and not worker.completed:
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

    def worker_factory(self, feature):
        worker = DeferredNews(feature)
        self.workers.append(worker)
        return worker

    def mock_workers(self):
        patcher = patch("core.main_panel.NewsFetchWorker", side_effect=self.worker_factory)
        patcher.start()
        self.addCleanup(patcher.stop)

    def refresh(self):
        buttons = [button for button in self.panel._stack.widget(1).findChildren(QPushButton)
                   if button.text() == "刷新"]
        self.assertEqual(len(buttons), 1)
        buttons[0].click()
        return self.panel._news_worker

    def text(self):
        # Read only the current layout: findChildren on the whole container
        # also includes obsolete cards awaiting deleteLater().
        lines = []
        for index in range(self.panel._news_layout.count()):
            widget = self.panel._news_layout.itemAt(index).widget()
            if isinstance(widget, QLabel):
                lines.append(widget.text())
            elif widget is not None:
                lines.extend(label.text() for label in widget.findChildren(QLabel))
        return "\n".join(lines)

    def deliver(self, worker, result=None, *, error=None, finish=True):
        if error is None:
            worker.result_ready.emit(result or {})
        else:
            worker.error_occurred.emit(error)
        self.app.processEvents()
        if finish:
            worker.finish()
            self.app.processEvents()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
        self.assertTrue(predicate(), "Qt worker did not reach the expected state within five seconds")

    def test_refresh_shows_loading_and_keeps_all_running_workers(self):
        self.mock_workers()
        self.make_panel()
        before = self.state_file.read_bytes()
        first = self.refresh()
        second = self.refresh()
        self.assertIn("获取中", self.text())
        self.assertTrue(first.started)
        self.assertTrue(second.started)
        self.assertIs(first.feature, self.panel._news_feature)
        self.assertIs(second.feature, self.panel._news_feature)
        self.assertEqual(self.panel._news_workers, {first, second})
        self.assertIs(self.panel._news_worker, second)
        self.assertEqual(self.state_file.read_bytes(), before)

    def test_old_success_cannot_replace_new_result_and_workers_live_until_finished(self):
        self.mock_workers()
        self.make_panel()
        first = self.refresh()
        second = self.refresh()
        self.deliver(second, news("最新新闻"), finish=False)
        expected = self.text()
        self.assertIn("最新新闻", expected)
        self.assertIsNone(self.panel._pending_news)
        self.deliver(first, news("过期新闻"), finish=False)
        self.assertEqual(self.text(), expected)
        self.assertEqual(self.panel._news_workers, {first, second})
        first.finish()
        self.app.processEvents()
        self.assertEqual(self.panel._news_workers, {second})
        self.assertIs(self.panel._news_worker, second)
        second.finish()
        self.app.processEvents()
        self.assertFalse(self.panel._news_workers)
        self.assertIsNone(self.panel._news_worker)
        self.assertEqual(self.text(), expected)

    def test_old_errors_do_not_replace_current_loading_or_success(self):
        self.mock_workers()
        self.make_panel()
        first = self.refresh()
        second = self.refresh()
        loading = self.text()
        request = self.panel._pending_news
        self.deliver(first, error="旧错误", finish=False)
        self.assertEqual(self.text(), loading)
        self.assertIs(self.panel._pending_news, request)
        self.deliver(second, news("最新新闻"))
        expected = self.text()
        self.deliver(first, error="更晚的旧错误")
        self.assertEqual(self.text(), expected)

    def test_three_refreshes_keep_only_latest_request_eligible(self):
        self.mock_workers()
        self.make_panel()
        first, second, latest = self.refresh(), self.refresh(), self.refresh()
        request = self.panel._pending_news
        loading = self.text()
        self.deliver(second, error="第二次失败")
        self.deliver(first, news("第一次成功"))
        self.assertEqual(self.text(), loading)
        self.assertIs(self.panel._pending_news, request)
        self.assertEqual(self.panel._news_workers, {latest})
        self.deliver(latest, news("第三次成功"))
        self.assertIn("第三次成功", self.text())

    def test_duplicate_results_cannot_change_completed_or_next_request(self):
        self.mock_workers()
        self.make_panel()
        first = self.refresh()
        self.deliver(first, news("有效结果"), finish=False)
        expected = self.text()
        self.deliver(first, error="重复失败", finish=False)
        self.deliver(first, news("重复成功"), finish=False)
        self.assertEqual(self.text(), expected)
        second = self.refresh()
        request = self.panel._pending_news
        loading = self.text()
        self.deliver(first, news("跨请求重复结果"))
        self.assertEqual(self.text(), loading)
        self.assertIs(self.panel._pending_news, request)
        self.assertEqual(self.panel._news_workers, {second})
        self.deliver(second, news("第二次有效结果"))
        self.assertIn("第二次有效结果", self.text())

    def test_current_error_is_visible_and_refresh_can_retry(self):
        self.mock_workers()
        self.make_panel()
        first = self.refresh()
        self.deliver(first, error="离线新闻失败")
        self.assertIn("离线新闻失败", self.text())
        self.assertIsNone(self.panel._pending_news)
        self.assertFalse(self.panel._news_workers)
        second = self.refresh()
        self.assertIsNot(first, second)
        self.assertIn("获取中", self.text())
        self.deliver(second, news("重试成功"))
        self.assertIn("重试成功", self.text())

    def test_empty_or_unsuccessful_results_end_loading_and_allow_retry(self):
        self.mock_workers()
        self.make_panel()
        for result in ({}, {"success": True, "data": []}, {"success": False, "data": []}):
            with self.subTest(result=result):
                worker = self.refresh()
                self.deliver(worker, result)
                self.assertIn("暂无新闻", self.text())
                self.assertNotIn("获取中", self.text())
                self.assertIsNone(self.panel._pending_news)
                self.assertFalse(self.panel._news_workers)
        retry = self.refresh()
        self.deliver(retry, news("空结果后重试成功"))
        self.assertIn("空结果后重试成功", self.text())

    def test_current_finished_without_result_ends_loading_and_allows_retry(self):
        self.mock_workers()
        self.make_panel()
        first = self.refresh()
        first.finish()
        self.app.processEvents()
        self.assertIn("未收到新闻数据", self.text())
        self.assertIsNone(self.panel._pending_news)
        self.assertFalse(self.panel._news_workers)
        self.assertIsNone(self.panel._news_worker)
        retry = self.refresh()
        self.deliver(retry, news("无结果后重试成功"))
        self.assertIn("无结果后重试成功", self.text())

    def test_old_finished_without_result_keeps_current_loading(self):
        self.mock_workers()
        self.make_panel()
        first = self.refresh()
        second = self.refresh()
        request, loading = self.panel._pending_news, self.text()
        first.finish()
        self.app.processEvents()
        self.assertEqual(self.text(), loading)
        self.assertIs(self.panel._pending_news, request)
        self.assertEqual(self.panel._news_workers, {second})
        self.assertIs(self.panel._news_worker, second)

    def test_constructor_failure_ends_loading_and_allows_retry(self):
        self.make_panel()
        with patch("core.main_panel.NewsFetchWorker", side_effect=RuntimeError("offline construction failed")):
            self.refresh()
        self.assertIn("offline construction failed", self.text())
        self.assertIsNone(self.panel._pending_news)
        self.assertFalse(self.panel._news_workers)
        self.assertIsNone(self.panel._news_worker)
        self.mock_workers()
        self.assertTrue(self.refresh().started)

    def test_constructor_failure_preserves_old_running_worker_but_ignores_its_result(self):
        self.mock_workers()
        self.make_panel()
        old = self.refresh()
        with patch("core.main_panel.NewsFetchWorker", side_effect=RuntimeError("offline construction failed")):
            self.refresh()
        expected = self.text()
        self.assertIn("offline construction failed", expected)
        self.assertEqual(self.panel._news_workers, {old})
        self.assertIsNone(self.panel._news_worker)
        self.deliver(old, news("旧请求迟到的成功"))
        self.assertEqual(self.text(), expected)
        self.assertFalse(self.panel._news_workers)

    def test_start_failure_releases_unstarted_worker_and_allows_retry(self):
        self.make_panel()
        failed = DeferredNews(self.panel._news_feature)
        with patch("core.main_panel.NewsFetchWorker", return_value=failed), \
                patch.object(failed, "start", side_effect=RuntimeError("offline start failed")):
            self.refresh()
        self.assertIn("offline start failed", self.text())
        self.assertIsNone(self.panel._pending_news)
        self.assertFalse(self.panel._news_workers)
        self.assertIsNone(self.panel._news_worker)
        self.mock_workers()
        self.assertTrue(self.refresh().started)

    def test_start_error_does_not_release_an_already_running_worker_early(self):
        self.make_panel()
        failed = self.worker_factory(self.panel._news_feature)

        def started_then_failed():
            failed.started = True
            raise RuntimeError("offline error after start")

        with patch("core.main_panel.NewsFetchWorker", return_value=failed), \
                patch.object(failed, "start", side_effect=started_then_failed):
            self.refresh()
        expected = self.text()
        self.assertIn("offline error after start", expected)
        self.assertIsNone(self.panel._pending_news)
        self.assertEqual(self.panel._news_workers, {failed})
        self.deliver(failed, news("失败后迟到结果"))
        self.assertEqual(self.text(), expected)
        self.assertFalse(self.panel._news_workers)
        self.assertIsNone(self.panel._news_worker)

    def test_worker_preserves_feature_result_and_exception_contract(self):
        self.make_panel()
        result = news("原服务返回值")
        worker = NewsFetchWorker(self.panel._news_feature)
        results, errors = [], []
        worker.result_ready.connect(results.append)
        worker.error_occurred.connect(errors.append)
        with patch.object(self.panel._news_feature, "execute", return_value=result) as execute:
            worker.run()
        execute.assert_called_once_with()
        self.assertEqual(results, [result])
        self.assertFalse(errors)
        with patch.object(self.panel._news_feature, "execute", side_effect=RuntimeError("offline fetch failed")):
            worker.run()
        self.assertEqual(results, [result])
        self.assertEqual(errors, ["offline fetch failed"])

    def test_real_qthreads_deliver_out_of_order_results_on_application_thread(self):
        self.make_panel()
        started = [threading.Event(), threading.Event()]
        release = [threading.Event(), threading.Event()]
        work_threads, callback_threads = [], []
        lock = threading.Lock()

        def fetch():
            with lock:
                index = len(work_threads)
                work_threads.append(QThread.currentThread())
            started[index].set()
            if not release[index].wait(5):
                raise RuntimeError("offline news release deadline exceeded")
            return news(("真实线程旧新闻", "真实线程最新新闻")[index])

        receive = self.panel._on_news_loaded

        def receive_on_main(*args):
            callback_threads.append(QThread.currentThread())
            receive(*args)

        live_workers = []
        with patch.object(self.panel._news_feature, "execute", side_effect=fetch), \
                patch.object(self.panel, "_on_news_loaded", side_effect=receive_on_main):
            try:
                first = self.refresh()
                live_workers.append(first)
                self.assertTrue(started[0].wait(5), "First news worker did not start")
                second = self.refresh()
                live_workers.append(second)
                self.assertTrue(started[1].wait(5), "Second news worker did not start")
                self.assertEqual(self.panel._news_workers, {first, second})
                release[1].set()
                self.wait_for(lambda: second not in self.panel._news_workers)
                expected = self.text()
                self.assertIn("真实线程最新新闻", expected)
                self.assertIn(first, self.panel._news_workers)
                release[0].set()
                self.wait_for(lambda: not self.panel._news_workers)
                self.assertEqual(self.text(), expected)
            finally:
                for gate in release:
                    gate.set()
                for worker in live_workers:
                    try:
                        worker.wait(5000)
                    except RuntimeError:
                        pass  # Qt may have already processed deleteLater().
                self.app.processEvents()
        self.assertEqual(callback_threads, [self.app.thread(), self.app.thread()])
        self.assertEqual(len(work_threads), 2)
        self.assertTrue(all(thread is not self.app.thread() for thread in work_threads))


if __name__ == "__main__":
    unittest.main()
