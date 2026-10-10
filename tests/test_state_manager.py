"""Exercise storage failures using temporary state and no Qt or model calls.

Each test imports a fresh storage module with a temporary config, so no test
reads the user's state file or inherits a previous test's pending writes.
"""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock
import uuid


SOURCE = Path(__file__).resolve().parents[1] / "core" / "state_manager.py"


class StateManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="critter-storage-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.state_path = self.root / "状态 data" / "state.json"
        self.storage = self.fresh_storage()

    def fresh_storage(self, path=None):
        """Give module globals the same isolation as a restarted process."""
        name = "_critter_state_test_" + uuid.uuid4().hex
        config = types.ModuleType("config")
        config.STATE_FILE = str(path or self.state_path)
        config.Config = types.SimpleNamespace(NEWS_CACHE_DURATION=3600)
        spec = importlib.util.spec_from_file_location(name, SOURCE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        with mock.patch.dict(sys.modules, {"config": config}):
            spec.loader.exec_module(module)
        return module

    def write_fixture(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
        self.state_path.write_bytes(raw)
        return raw

    def assert_clean_status(self, storage=None):
        status = (storage or self.storage).get_storage_status()
        self.assertEqual(status.path, str(self.state_path))
        self.assertEqual(status.pending_fields, ())
        self.assertIsNone(status.error)

    def test_new_directory_is_created_only_when_saving_and_survives_restart(self):
        self.assertTrue(self.storage.initialize_storage())
        self.assertEqual(self.storage._load_state(), {})
        self.assertFalse(self.state_path.parent.exists())
        self.assertTrue(self.storage.save_settings({"pet_name": "豆包"}))
        self.assertTrue(self.storage.save_notes([{"id": "n1", "body": "明日计划"}]))
        self.assertTrue(self.storage.save_theme("dark"))

        restarted = self.fresh_storage()
        self.assertTrue(restarted.initialize_storage())
        self.assertEqual(restarted.load_settings()["pet_name"], "豆包")
        self.assertEqual(restarted.load_notes(), [{"id": "n1", "body": "明日计划"}])
        self.assertEqual(restarted.load_theme(), "dark")
        self.assert_clean_status(restarted)

    def test_save_wrappers_return_success_and_do_not_drop_other_fields(self):
        self.write_fixture({"future_field": {"keep": True}})
        writers = (
            (self.storage.save_chat_history, ([{"role": "user", "content": "hi"}],)),
            (self.storage.save_timer_state, ("2026-10-10T12:30:00", True)),
            (self.storage.save_window_position, (120, 230)),
            (self.storage.save_news_cache, ([{"title": "fixture"}],)),
            (self.storage.save_pet_stats, (70.0, 80.0, 90.0)),
            (self.storage.save_notes, ([{"id": "note"}],)),
            (self.storage.save_chat_sessions, ([{"id": "session"}],)),
            (self.storage.save_theme, ("dark",)),
            (self.storage.save_settings, ({"pet_name": "小狗"},)),
        )
        for writer, args in writers:
            with self.subTest(writer=writer.__name__):
                self.assertIs(writer(*args), True)
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["future_field"], {"keep": True})
        self.assertEqual(set(saved), {
            "future_field", "chat_history", "timer", "window_position",
            "news_cache", "pet_stats", "notes", "chat_sessions", "theme", "settings",
        })

    def test_replace_failure_keeps_original_bytes_and_retries_all_pending_fields(self):
        original = self.write_fixture({"theme": "light", "notes": [{"id": "old"}],
                                       "unknown": [1, 2, 3]})
        self.assertTrue(self.storage.initialize_storage())
        pending_notes = [{"id": "new", "body": "待保存"}]
        with mock.patch.object(self.storage.os, "replace", side_effect=OSError("disk full")):
            self.assertFalse(self.storage.save_notes(pending_notes))
            self.assertFalse(self.storage.save_settings({"pet_name": "团子"}))
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertEqual(list(self.state_path.parent.iterdir()), [self.state_path])
        status = self.storage.get_storage_status()
        self.assertEqual(set(status.pending_fields), {"notes", "settings"})
        self.assertTrue(status.error)
        self.assertEqual(self.storage.load_notes(), pending_notes)
        self.assertEqual(self.storage.load_settings()["pet_name"], "团子")
        # A caller changing its input after a failed save must not mutate the
        # only in-memory copy that will be retried.
        pending_notes[0]["body"] = "caller mutation"
        self.assertEqual(self.storage.load_notes()[0]["body"], "待保存")

        self.assertTrue(self.storage.retry_pending_saves())
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["notes"], [{"id": "new", "body": "待保存"}])
        self.assertEqual(saved["settings"], {"pet_name": "团子"})
        self.assertEqual(saved["unknown"], [1, 2, 3])
        self.assertEqual(saved["theme"], "light")
        self.assert_clean_status()
        self.assertEqual(self.fresh_storage().load_notes(), saved["notes"])

    def test_later_successful_save_flushes_latest_pending_value_with_other_fields(self):
        original = self.write_fixture({"notes": [{"id": "keep"}], "theme": "light"})
        with mock.patch.object(self.storage.os, "replace", side_effect=PermissionError("locked")):
            self.assertFalse(self.storage.save_settings({"pet_name": "first"}))
            self.assertFalse(self.storage.save_settings({"pet_name": "latest"}))
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertTrue(self.storage.save_theme("dark"))
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"notes": [{"id": "keep"}], "theme": "dark",
                                 "settings": {"pet_name": "latest"}})
        self.assert_clean_status()

    def test_fsync_failure_cannot_truncate_original_and_cleans_temporary_file(self):
        original = self.write_fixture({"notes": [{"id": "precious"}]})
        self.assertTrue(self.storage.initialize_storage())
        with mock.patch.object(self.storage.os, "fsync", side_effect=OSError("I/O failure")):
            self.assertFalse(self.storage.save_theme("dark"))
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertEqual(list(self.state_path.parent.iterdir()), [self.state_path])
        self.assertEqual(self.storage.get_storage_status().pending_fields, ("theme",))
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.fresh_storage().load_notes(), [{"id": "precious"}])
        self.assert_clean_status()

    def test_failed_first_write_does_not_leave_an_empty_state_file(self):
        with mock.patch.object(self.storage.os, "replace", side_effect=OSError("disk full")):
            self.assertFalse(self.storage.save_notes([{"id": "pending"}]))
        self.assertFalse(self.state_path.exists())
        self.assertEqual(list(self.state_path.parent.iterdir()), [])
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.fresh_storage().load_notes(), [{"id": "pending"}])

    def test_serialization_failure_is_reported_without_changing_the_disk(self):
        original = self.write_fixture({"notes": [{"id": "keep"}]})
        self.assertFalse(self.storage.save_field("extension", {"bad": object()}))
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertEqual(list(self.state_path.parent.iterdir()), [self.state_path])
        self.assertEqual(self.storage.get_storage_status().pending_fields, ("extension",))
        self.assertTrue(self.storage.get_storage_status().error)
        self.assertFalse(self.storage.retry_pending_saves())
        self.assertTrue(self.storage.save_field("extension", {"ok": "serializable"}))
        self.assertEqual(self.fresh_storage()._load_state(), {
            "notes": [{"id": "keep"}], "extension": {"ok": "serializable"},
        })
        self.assert_clean_status()

    def test_concurrent_field_updates_preserve_every_writer(self):
        self.write_fixture({"notes": [{"id": "keep"}]})
        writer_count = 24
        start = threading.Barrier(writer_count)

        def save(index):
            start.wait(timeout=10)
            return self.storage.save_field(f"worker_{index}", {"value": index})

        with ThreadPoolExecutor(max_workers=writer_count) as pool:
            results = list(pool.map(save, range(writer_count)))
        self.assertEqual(results, [True] * writer_count)
        expected = {f"worker_{i}": {"value": i} for i in range(writer_count)}
        expected["notes"] = [{"id": "keep"}]
        self.assertEqual(self.fresh_storage()._load_state(), expected)
        self.assert_clean_status()

    def test_patched_state_path_has_independent_cache_and_pending_updates(self):
        original = self.write_fixture({"notes": [{"id": "first file"}]})
        with mock.patch.object(self.storage.os, "replace", side_effect=OSError("disk full")):
            self.assertFalse(self.storage.save_theme("dark"))
        alternate = self.root / "another state.json"
        alternate.write_text('{"notes": [{"id": "second file"}]}', encoding="utf-8")
        with mock.patch.object(self.storage, "_STATE_FILE", str(alternate)):
            self.assertTrue(self.storage.initialize_storage())
            self.assertEqual(self.storage.load_notes(), [{"id": "second file"}])
            self.assertEqual(self.storage.get_storage_status().pending_fields, ())
            self.assertTrue(self.storage.save_settings({"pet_name": "other"}))
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertEqual(json.loads(alternate.read_text(encoding="utf-8")), {
            "notes": [{"id": "second file"}], "settings": {"pet_name": "other"},
        })

    def test_corrupt_json_non_object_and_invalid_utf8_are_backed_up_byte_for_byte(self):
        for index, raw in enumerate((b'{"notes": [', b'[1, 2, 3]', b'\xff\xfe\x00bad')):
            with self.subTest(raw=raw):
                path = self.root / str(index) / "state.json"
                path.parent.mkdir()
                path.write_bytes(raw)
                storage = self.fresh_storage(path)
                self.assertTrue(storage.initialize_storage())
                backup = Path(storage.get_storage_status().recovery_backup)
                self.assertNotEqual(backup, path)
                self.assertEqual(backup.parent, path.parent)
                self.assertEqual(backup.read_bytes(), raw)
                if os.name == "posix":
                    self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
                self.assertEqual(storage._load_state(), {})
                # Reading again must not create an unbounded series of backups.
                files_after_backup = set(path.parent.iterdir())
                self.assertEqual(storage._load_state(), {})
                self.assertEqual(set(path.parent.iterdir()), files_after_backup)
                self.assertTrue(storage.save_notes([{"id": "recovered"}]))
                self.assertEqual(self.fresh_storage(path).load_notes(), [{"id": "recovered"}])
                self.assertEqual(backup.read_bytes(), raw)

    def test_repeated_corruption_uses_unique_backups_and_acknowledgment_keeps_them(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_bytes(b"first broken state")
        self.assertTrue(self.storage.initialize_storage())
        first = Path(self.storage.get_storage_status().recovery_backup)
        self.assertTrue(self.storage.save_theme("dark"))
        self.state_path.write_bytes(b"second broken state")
        restarted = self.fresh_storage()
        self.assertTrue(restarted.initialize_storage())
        second = Path(restarted.get_storage_status().recovery_backup)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), b"first broken state")
        self.assertEqual(second.read_bytes(), b"second broken state")
        restarted.acknowledge_recovery()
        self.assertIsNone(restarted.get_storage_status().recovery_backup)
        self.assertEqual(first.read_bytes(), b"first broken state")
        self.assertEqual(second.read_bytes(), b"second broken state")

    def test_corruption_after_valid_read_preserves_snapshot_and_pending_changes(self):
        self.write_fixture({"notes": [{"id": "keep from memory"}], "theme": "light",
                            "future_field": {"important": True}})
        self.assertTrue(self.storage.initialize_storage())
        with mock.patch.object(self.storage.os, "replace", side_effect=OSError("disk full")):
            self.assertFalse(self.storage.save_settings({"pet_name": "pending name"}))
        corrupt = b'{"notes": ["partially overwritten while running"'
        self.state_path.write_bytes(corrupt)
        self.assertTrue(self.storage.save_theme("dark"))
        status = self.storage.get_storage_status()
        self.assertTrue(status.recovered_from_memory)
        self.assertEqual(Path(status.recovery_backup).read_bytes(), corrupt)
        self.assertEqual(self.fresh_storage()._load_state(), {
            "notes": [{"id": "keep from memory"}], "theme": "dark",
            "future_field": {"important": True}, "settings": {"pet_name": "pending name"},
        })
        self.assert_clean_status()

    def test_unreadable_initial_state_blocks_saves_without_queuing_default_notes(self):
        original = self.write_fixture({"notes": [{"id": "must survive"}], "theme": "dark"})
        real_open = open

        def fail_state_read(file, mode="r", *args, **kwargs):
            if os.fspath(file) == str(self.state_path) and "r" in mode:
                raise PermissionError("state file is not readable")
            return real_open(file, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=fail_state_read):
            self.assertFalse(self.storage.initialize_storage())
            self.assertFalse(self.storage.save_notes([]))
            status = self.storage.get_storage_status()
            self.assertEqual(status.pending_fields, ())
            self.assertTrue(status.error)
            self.assertIsNone(status.recovery_backup)
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertEqual(list(self.state_path.parent.iterdir()), [self.state_path])
        self.assertTrue(self.storage.initialize_storage())
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.storage.load_notes(), [{"id": "must survive"}])
        self.assertEqual(self.state_path.read_bytes(), original)

    def test_backup_creation_failure_blocks_recovery_and_cannot_overwrite_corruption(self):
        self.state_path.parent.mkdir(parents=True)
        original = b'{"notes": ["a recoverable fragment"'
        self.state_path.write_bytes(original)
        real_open = open

        def fail_backup(file, mode="r", *args, **kwargs):
            if "x" in mode:
                raise PermissionError("backup directory is read-only")
            return real_open(file, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=fail_backup):
            self.assertFalse(self.storage.initialize_storage())
            self.assertFalse(self.storage.save_notes([]))
            self.assertFalse(self.storage.retry_pending_saves())
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertEqual(list(self.state_path.parent.iterdir()), [self.state_path])
        status = self.storage.get_storage_status()
        self.assertEqual(status.pending_fields, ())
        self.assertTrue(status.error)
        self.assertIsNone(status.recovery_backup)
        self.assertTrue(self.storage.initialize_storage())
        backup = Path(self.storage.get_storage_status().recovery_backup)
        self.assertEqual(backup.read_bytes(), original)

    def test_temporary_read_failure_after_success_uses_snapshot_and_retries_pending(self):
        original = self.write_fixture({"notes": [{"id": "keep"}], "theme": "light"})
        self.assertTrue(self.storage.initialize_storage())
        real_open = open

        def fail_state_read(file, mode="r", *args, **kwargs):
            if os.fspath(file) == str(self.state_path) and "r" in mode:
                raise PermissionError("temporary read denial")
            return real_open(file, mode, *args, **kwargs)

        with mock.patch("builtins.open", side_effect=fail_state_read):
            self.assertEqual(self.storage.load_notes(), [{"id": "keep"}])
            self.assertFalse(self.storage.save_theme("dark"))
            self.assertEqual(self.storage.load_theme(), "dark")
            self.assertEqual(self.storage.get_storage_status().pending_fields, ("theme",))
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.fresh_storage()._load_state(), {
            "notes": [{"id": "keep"}], "theme": "dark",
        })
        self.assert_clean_status()

    def test_backup_fsync_failure_removes_partial_backup_and_keeps_original(self):
        self.state_path.parent.mkdir(parents=True)
        original = b"broken but must be preserved"
        self.state_path.write_bytes(original)
        with mock.patch.object(self.storage.os, "fsync", side_effect=OSError("backup flush failed")):
            self.assertFalse(self.storage.initialize_storage())
            self.assertFalse(self.storage.save_notes([]))
        self.assertEqual(self.state_path.read_bytes(), original)
        self.assertEqual(list(self.state_path.parent.iterdir()), [self.state_path])
        self.assertIsNone(self.storage.get_storage_status().recovery_backup)
        self.assertEqual(self.storage.get_storage_status().pending_fields, ())
        self.assertTrue(self.storage.initialize_storage())
        backup = Path(self.storage.get_storage_status().recovery_backup)
        self.assertEqual(backup.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
