"""Real Qt checks for deferred scrolling; no model, network, or saved data."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import sys
import time
import unittest
from unittest.mock import patch

from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QScrollBar, QVBoxLayout, QWidget

from ui.chat_list import ChatList


class RecordingScrollBar(QScrollBar):
    """Keep the real scrollbar while observing explicit bottom-scroll calls."""

    def __init__(self):
        super().__init__(Qt.Orientation.Vertical)
        self.scroll_calls = []

    def setValue(self, value):
        self.scroll_calls.append((value, self.maximum()))
        super().setValue(value)


class ChatScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.windows = []
        self.callback_errors = []
        for patcher in (
            patch.object(sys, "excepthook", side_effect=self.capture_callback_error),
            patch("socket.socket.connect", side_effect=AssertionError("No network in scroll tests")),
            patch("socket.create_connection", side_effect=AssertionError("No network in scroll tests")),
            patch("subprocess.Popen", side_effect=AssertionError("No CLI in scroll tests")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.close_windows)

    def capture_callback_error(self, _exception_type, exception, _traceback):
        self.callback_errors.append(exception)

    def wait_until(self, predicate, message, timeout_ms=5000):
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(10)
        self.fail(f"{message}; callback errors: {self.callback_errors!r}")

    def pass_pending_scroll_deadline(self):
        # This barrier is longer than the existing 50 ms scroll delay. Wait for
        # its actual Qt event, allowing slower CI machines up to five seconds.
        barrier = QTimer()
        barrier.setSingleShot(True)
        barrier.setTimerType(Qt.TimerType.PreciseTimer)
        reached = []
        barrier.timeout.connect(lambda: reached.append(True))
        barrier.start(150)
        self.wait_until(lambda: bool(reached), "Qt event-loop barrier did not fire")

    def close_windows(self):
        for window in self.windows:
            if not sip.isdeleted(window):
                window.close()
                window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.pass_pending_scroll_deadline()

    def make_chat(self, parented=False):
        parent = QWidget() if parented else None
        chat = ChatList(parent)
        bar = RecordingScrollBar()
        chat.setVerticalScrollBar(bar)
        window = parent or chat
        if parent is not None:
            layout = QVBoxLayout(parent)
            layout.addWidget(chat)
        self.windows.append(window)
        window.resize(420, 220)
        window.show()
        self.wait_until(lambda: chat.isVisible() and chat.viewport().height() > 0,
                        "Chat viewport did not become visible")
        return chat, bar, parent

    @staticmethod
    def long_message(prefix):
        return "\n".join(f"{prefix} — line {index}" for index in range(80))

    def assert_at_bottom(self, bar):
        self.wait_until(lambda: bool(bar.scroll_calls) and bar.maximum() > 0
                        and bar.value() == bar.maximum(),
                        "Long conversation did not scroll to its current bottom")
        self.assertTrue(all(value == maximum for value, maximum in bar.scroll_calls))
        self.assertEqual(self.callback_errors, [])

    def test_long_message_scrolls_to_bottom_after_real_layout(self):
        chat, bar, _parent = self.make_chat()
        message = self.long_message("Long reply")
        bubble = chat.add_message(message)
        self.assert_at_bottom(bar)
        self.assertEqual(bubble._label.text(), message)
        self.assertFalse(bubble.is_user)
        self.assertEqual(len(bar.scroll_calls), 1)

    def test_replacing_latest_reply_scrolls_and_preserves_existing_bubble(self):
        chat, bar, _parent = self.make_chat()
        reply = chat.add_message(self.long_message("Original reply"))
        self.assert_at_bottom(bar)
        bar.setValue(0)
        bar.scroll_calls.clear()
        replacement = self.long_message("Replacement reply") * 2
        chat.replace_last_pet_message(replacement)
        self.assert_at_bottom(bar)
        self.assertEqual(chat._bubbles, [reply])
        self.assertEqual(reply._label.text(), replacement)

    def test_replacing_without_a_reply_appends_one_and_scrolls(self):
        chat, bar, _parent = self.make_chat()
        user_bubble = chat.add_message(self.long_message("User question"), is_user=True)
        self.assert_at_bottom(bar)
        bar.setValue(0)
        bar.scroll_calls.clear()
        fallback = self.long_message("First reply")
        chat.replace_last_pet_message(fallback)
        self.assert_at_bottom(bar)
        self.assertEqual(chat._bubbles[0], user_bubble)
        self.assertEqual(len(chat._bubbles), 2)
        self.assertFalse(chat._bubbles[-1].is_user)
        self.assertEqual(chat._bubbles[-1]._label.text(), fallback)

    def test_twelve_messages_in_one_burst_scroll_only_once(self):
        chat, bar, _parent = self.make_chat()
        for index in range(12):
            chat.add_message(f"Message {index}\nSecond line", is_user=index % 2 == 0)
        self.assert_at_bottom(bar)
        self.pass_pending_scroll_deadline()
        self.assertEqual(len(chat._bubbles), 12)
        self.assertEqual(len(bar.scroll_calls), 1)
        self.assertEqual(bar.value(), bar.maximum())
        self.assertEqual(self.callback_errors, [])

    def test_destroy_chat_before_pending_scroll_has_no_callback_error(self):
        chat, bar, _parent = self.make_chat()
        chat.add_message(self.long_message("Pending before direct deletion"))
        chat.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(sip.isdeleted(chat))
        self.assertTrue(sip.isdeleted(bar))
        self.pass_pending_scroll_deadline()
        self.assertEqual(self.callback_errors, [])
        self.assertEqual(bar.scroll_calls, [])

    def test_destroy_parent_before_pending_scroll_has_no_callback_error(self):
        chat, bar, parent = self.make_chat(parented=True)
        chat.add_message(self.long_message("Pending before parent deletion"))
        parent.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(sip.isdeleted(parent))
        self.assertTrue(sip.isdeleted(chat))
        self.assertTrue(sip.isdeleted(bar))
        self.pass_pending_scroll_deadline()
        self.assertEqual(self.callback_errors, [])
        self.assertEqual(bar.scroll_calls, [])

    def test_clear_then_append_scrolls_to_the_current_content(self):
        chat, bar, _parent = self.make_chat()
        removed = chat.add_message(self.long_message("Removed reply"))
        chat.clear_messages()
        replacement = chat.add_message(self.long_message("After clearing"), is_user=True)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(sip.isdeleted(removed))
        self.assert_at_bottom(bar)
        self.assertEqual(chat._bubbles, [replacement])
        self.assertTrue(replacement.is_user)
        self.assertEqual(replacement._label.text(), self.long_message("After clearing"))

    def test_close_hides_without_deleting_and_scroll_still_works_after_show(self):
        chat, bar, _parent = self.make_chat()
        chat.add_message(self.long_message("Reply before hiding"))
        chat.close()
        self.assertFalse(chat.isVisible())
        self.assertFalse(sip.isdeleted(chat))
        self.pass_pending_scroll_deadline()
        self.assertEqual(self.callback_errors, [])
        chat.show()
        self.wait_until(chat.isVisible, "Chat did not become visible again")
        bar.setValue(0)
        bar.scroll_calls.clear()
        chat.add_message(self.long_message("Reply after showing"))
        self.assert_at_bottom(bar)
        self.assertEqual(len(chat._bubbles), 2)


if __name__ == "__main__":
    unittest.main()
