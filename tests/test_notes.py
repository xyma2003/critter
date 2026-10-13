"""Note identity regressions using isolated state, without Qt or model calls."""

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]


class NotesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="critter-notes-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.state_path = self.directory / "独立数据" / "state.json"
        self.storage, self.notes = self.fresh_services()

    def load_module(self, relative_path):
        name = "_critter_notes_test_" + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return module

    def fresh_services(self):
        # A fresh storage module also resets C03's pending-save queue, as a
        # process restart would. Importing never opens real user configuration.
        config = types.ModuleType("config")
        config.STATE_FILE = str(self.state_path)
        with mock.patch.dict(sys.modules, {"config": config}):
            storage = self.load_module("core/state_manager.py")
        path_patch = mock.patch.object(storage, "_STATE_FILE", str(self.state_path))
        path_patch.start()
        self.addCleanup(path_patch.stop)
        with mock.patch.dict(sys.modules, {"core.state_manager": storage}):
            notes = self.load_module("services/notes/__init__.py")
        return storage, notes

    def write_fixture(self, notes):
        state = {"notes": deepcopy(notes), "theme": "dark",
                 "future_field": {"preserve": ["扩展数据", 7]}}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
        self.state_path.write_bytes(raw)
        return raw

    def assert_uuid_id(self, note_id):
        self.assertIsInstance(note_id, str)
        parsed = uuid.UUID(hex=note_id)
        self.assertEqual(parsed.version, 4)
        self.assertEqual(parsed.hex, note_id)

    def test_same_second_notes_and_diaries_can_be_edited_and_deleted_individually(self):
        second = 1791849600
        with mock.patch.object(self.notes.time, "time", return_value=second):
            created = [self.notes.create(f"便签 {i}", f"标题 {i}") for i in range(3)]
            created += [self.notes.create_diary(f"日记 {i}", "2026-10-13") for i in range(3)]
            self.assertEqual(len({note["id"] for note in created}), 6)
            for note in created:
                self.assert_uuid_id(note["id"])
                self.assertEqual(note["updated"], second)
            for target in created:
                before = self.notes.load_all()
                self.assertTrue(self.notes.update(target["id"], "独立修改", "新标题"))
                after = self.notes.load_all()
                self.assertEqual(len(after), 6)
                for old, current in zip(before, after):
                    if old["id"] == target["id"]:
                        self.assertEqual(current, {
                            **old, "content": "独立修改", "title": "新标题", "updated": second,
                        })
                    else:
                        self.assertEqual(current, old)
            for target in created:
                before = self.notes.load_all()
                expected = [note for note in before if note["id"] != target["id"]]
                self.assertEqual(self.notes.delete(target["id"]), expected)
                self.assertEqual(self.notes.load_all(), expected)

    def test_unique_old_integer_and_string_ids_keep_identity_when_mixed_with_new_ids(self):
        original = [
            {"id": 123, "content": "旧整数", "updated": 123},
            {"id": "123", "content": "旧字符串", "updated": 456, "extension": [1, 2]},
        ]
        self.write_fixture(original)
        new = self.notes.create("新便签")
        self.assert_uuid_id(new["id"])
        self.assertEqual(self.notes.load_all()[:2], original)
        self.assertTrue(self.notes.update("123", "仅字符串记录"))
        self.assertEqual(self.notes.load_all()[0], original[0])
        self.assertEqual(self.notes.load_all()[1]["extension"], [1, 2])
        self.notes.delete(123)
        remaining = self.notes.load_all()
        self.assertEqual([note["id"] for note in remaining], ["123", new["id"]])
        self.assertEqual(remaining[0]["content"], "仅字符串记录")
        self.assertEqual(remaining[1], new)

    def test_duplicate_groups_get_new_ids_without_losing_order_content_or_extensions(self):
        original = [
            {"id": 101, "content": "第一个旧便签", "updated": 101, "title": "A"},
            {"id": 202, "content": "唯一便签", "updated": 202, "future": {"x": 1}},
            {"id": 101, "content": "同秒日记", "updated": 101, "kind": "diary", "date": "2026-10-13"},
            {"id": "duplicate", "content": "第三条", "updated": 300, "tags": ["保留"]},
            {"id": "duplicate", "content": "第四条", "updated": 301, "extra": None},
        ]
        self.write_fixture(original)
        repaired = self.notes.load_all()
        self.assertEqual(len(repaired), len(original))
        self.assertEqual(len({note["id"] for note in repaired}), len(original))
        for old, current in zip(original, repaired):
            self.assertEqual({k: v for k, v in old.items() if k != "id"},
                             {k: v for k, v in current.items() if k != "id"})
            if old["id"] == 202:
                self.assertEqual(current["id"], 202)
            else:
                self.assertNotEqual(current["id"], old["id"])
                self.assert_uuid_id(current["id"])
        saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["notes"], repaired)
        self.assertEqual(saved["theme"], "dark")
        self.assertEqual(saved["future_field"], {"preserve": ["扩展数据", 7]})
        self.assertEqual(self.fresh_services()[1].load_all(), repaired)

        # A stale UI holding the old ambiguous ID must never act on one of the
        # formerly conflicting records; newly returned IDs identify each one.
        for old_id in (101, "duplicate"):
            self.assertFalse(self.notes.update(old_id, "不能写入"))
            self.assertEqual(self.notes.delete(old_id), repaired)
        target = repaired[2]
        self.assertTrue(self.notes.update(target["id"], "只编辑这篇日记"))
        updated = self.notes.load_all()
        self.assertEqual(updated[0], repaired[0])
        self.assertEqual(updated[2]["content"], "只编辑这篇日记")
        self.notes.delete(target["id"])
        self.assertEqual(self.notes.load_all(), [note for note in updated if note["id"] != target["id"]])

    def test_new_note_skips_uuid_candidates_already_used_by_existing_notes(self):
        existing = uuid.UUID("12345678-1234-4234-8234-123456789012")
        fresh = uuid.UUID("abcdefab-cdef-4abc-8def-abcdefabcdef")
        self.write_fixture([{"id": existing.hex, "content": "不能撞这个 ID", "updated": 1}])
        with mock.patch.object(self.notes.uuid, "uuid4", side_effect=[existing, fresh]) as generate:
            created = self.notes.create("新便签")
        self.assertEqual(created["id"], fresh.hex)
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(len(self.notes.load_all()), 2)

    def test_repair_reserves_ids_of_later_notes_and_each_new_assignment(self):
        existing = uuid.UUID("12345678-1234-4234-8234-123456789012")
        first = uuid.UUID("abcdefab-cdef-4abc-8def-abcdefabcdef")
        second = uuid.UUID("76543210-1234-4234-8234-123456789012")
        original = [{"id": 17, "content": "A"}, {"id": 17, "content": "B"},
                    {"id": existing.hex, "content": "后面的唯一 ID"}]
        self.write_fixture(original)
        with mock.patch.object(self.notes.uuid, "uuid4", side_effect=[existing, first, first, second]):
            repaired = self.notes.load_all()
        self.assertEqual([note["id"] for note in repaired], [first.hex, second.hex, existing.hex])
        self.assertEqual(repaired[2], original[2])

    def test_failed_repair_keeps_ids_stable_until_retry_and_after_restart(self):
        original = [{"id": 17, "content": "A", "updated": 10},
                    {"id": 17, "content": "B", "updated": 20, "future": [1]}]
        raw = self.write_fixture(original)
        with mock.patch.object(self.storage, "_atomic_write", side_effect=PermissionError("只读目录")) as write:
            repaired = self.notes.load_all()
            self.assertEqual(len({note["id"] for note in repaired}), 2)
            for note in repaired:
                self.assert_uuid_id(note["id"])
            self.assertEqual(self.state_path.read_bytes(), raw)
            self.assertEqual(self.storage.get_storage_status().pending_fields, ("notes",))
            self.assertIsNotNone(self.storage.get_storage_status().error)
            with mock.patch.object(self.notes.uuid, "uuid4", side_effect=AssertionError("IDs changed again")):
                self.assertEqual(self.notes.load_all(), repaired)
                self.assertEqual(self.notes.load_all(), repaired)
            self.assertEqual(write.call_count, 1)
            # The returned list must not be the pending queue's mutable copy.
            expected = deepcopy(repaired)
            repaired[0]["content"] = "调用方临时修改"
            self.assertEqual(self.notes.load_all(), expected)
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.storage.get_storage_status().pending_fields, ())
        self.assertEqual(self.fresh_services()[1].load_all(), expected)

        # Real imports in a new interpreter verify identity survives outside
        # this test's patched module names and in-memory pending state.
        script = (
            "import json, sys; "
            "sys.path.insert(0, sys.argv[1]); "
            "from services.notes import load_all; "
            "print(json.dumps(load_all(), ensure_ascii=False))"
        )
        env = {key: value for key, value in os.environ.items() if key in ("PATH", "SYSTEMROOT")}
        env.update(PYTHON_DOTENV_DISABLED="1", CRITTER_DATA_DIR=str(self.state_path.parent))
        process = subprocess.run([sys.executable, "-B", "-c", script, str(ROOT)],
                                 cwd=self.directory, env=env, text=True, capture_output=True,
                                 timeout=20, check=True)
        self.assertEqual(json.loads(process.stdout), expected)

    def test_missing_id_does_not_edit_or_remove_any_note(self):
        original = [{"id": 1, "content": "保留整数 ID"},
                    {"id": "other", "content": "保留字符串 ID"}]
        self.write_fixture(original)
        self.assertFalse(self.notes.update("missing", "不该出现", "不存在"))
        self.assertEqual(self.notes.delete("missing"), original)
        self.assertEqual(self.notes.load_all(), original)

    def test_normal_reads_do_not_rewrite_existing_file_or_create_an_empty_file(self):
        original = [{"id": 1, "content": "旧便签", "unknown": True},
                    {"id": "1", "content": "字符串 ID"}]
        raw = self.write_fixture(original)
        before = self.state_path.stat()
        with mock.patch.object(self.notes, "save_notes", side_effect=AssertionError("unexpected save")):
            self.assertEqual(self.notes.load_all(), original)
            self.assertEqual(self.notes.load_all(), original)
        after = self.state_path.stat()
        self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        empty_path = self.directory / "不存在的目录" / "state.json"
        with mock.patch.object(self.storage, "_STATE_FILE", str(empty_path)):
            self.assertEqual(self.notes.load_all(), [])
        self.assertFalse(empty_path.parent.exists())


if __name__ == "__main__":
    unittest.main()
