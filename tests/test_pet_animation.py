"""Exercise shipped GIFs and real Qt timers without user data or model calls."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from hashlib import sha256
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PyQt6 import sip
from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QImageReader, QMovie
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from config import ASSETS_DIR, Config
from core import state_manager
from core.animation_manager import AnimationManager, AnimationState
from core.pet_window import PetWindow


class PetAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="critter-animation-test-")
        self.addCleanup(self.temp.cleanup)
        self.pet = None
        for patcher in (
            patch.object(state_manager, "_STATE_FILE", str(Path(self.temp.name) / "state.json")),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
            patch("socket.socket.connect", side_effect=AssertionError("No network in animation tests")),
            patch("socket.create_connection", side_effect=AssertionError("No network in animation tests")),
            patch("subprocess.Popen", side_effect=AssertionError("No CLI in animation tests")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.close_pet)

    def make_pet(self):
        self.pet = PetWindow()
        self.pet.show()
        self.app.processEvents()
        return self.pet

    def close_pet(self):
        if self.pet is None:
            return
        self.pet.animation_manager.stop()
        if self.pet.alert_timer is not None:
            self.pet.alert_timer.stop()
        self.pet.speech_bubble._hide_timer.stop()
        self.pet.speech_bubble.close()
        self.pet.close()
        self.pet.speech_bubble.deleteLater()
        self.pet.deleteLater()
        self.app.processEvents()
        self.pet = None

    def wait_until(self, condition, timeout_ms=1600):
        deadline = time.monotonic() + timeout_ms / 1000
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), "Qt event did not arrive before the timeout")

    def assert_stopped(self, movie):
        if not sip.isdeleted(movie):
            self.assertEqual(movie.state(), QMovie.MovieState.NotRunning)

    def active_movie(self):
        movie = self.pet.pet_label.movie()
        self.assertIsInstance(movie, QMovie)
        self.assertTrue(movie.isValid())
        self.assertEqual(movie.state(), QMovie.MovieState.Running)
        return movie

    @staticmethod
    def image_digest(movie):
        image = movie.currentImage()
        if image.isNull():
            return None
        return sha256(image.constBits().asstring(image.sizeInBytes())).hexdigest()

    def painted_size(self):
        image = self.pet.pet_label.grab().toImage()
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        points = [(x, y) for y in range(image.height()) for x in range(image.width())
                  if image.pixelColor(x, y).alpha() > 0]
        self.assertTrue(points, "The animated pet was not painted")
        return (max(x for x, _ in points) - min(x for x, _ in points) + 1,
                max(y for _, y in points) - min(y for _, y in points) + 1)

    def test_every_shipped_state_advances_real_frames_with_different_pixels(self):
        self.make_pet()
        for state in AnimationState:
            with self.subTest(state=state.value):
                resource = ASSETS_DIR / "animations" / Config.DEFAULT_PET / f"{state.value}.gif"
                self.assertTrue(resource.is_file(), f"Missing animation: {resource}")
                self.pet.animation_manager.set_state(state)
                movie = self.active_movie()
                self.assertEqual(Path(movie.fileName()).resolve(), resource.resolve())
                self.assertGreater(movie.frameCount(), 1)
                self.assertEqual(movie.loopCount(), -1)
                frames = {movie.currentFrameNumber()}
                pixels = {self.image_digest(movie)}

                def record_frame(number):
                    frames.add(number)
                    pixels.add(self.image_digest(movie))

                movie.frameChanged.connect(record_frame)
                try:
                    self.wait_until(lambda: len(frames) > 1 and len(pixels - {None}) > 1)
                finally:
                    movie.frameChanged.disconnect(record_frame)
                image = movie.currentImage()
                self.assertTrue(image.hasAlphaChannel())
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
                self.assertEqual(image.pixelColor(image.width() - 1, image.height() - 1).alpha(), 0)

    def test_all_animation_paths_resolve_after_changing_working_directory(self):
        previous = Path.cwd()
        os.chdir(self.temp.name)
        try:
            self.make_pet()
            for state in AnimationState:
                self.pet.animation_manager.set_state(state)
                movie = self.active_movie()
                self.assertTrue(Path(movie.fileName()).is_absolute())
                self.assertEqual(Path(movie.fileName()).resolve(),
                                 (ASSETS_DIR / "animations" / Config.DEFAULT_PET / f"{state.value}.gif").resolve())
        finally:
            os.chdir(previous)

    def test_missing_gif_clears_and_stops_previous_movie_then_can_recover(self):
        self.make_pet()
        old_movie = self.active_movie()
        with patch("core.pet_window.ASSETS_DIR", Path(self.temp.name) / "missing"):
            self.pet.animation_manager.set_state(AnimationState.INTERACT_WASH)
            self.app.processEvents()
            self.assertIsNone(self.pet.pet_label.movie())
            self.assert_stopped(old_movie)
            self.assertTrue(self.pet.pet_label.text())
            self.assertTrue(self.pet.pet_label.pixmap().isNull())
            fallback = self.pet.pet_label.text()
            QTest.qWait(160)
            self.assertEqual(self.pet.pet_label.text(), fallback)
            self.assertIsNone(self.pet.pet_label.movie())
        self.pet.animation_manager.set_state(AnimationState.IDLE_SLEEP)
        self.assertIsNot(self.active_movie(), old_movie)

    def test_corrupt_gif_clears_previous_frame_and_shows_state_fallback(self):
        self.make_pet()
        old_movie = self.active_movie()
        root = Path(self.temp.name) / "broken-assets"
        directory = root / "animations" / Config.DEFAULT_PET
        directory.mkdir(parents=True)
        (directory / "alert_run.gif").write_bytes(b"not a GIF file")
        with patch("core.pet_window.ASSETS_DIR", root):
            self.pet.animation_manager.set_state(AnimationState.ALERT_RUN)
            self.app.processEvents()
            self.assertIsNone(self.pet.pet_label.movie())
            self.assert_stopped(old_movie)
            self.assertTrue(self.pet.pet_label.text())
            self.assertTrue(self.pet.pet_label.pixmap().isNull())
            self.assertEqual(self.pet.animation_manager.current_state, AnimationState.ALERT_RUN)

    def test_switching_stops_old_movie_and_attaches_only_current_movie(self):
        self.make_pet()
        old_movies = []
        for state in (AnimationState.INTERACT_WAG, AnimationState.IDLE_WALK,
                      AnimationState.INTERACT_WASH, AnimationState.IDLE_SLEEP):
            old_movies.append(self.active_movie())
            self.pet.animation_manager.set_state(state)
            current = self.active_movie()
            self.app.processEvents()
            self.assertTrue(all(current is not previous for previous in old_movies))
            for previous in old_movies:
                self.assert_stopped(previous)

    def test_decoder_error_falls_back_only_for_the_current_movie(self):
        self.make_pet()
        previous = self.active_movie()
        self.pet.animation_manager.set_state(AnimationState.IDLE_WALK)
        current = self.active_movie()
        error = QImageReader.ImageReaderError.InvalidDataError
        # A retired decoder can still have a queued error before deleteLater.
        if not sip.isdeleted(previous):
            previous.error.emit(error)
        self.assertIs(self.pet.pet_label.movie(), current)
        self.assertEqual(current.state(), QMovie.MovieState.Running)
        current.error.emit(error)
        self.assertIsNone(self.pet.pet_label.movie())
        self.assertTrue(self.pet.pet_label.text())
        self.assertTrue(self.pet.pet_label.pixmap().isNull())
        self.assert_stopped(current)

    def test_repeated_interactions_restart_the_return_timer(self):
        self.make_pet()
        manager = self.pet.animation_manager
        with patch.object(AnimationManager, "INTERACTION_DURATION_MS", 250), \
                patch("core.animation_manager.random.choice", return_value=AnimationState.INTERACT_WAG):
            manager.trigger_interact()
            QTest.qWait(140)
            manager.trigger_interact()
            QTest.qWait(160)
            # The first interaction's original deadline has passed, but the
            # second interaction still owns a complete interval.
            self.assertEqual(manager.current_state, AnimationState.INTERACT_WAG)
            self.wait_until(lambda: manager.current_state == AnimationState.IDLE_SLEEP, 500)

    def test_idle_timer_does_not_replace_interaction_or_alert(self):
        self.make_pet()
        manager = self.pet.animation_manager
        with patch("core.animation_manager.random.choice", return_value=AnimationState.INTERACT_WASH):
            manager.trigger_interact()
        manager._switch_idle_state()
        self.assertEqual(manager.current_state, AnimationState.INTERACT_WASH)
        self.pet.trigger_alert_animation()
        manager._switch_idle_state()
        self.assertEqual(manager.current_state, AnimationState.ALERT_RUN)
        manager.trigger_interact()
        self.assertEqual(manager.current_state, AnimationState.ALERT_RUN)

    def test_temporary_rest_and_walk_interactions_are_not_preempted_by_idle_timer(self):
        self.make_pet()
        manager = self.pet.animation_manager
        with patch.object(AnimationManager, "INTERACTION_DURATION_MS", 100):
            for state in (AnimationState.IDLE_SLEEP, AnimationState.IDLE_WALK):
                manager.trigger_interact(state)
                opposite = (AnimationState.IDLE_WALK if state == AnimationState.IDLE_SLEEP
                            else AnimationState.IDLE_SLEEP)
                with patch("core.animation_manager.random.choice", return_value=opposite):
                    manager._switch_idle_state()
                self.assertEqual(manager.current_state, state)
                self.assertTrue(manager.interaction_timer.isActive())
        self.wait_until(lambda: manager.current_state == AnimationState.IDLE_SLEEP, 500)

    def test_interaction_deadline_cannot_override_later_alert(self):
        self.make_pet()
        manager = self.pet.animation_manager
        with patch.object(AnimationManager, "INTERACTION_DURATION_MS", 100):
            manager.trigger_interact()
            self.pet.trigger_alert_animation()
            QTest.qWait(180)
        self.assertEqual(manager.current_state, AnimationState.ALERT_RUN)
        self.assertTrue(self.pet.alert_timer.isActive())
        self.active_movie()

    def test_alert_scales_animation_and_stop_restores_idle_size_without_movement(self):
        self.make_pet()
        self.pet.move(120, 100)
        old_movie = self.active_movie()
        self.pet.trigger_alert_animation()
        expected = QSize(*(int(value * Config.PET_SCALE_ALERT) for value in Config.PET_SIZE))
        self.assertEqual(self.pet.size(), expected)
        self.assertEqual(self.pet.pet_label.size(), expected)
        self.active_movie()
        self.assert_stopped(old_movie)
        timer = self.pet.alert_timer
        alert_movie = self.active_movie()
        self.pet.stop_alert_animation()
        self.app.processEvents()
        self.assertEqual(self.pet.size(), QSize(*Config.PET_SIZE))
        self.assertEqual(self.pet.pet_label.size(), QSize(*Config.PET_SIZE))
        self.active_movie()
        self.assertEqual(self.pet.animation_manager.current_state, AnimationState.IDLE_SLEEP)
        self.assert_stopped(alert_movie)
        if not sip.isdeleted(timer):
            self.assertFalse(timer.isActive())
        stopped_position = QPoint(self.pet.pos())
        QTest.qWait(140)
        self.assertEqual(self.pet.pos(), stopped_position)

    def test_painted_animation_scales_with_label_without_losing_transparency(self):
        self.make_pet()
        movie = self.active_movie()
        movie.setPaused(True)
        normal = self.painted_size()
        self.pet.resize(300, 300)
        self.pet.pet_label.resize(300, 300)
        enlarged = self.painted_size()
        self.assertEqual(self.pet.pet_label.size(), QSize(300, 300))
        self.assertIs(self.pet.pet_label.movie(), movie)
        for before, after in zip(normal, enlarged):
            self.assertAlmostEqual(after / before, 2.0, delta=0.12)
        self.pet.resize(*Config.PET_SIZE)
        self.pet.pet_label.resize(*Config.PET_SIZE)
        self.assertEqual(self.painted_size(), normal)

    def test_double_click_stops_alert_and_final_release_does_not_start_an_interaction(self):
        self.make_pet()
        self.pet.trigger_alert_animation()
        QTest.mouseDClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertEqual(self.pet.animation_manager.current_state, AnimationState.IDLE_SLEEP)
        QTest.mouseRelease(self.pet, Qt.MouseButton.LeftButton)
        self.assertEqual(self.pet.animation_manager.current_state, AnimationState.IDLE_SLEEP)
        QTest.mouseClick(self.pet, Qt.MouseButton.LeftButton)
        self.assertIn(self.pet.animation_manager.current_state,
                      (AnimationState.INTERACT_WASH, AnimationState.INTERACT_WAG))

    def test_alert_movement_stays_inside_screen_even_when_pet_is_larger(self):
        self.make_pet()
        self.pet.move(-100, 900)
        with patch("core.pet_window.ScreenUtils.get_screen_size", return_value=(640, 480)):
            self.pet.trigger_alert_animation()
            self.assertGreaterEqual(self.pet.x(), 0)
            self.assertGreaterEqual(self.pet.y(), 0)
            self.assertLessEqual(self.pet.x(), 640 - self.pet.width())
            self.assertLessEqual(self.pet.y(), 480 - self.pet.height())
            for _ in range(20):
                self.pet._move_randomly()
                self.assertGreaterEqual(self.pet.x(), 0)
                self.assertGreaterEqual(self.pet.y(), 0)
                self.assertLessEqual(self.pet.x(), 640 - self.pet.width())
                self.assertLessEqual(self.pet.y(), 480 - self.pet.height())
        with patch("core.pet_window.ScreenUtils.get_screen_size", return_value=(100, 100)):
            self.pet._move_randomly()
            self.assertEqual(self.pet.pos(), QPoint(0, 0))

    def test_repeated_alerts_leave_no_old_active_movement_timers(self):
        self.make_pet()
        timers = []
        for _ in range(5):
            self.pet.trigger_alert_animation()
            current = self.pet.alert_timer
            self.assertTrue(current.isActive())
            self.assertIs(current.parent(), self.pet)
            for previous in timers:
                if previous is not current and not sip.isdeleted(previous):
                    self.assertFalse(previous.isActive())
            timers.append(current)
        self.pet.stop_alert_animation()
        self.app.processEvents()
        for timer in timers:
            if not sip.isdeleted(timer):
                self.assertFalse(timer.isActive())

    def test_manager_stop_cancels_idle_and_pending_interaction_return(self):
        self.make_pet()
        manager = self.pet.animation_manager
        with patch.object(AnimationManager, "INTERACTION_DURATION_MS", 80):
            manager.trigger_interact()
            state = manager.current_state
            manager.stop()
            self.assertFalse(manager.state_timer.isActive())
            QTest.qWait(150)
        self.assertEqual(manager.current_state, state)

    def test_window_close_stops_movie_and_alert_timer(self):
        self.make_pet()
        self.pet.trigger_alert_animation()
        timer = self.pet.alert_timer
        movie = self.active_movie()
        self.pet.close()
        self.app.processEvents()
        self.assert_stopped(movie)
        if not sip.isdeleted(timer):
            self.assertFalse(timer.isActive())
        self.assertFalse(self.pet.animation_manager.state_timer.isActive())


if __name__ == "__main__":
    unittest.main()
