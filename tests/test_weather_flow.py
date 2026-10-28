"""Offline weather UI races and real Qt worker delivery; no live requests."""

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
from PyQt6.QtWidgets import QApplication

from config import Config
from core.main_panel import MainPanel, WeatherThread


def weather(description, temperature="18"):
    return {
        "desc_zh": description,
        "temp_C": temperature,
        "feels_like_C": "17",
        "forecast": [{"date": "2026-10-28", "desc": "晴", "min_C": "12", "max_C": "20"}],
    }


class DeferredWeather(QObject):
    """Deliver a result and finish independently, just like a real QThread."""

    done = pyqtSignal(object, bool, object)
    finished = pyqtSignal()

    def __init__(self, city, force=False):
        super().__init__()
        self.city = city
        self.force = force
        self.started = False
        self.completed = False

    def start(self):
        self.started = True

    def isRunning(self):
        return self.started and not self.completed

    def finish(self):
        self.completed = True
        self.finished.emit()


class WeatherFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-weather-flow-")
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
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in weather test")),
            patch("socket.create_connection", side_effect=AssertionError("Network forbidden in weather test")),
            patch("core.main_panel.subprocess.Popen", side_effect=AssertionError("Real CLI forbidden in weather test")),
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

    def worker_factory(self, city, force=False):
        worker = DeferredWeather(city, force)
        self.workers.append(worker)
        return worker

    def mock_workers(self):
        patcher = patch("core.main_panel.WeatherThread", side_effect=self.worker_factory)
        patcher.start()
        self.addCleanup(patcher.stop)

    def select(self, city):
        self.panel._select_city(city)
        return self.workers[-1]

    def deliver(self, worker, data=None, *, error=None, from_cache=False, finish=True):
        worker.done.emit(data, from_cache, error)
        self.app.processEvents()
        if finish:
            worker.finish()
            self.app.processEvents()

    def wait_for(self, predicate):
        """Pump Qt events with a bounded deadline; ordering comes from Events."""
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
        self.assertTrue(predicate(), "Qt worker did not reach the expected state within five seconds")

    def test_new_selection_shows_loading_and_keeps_all_running_workers(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        second = self.select("上海")
        self.assertEqual(self.panel._weather_selected, "上海")
        self.assertIn("上海", self.panel._weather_detail.text())
        self.assertIn("获取", self.panel._weather_detail.text())
        self.assertTrue(first.started)
        self.assertTrue(second.started)
        self.assertEqual(self.panel._weather_threads, {first, second})
        self.assertIs(self.panel._weather_thread, second)

    def test_late_old_success_cannot_overwrite_new_city_or_release_its_worker(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        second = self.select("上海")
        self.deliver(second, weather("上海多云", "23"), finish=False)
        expected = self.panel._weather_detail.text()
        self.assertIn("📍 上海", expected)
        self.assertIn("上海多云  23°C", expected)
        self.assertIn("2026-10-28", expected)
        self.deliver(first, weather("北京旧天气"), finish=False)
        self.assertEqual(self.panel._weather_detail.text(), expected)
        self.assertEqual(self.panel._weather_threads, {first, second})
        first.finish()
        self.app.processEvents()
        self.assertEqual(self.panel._weather_detail.text(), expected)
        self.assertEqual(self.panel._weather_threads, {second})
        self.assertIs(self.panel._weather_thread, second)
        second.finish()
        self.app.processEvents()
        self.assertFalse(self.panel._weather_threads)
        self.assertIsNone(self.panel._weather_thread)

    def test_late_old_error_does_not_replace_current_loading_or_success(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        second = self.select("上海")
        loading = self.panel._weather_detail.text()
        self.deliver(first, error="北京旧错误", finish=False)
        self.assertEqual(self.panel._weather_detail.text(), loading)
        self.assertIsNotNone(self.panel._pending_weather)
        self.deliver(second, weather("上海成功"), from_cache=True)
        expected = self.panel._weather_detail.text()
        self.deliver(first, error="北京更晚的错误")
        self.assertEqual(self.panel._weather_detail.text(), expected)
        self.assertIn("上海成功", expected)

    def test_returning_to_same_city_still_ignores_its_first_request(self):
        self.mock_workers()
        self.make_panel()
        first_a = self.select("北京")
        first_b = self.select("上海")
        latest_a = self.select("北京")
        current_request = self.panel._pending_weather
        loading = self.panel._weather_detail.text()
        self.deliver(first_a, weather("北京旧天气"))
        self.deliver(first_b, error="上海旧错误")
        self.assertEqual(self.panel._weather_detail.text(), loading)
        self.assertIs(self.panel._pending_weather, current_request)
        self.assertEqual(self.panel._weather_threads, {latest_a})
        self.assertIs(self.panel._weather_thread, latest_a)
        self.deliver(latest_a, weather("北京新天气"))
        self.assertIn("北京新天气", self.panel._weather_detail.text())
        self.assertNotIn("北京旧天气", self.panel._weather_detail.text())

    def test_duplicate_results_do_not_change_completed_result_or_next_request(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        self.deliver(first, weather("第一次有效结果"), finish=False)
        expected = self.panel._weather_detail.text()
        self.assertIsNone(self.panel._pending_weather)
        self.deliver(first, error="重复失败", finish=False)
        self.deliver(first, weather("重复成功"), finish=False)
        self.assertEqual(self.panel._weather_detail.text(), expected)
        second = self.select("上海")
        loading = self.panel._weather_detail.text()
        request = self.panel._pending_weather
        self.deliver(first, weather("跨请求重复结果"))
        self.assertEqual(self.panel._weather_detail.text(), loading)
        self.assertIs(self.panel._pending_weather, request)
        self.assertEqual(self.panel._weather_threads, {second})
        self.deliver(second, weather("上海有效结果"))
        self.assertIn("上海有效结果", self.panel._weather_detail.text())

    def test_old_worker_finishing_without_result_leaves_current_request_loading(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        second = self.select("上海")
        loading = self.panel._weather_detail.text()
        current_request = self.panel._pending_weather
        first.finish()
        self.app.processEvents()
        self.assertEqual(self.panel._weather_detail.text(), loading)
        self.assertIs(self.panel._pending_weather, current_request)
        self.assertEqual(self.panel._weather_threads, {second})
        self.assertIs(self.panel._weather_thread, second)

    def test_current_error_is_visible_and_allows_same_city_retry(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        self.deliver(first, error="离线天气失败")
        self.assertIn("离线天气失败", self.panel._weather_detail.text())
        self.assertIsNone(self.panel._pending_weather)
        self.assertFalse(self.panel._weather_threads)
        second = self.select("北京")
        self.assertIsNot(second, first)
        self.assertIn("获取", self.panel._weather_detail.text())
        self.deliver(second, weather("重试成功"))
        self.assertIn("重试成功", self.panel._weather_detail.text())

    def test_empty_current_result_ends_loading_and_allows_retry(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        self.deliver(first)
        self.assertIn("暂无数据", self.panel._weather_detail.text())
        self.assertIsNone(self.panel._pending_weather)
        self.assertFalse(self.panel._weather_threads)
        second = self.select("北京")
        self.deliver(second, weather("空结果后重试成功"))
        self.assertIn("空结果后重试成功", self.panel._weather_detail.text())

    def test_current_worker_finishing_without_result_ends_loading_and_allows_retry(self):
        self.mock_workers()
        self.make_panel()
        first = self.select("北京")
        first.finish()
        self.app.processEvents()
        self.assertNotIn("获取", self.panel._weather_detail.text())
        self.assertIn("❌", self.panel._weather_detail.text())
        self.assertIsNone(self.panel._pending_weather)
        self.assertFalse(self.panel._weather_threads)
        self.assertIsNone(self.panel._weather_thread)
        self.assertTrue(self.select("北京").started)

    def test_constructor_failure_ends_loading_and_allows_retry(self):
        self.make_panel()
        with patch("core.main_panel.WeatherThread", side_effect=RuntimeError("offline construction failed")):
            self.panel._select_city("北京")
        self.assertIn("offline construction failed", self.panel._weather_detail.text())
        self.assertIsNone(self.panel._pending_weather)
        self.assertFalse(self.panel._weather_threads)
        self.assertIsNone(self.panel._weather_thread)
        self.mock_workers()
        self.assertTrue(self.select("北京").started)

    def test_start_failure_releases_unstarted_worker_and_allows_retry(self):
        self.make_panel()
        failed = DeferredWeather("北京")
        with patch("core.main_panel.WeatherThread", return_value=failed), \
                patch.object(failed, "start", side_effect=RuntimeError("offline start failed")):
            self.panel._select_city("北京")
        self.assertIn("offline start failed", self.panel._weather_detail.text())
        self.assertIsNone(self.panel._pending_weather)
        self.assertFalse(self.panel._weather_threads)
        self.assertIsNone(self.panel._weather_thread)
        self.mock_workers()
        self.assertTrue(self.select("北京").started)

    def test_unexpected_fetch_exception_becomes_one_failure_result(self):
        worker = WeatherThread("北京")
        results = []
        worker.done.connect(lambda *args: results.append(args))
        with patch("core.main_panel.fetch_weather", side_effect=RuntimeError("offline unexpected fetch error")):
            worker.run()
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0][0])
        self.assertFalse(results[0][1])
        self.assertIn("offline unexpected fetch error", results[0][2])

    def test_worker_preserves_city_force_and_cached_result(self):
        for force in (False, True):
            with self.subTest(force=force):
                data = weather("离线缓存")
                worker = WeatherThread("北京", force=force)
                results = []
                worker.done.connect(lambda *args: results.append(args))
                with patch("core.main_panel.fetch_weather", return_value=(data, True, None)) as fetch:
                    worker.run()
                fetch.assert_called_once_with("北京", force)
                self.assertEqual(results, [(data, True, None)])

    def test_real_qthreads_deliver_out_of_order_results_on_application_thread(self):
        self.make_panel()
        started = {city: threading.Event() for city in ("北京", "上海")}
        release = {city: threading.Event() for city in started}
        work_threads = []
        callback_threads = []

        def fetch(city, force):
            work_threads.append(QThread.currentThread())
            started[city].set()
            if not release[city].wait(5):
                return None, False, "offline test release deadline exceeded"
            return weather(city + "真实线程结果"), False, None

        receive = self.panel._on_weather_loaded

        def receive_on_main(*args):
            callback_threads.append(QThread.currentThread())
            receive(*args)

        live_workers = []
        with patch("core.main_panel.fetch_weather", side_effect=fetch), \
                patch.object(self.panel, "_on_weather_loaded", side_effect=receive_on_main):
            try:
                self.panel._select_city("北京")
                first = self.panel._weather_thread
                live_workers.append(first)
                self.assertTrue(started["北京"].wait(5), "Beijing worker did not start")
                self.panel._select_city("上海")
                second = self.panel._weather_thread
                live_workers.append(second)
                self.assertTrue(started["上海"].wait(5), "Shanghai worker did not start")
                self.assertEqual(self.panel._weather_threads, {first, second})
                release["上海"].set()
                self.wait_for(lambda: second not in self.panel._weather_threads)
                expected = self.panel._weather_detail.text()
                self.assertIn("📍 上海", expected)
                self.assertIn("上海真实线程结果", expected)
                self.assertIn(first, self.panel._weather_threads)
                release["北京"].set()
                self.wait_for(lambda: not self.panel._weather_threads)
                self.assertEqual(self.panel._weather_detail.text(), expected)
            finally:
                for event in release.values():
                    event.set()
                for worker in live_workers:
                    # Completed workers may already have been deleteLater()'d.
                    try:
                        worker.wait(5000)
                    except RuntimeError:
                        pass
                self.app.processEvents()
        self.assertEqual(callback_threads, [self.app.thread(), self.app.thread()])
        self.assertEqual(len(work_threads), 2)
        self.assertTrue(all(thread is not self.app.thread() for thread in work_threads))


if __name__ == "__main__":
    unittest.main()
