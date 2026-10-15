"""Real Qt panel actions animate the pet without duplicating saved activity."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMovie
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from config import Config
from core import state_manager
from core.animation_manager import AnimationManager, AnimationState
from core.main_panel import MainPanel
from core.pet_window import PetWindow


ACTIONS = (
    ("🍚 喂食", "feed", AnimationState.INTERACT_WASH),
    ("🎾 玩耍", "play", AnimationState.IDLE_WALK),
    ("🤲 抚摸", "pet", AnimationState.INTERACT_WAG),
    ("💤 休息", "rest", AnimationState.IDLE_SLEEP),
)


class PetPanelAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="critter-pet-panel-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "state.json"
        self.path.write_text(json.dumps({"notes": [{"id": 1, "content": "保留便签"}],
                                         "future_field": {"keep": True}}), encoding="utf-8")
        for patcher in (
            patch.object(state_manager, "_STATE_FILE", str(self.path)),
            patch.object(Config, "ENABLE_AI_AGENT", False),
            patch.object(Config, "ANTHROPIC_API_KEY", ""),
            patch.object(AnimationManager, "INTERACTION_DURATION_MS", 10000),
            patch("core.main_panel.CLAUDE_CLI", "/missing/critter-offline-cli"),
            patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}),
            patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
            patch("socket.create_connection", side_effect=AssertionError("Network forbidden")),
            patch("subprocess.Popen", side_effect=AssertionError("CLI forbidden")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.pet = PetWindow()
        self.pet.show()
        self.panel = MainPanel(self.pet)
        self.panel._decay_timer.stop()
        self.panel._switch_tab(2)
        self.panel.show()
        self.app.processEvents()
        self.addCleanup(self.close_windows)

    def close_windows(self):
        self.panel._timer_feature.countdown.timer.stop()
        self.panel.close()
        self.pet.close()
        self.panel.deleteLater()
        self.pet.deleteLater()
        self.app.processEvents()

    def click_action(self, label):
        button = next(button for button in self.panel.findChildren(QPushButton)
                      if button.text() == label)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def assert_saved_once(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        actions = [event["kind"] for events in data["pet_interactions"].values() for event in events]
        self.assertEqual(actions, [action[1] for action in ACTIONS])
        self.assertEqual(data["notes"], [{"id": 1, "content": "保留便签"}])
        self.assertEqual(data["future_field"], {"keep": True})

    def test_four_buttons_animate_and_record_each_action_once(self):
        for label, _kind, state in ACTIONS:
            with self.subTest(action=label):
                self.click_action(label)
                self.assertEqual(self.pet.animation_manager.current_state, state)
                self.assertEqual(self.pet.pet_label.movie().state(), QMovie.MovieState.Running)
        self.assert_saved_once()

    def test_panel_actions_do_not_replace_active_alarm(self):
        self.panel._timer_feature._on_timeout()
        for label, _kind, _state in ACTIONS:
            self.click_action(label)
            self.assertEqual(self.pet.animation_manager.current_state, AnimationState.ALERT_RUN)
            self.assertTrue(self.pet.alert_timer.isActive())
        self.assert_saved_once()
        self.pet.stop_alert_animation()
        self.assertEqual(self.pet.animation_manager.current_state, AnimationState.IDLE_SLEEP)

    def test_panel_actions_remain_usable_without_desktop_window(self):
        self.panel.pet_window = None
        for label, _kind, _state in ACTIONS:
            self.click_action(label)
        self.assert_saved_once()


if __name__ == "__main__":
    unittest.main()
