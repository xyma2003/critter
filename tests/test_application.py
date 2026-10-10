"""Run startup and quit safeguards in isolated, offscreen Qt processes.

These tests use temporary data and real event loops/message boxes. Model calls,
network connections and project dotenv loading are disabled in every child.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class ApplicationTests(unittest.TestCase):
    def run_qt(self, source):
        with tempfile.TemporaryDirectory(prefix="critter-application-") as temporary:
            env = os.environ.copy()
            for key in list(env):
                if key.startswith(("ANTHROPIC_", "OPENAI_")):
                    env.pop(key)
            env.update({
                "QT_QPA_PLATFORM": "offscreen",
                "PYTHON_DOTENV_DISABLED": "1",
                "CRITTER_DATA_DIR": str(Path(temporary) / "isolated data"),
                "PYTHONPATH": str(PROJECT),
                "PYTHONDONTWRITEBYTECODE": "1",
            })
            prefix = """
                import json
                import os
                from pathlib import Path
                import socket
                import traceback
                from unittest import mock

                def no_network(*args, **kwargs):
                    raise AssertionError("Network access is forbidden in this test")

                socket.socket.connect = no_network
                socket.socket.connect_ex = no_network
                socket.create_connection = no_network
                from config import Config, STATE_FILE
                Config.ENABLE_AI_AGENT = False
                Config.ANTHROPIC_API_KEY = ""
                from PyQt6.QtCore import QTimer
                from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget
                state_path = Path(STATE_FILE)
            """
            result = subprocess.run(
                [sys.executable, "-B", "-c", textwrap.dedent(prefix) + textwrap.dedent(source)],
                cwd=temporary, env=env, capture_output=True, text=True,
                encoding="utf-8", timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("APPLICATION_TEST_OK", result.stdout)

    def test_real_quit_event_can_be_cancelled_then_allowed(self):
        self.run_qt("""
            from core.application import CritterApplication
            app = CritterApplication([])
            app.setQuitOnLastWindowClosed(False)
            window = QWidget()
            window.show()
            calls = []
            continued = []

            def continue_after_cancel():
                continued.append(True)
                QApplication.quit()

            def confirm_exit():
                calls.append(True)
                if len(calls) == 1:
                    QTimer.singleShot(25, continue_after_cancel)
                    return False
                return True

            app.confirm_exit = confirm_exit
            QTimer.singleShot(0, QApplication.quit)
            QTimer.singleShot(5000, lambda: app.exit(98))
            result = app.exec()
            assert result == 0, result
            assert len(calls) == 2, calls
            assert continued == [True], continued
            assert not state_path.exists()
            print("APPLICATION_TEST_OK")
        """)

    def test_unreadable_startup_close_never_constructs_panel_or_overwrites_state(self):
        self.run_qt("""
            import main
            original = b'{"notes": [{"id": "must survive"}], "theme": "dark"}'
            state_path.parent.mkdir(parents=True)
            state_path.write_bytes(original)
            real_open = open
            real_exec = QMessageBox.exec
            dialogs = []

            def fail_state_read(file, mode="r", *args, **kwargs):
                if os.fspath(file) == str(state_path) and "r" in mode:
                    raise PermissionError("initial data read denied")
                return real_open(file, mode, *args, **kwargs)

            def close_startup_dialog(dialog):
                dialogs.append(dialog.text())
                button = dialog.button(QMessageBox.StandardButton.Close)
                assert button is not None
                QTimer.singleShot(0, button.click)
                return real_exec(dialog)

            with mock.patch("builtins.open", side_effect=fail_state_read), \\
                    mock.patch.object(main, "MainPanel") as panel, \\
                    mock.patch.object(main, "PetWindow") as pet, \\
                    mock.patch.object(QMessageBox, "exec", close_startup_dialog):
                result = main.main()
                panel.assert_not_called()
                pet.assert_not_called()
            assert result == 1, result
            assert len(dialogs) == 1 and "Critter 尚未启动" in dialogs[0], dialogs
            assert state_path.read_bytes() == original
            assert list(state_path.parent.iterdir()) == [state_path]
            print("APPLICATION_TEST_OK")
        """)

    def run_main_exit_scenario(self, choice):
        self.run_qt(f"choice = {choice!r}\n" + textwrap.dedent("""
            import main
            from core import state_manager as state
            from core.application import CritterApplication

            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps({
                "notes": [{"id": "old note", "body": "preserve on discard"}],
                "future_field": {"keep": True},
            }), encoding="utf-8")
            pending_notes = [{"id": "new note", "body": "save on retry"}]
            real_replace = state.os.replace
            real_dialog_exec = QMessageBox.exec
            fail_writes = [False]
            old_bytes = []
            continued = []
            dialogs = []
            backups = []
            failures = []
            corrupted_during_retry = b'{"notes": ["damaged while exit dialog was open"'

            def guarded(callback):
                def run():
                    try:
                        callback()
                    except BaseException:
                        failures.append(traceback.format_exc())
                        QApplication.instance().exit(97)
                return run

            def maybe_fail_replace(*args, **kwargs):
                if fail_writes[0]:
                    raise OSError("injected atomic replacement failure")
                return real_replace(*args, **kwargs)

            def continue_after_cancel():
                continued.append(True)
                assert state_path.read_bytes() == old_bytes[0]
                assert state.load_notes() == pending_notes
                assert "notes" in state.get_storage_status().pending_fields
                QApplication.quit()

            def drive_dialog(dialog):
                if choice == "retry_corruption" and "备份位置：" in dialog.text():
                    status = state.get_storage_status()
                    assert status.recovered_from_memory, status
                    backup = Path(status.recovery_backup)
                    assert backup.read_bytes() == corrupted_during_retry
                    assert str(backup) in dialog.text(), dialog.text()
                    assert len(dialogs) == 1, dialogs
                    backups.append(backup)
                    dialogs.append(dialog.text())
                    buttons = [button for button in dialog.buttons()
                               if button.text() == "我已知悉，继续退出"]
                    assert len(buttons) == 1
                    QTimer.singleShot(0, buttons[0].click)
                    return real_dialog_exec(dialog)
                assert "部分修改只保留在当前会话" in dialog.text(), dialog.text()
                dialogs.append(dialog.text())
                first_cancel = choice == "retry" and len(dialogs) == 1
                label = ("取消退出" if first_cancel else
                         "重试保存" if choice.startswith("retry") else "不保存并退出")
                buttons = [button for button in dialog.buttons() if button.text() == label]
                assert len(buttons) == 1, [button.text() for button in dialog.buttons()]
                assert dialog.defaultButton().text() == "取消退出"

                def click():
                    if label == "重试保存":
                        if choice == "retry_corruption":
                            # Introduce corruption only after the quit-save has
                            # failed, immediately before the actual retry.
                            state_path.write_bytes(corrupted_during_retry)
                        fail_writes[0] = False
                    buttons[0].click()

                QTimer.singleShot(0, guarded(click))
                result = real_dialog_exec(dialog)
                if first_cancel:
                    QTimer.singleShot(25, guarded(continue_after_cancel))
                return result

            def begin_failure():
                old_bytes.append(state_path.read_bytes())
                fail_writes[0] = True
                assert state.save_notes(pending_notes) is False
                assert state_path.read_bytes() == old_bytes[0]
                QApplication.quit()

            class TestApplication(CritterApplication):
                def exec(self):
                    QTimer.singleShot(0, guarded(begin_failure))
                    QTimer.singleShot(5000, lambda: self.exit(98))
                    return super().exec()

            with mock.patch.object(main, "CritterApplication", TestApplication), \\
                    mock.patch.object(state.os, "replace", maybe_fail_replace), \\
                    mock.patch.object(QMessageBox, "exec", drive_dialog):
                result = main.main()
            assert not failures, failures
            assert result == 0, result
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            assert saved["future_field"] == {"keep": True}, saved
            if choice.startswith("retry"):
                assert continued == ([True] if choice == "retry" else []), continued
                assert len(dialogs) == 2, dialogs
                assert saved["notes"] == pending_notes, saved
                assert "window_position" in saved and "last_seen" in saved, saved
                assert not state.get_storage_status().pending_fields
                assert state.get_storage_status().error is None
                if choice == "retry_corruption":
                    assert len(backups) == 1, backups
                    assert backups[0].read_bytes() == corrupted_during_retry
                    assert state.get_storage_status().recovery_backup is None
            else:
                assert not continued, continued
                assert len(dialogs) == 1, dialogs
                assert state_path.read_bytes() == old_bytes[0]
                assert saved["notes"] == [{"id": "old note", "body": "preserve on discard"}]
                assert "notes" in state.get_storage_status().pending_fields
            print("APPLICATION_TEST_OK")
        """))

    def test_main_cancel_exit_then_retry_saves_and_quits(self):
        self.run_main_exit_scenario("retry")

    def test_main_explicit_discard_quits_while_retaining_previous_disk_data(self):
        self.run_main_exit_scenario("discard")

    def test_corruption_during_exit_retry_requires_backup_acknowledgment(self):
        self.run_main_exit_scenario("retry_corruption")

    def test_corruption_discovered_on_exit_requires_recovery_acknowledgment(self):
        self.run_qt("""
            import main
            from core import state_manager as state
            from core.application import CritterApplication

            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps({
                "notes": [{"id": "keep from the loaded snapshot"}],
                "future_field": {"keep": True},
            }), encoding="utf-8")
            corrupted = b'{"notes": ["damaged just before exit"'
            real_dialog_exec = QMessageBox.exec
            backups = []
            dialogs = []
            continued = []
            failures = []

            def guarded(callback):
                def run():
                    try:
                        callback()
                    except BaseException:
                        failures.append(traceback.format_exc())
                        QApplication.instance().exit(97)
                return run

            def continue_after_return():
                continued.append(True)
                assert state.get_storage_status().recovery_backup
                assert state.load_notes() == [{"id": "keep from the loaded snapshot"}]
                QApplication.quit()

            def drive_recovery_dialog(dialog):
                status = state.get_storage_status()
                assert status.recovery_backup, status
                assert status.recovered_from_memory, status
                backup = Path(status.recovery_backup)
                assert backup.read_bytes() == corrupted
                assert str(backup) in dialog.text(), dialog.text()
                backups.append(backup)
                dialogs.append(dialog.text())
                label = "返回应用" if len(dialogs) == 1 else "我已知悉，继续退出"
                buttons = [button for button in dialog.buttons() if button.text() == label]
                assert len(buttons) == 1, [button.text() for button in dialog.buttons()]
                assert dialog.defaultButton().text() == "返回应用"
                QTimer.singleShot(0, buttons[0].click)
                result = real_dialog_exec(dialog)
                if len(dialogs) == 1:
                    QTimer.singleShot(25, guarded(continue_after_return))
                return result

            def corrupt_then_quit():
                assert state.load_notes() == [{"id": "keep from the loaded snapshot"}]
                state_path.write_bytes(corrupted)
                QApplication.quit()

            class TestApplication(CritterApplication):
                def exec(self):
                    QTimer.singleShot(0, guarded(corrupt_then_quit))
                    QTimer.singleShot(5000, lambda: self.exit(98))
                    return super().exec()

            with mock.patch.object(main, "CritterApplication", TestApplication), \\
                    mock.patch.object(QMessageBox, "exec", drive_recovery_dialog):
                result = main.main()
            assert not failures, failures
            assert result == 0, result
            assert continued == [True], continued
            assert len(dialogs) == 2, dialogs
            assert backups[0] == backups[1], backups
            assert backups[0].read_bytes() == corrupted
            assert state.get_storage_status().recovery_backup is None
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            assert saved["notes"] == [{"id": "keep from the loaded snapshot"}], saved
            assert saved["future_field"] == {"keep": True}, saved
            print("APPLICATION_TEST_OK")
        """)


if __name__ == "__main__":
    unittest.main()
