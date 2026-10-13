"""Persistent pet-action evidence, with temporary state and no Qt or models."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]
ZONE = datetime.timezone(datetime.timedelta(hours=8))
AT = datetime.datetime(2026, 10, 13, 12, 30, 1, tzinfo=ZONE)
DAY = "2026-10-13"
STATS = {"hunger": 90.0, "energy": 80.0, "mood": 70.0}
ZERO_COUNTS = {"feed": 0, "play": 0, "rest": 0, "pet": 0}


class PetActivityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="critter-activity-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.state_path = self.directory / "独立数据" / "state.json"
        self.storage, self.pet_module = self.fresh_services()

    def load_module(self, relative_path):
        name = "_critter_activity_test_" + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return module

    def fresh_services(self):
        config = types.ModuleType("config")
        config.STATE_FILE = str(self.state_path)
        with mock.patch.dict(sys.modules, {"config": config}):
            storage = self.load_module("core/state_manager.py")
        with mock.patch.dict(sys.modules, {"core.state_manager": storage}):
            pet_module = self.load_module("data/pet/__init__.py")
        return storage, pet_module

    def write_fixture(self, **fields):
        state = {"pet_stats": deepcopy(STATS), "theme": "dark",
                 "future_field": {"keep": ["扩展", 1]}, **fields}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
        self.state_path.write_bytes(raw)
        return raw

    def read_disk(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def record(self, kind, at=AT, stats=STATS):
        return self.storage.record_pet_interaction(kind, stats, at)

    def test_two_feeds_and_one_play_survive_restart_and_new_interpreter(self):
        self.write_fixture()
        for kind in ("feed", "feed", "play"):
            self.assertTrue(self.record(kind))
        expected = {**ZERO_COUNTS, "feed": 2, "play": 1}
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), expected)
        restarted, _ = self.fresh_services()
        self.assertEqual(restarted.load_pet_interaction_counts(DAY), expected)
        script = """
import json, sys, types
sys.path.insert(0, sys.argv[1])
config = types.ModuleType('config')
config.STATE_FILE = sys.argv[2]
sys.modules['config'] = config
from core.state_manager import load_pet_interaction_counts, load_pet_stats
print(json.dumps({'counts': load_pet_interaction_counts(sys.argv[3]),
                  'stats': load_pet_stats()}))
"""
        result = subprocess.run([sys.executable, "-c", script, str(ROOT),
                                 str(self.state_path), DAY], text=True,
                                capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), {"counts": expected, "stats": STATS})

    def test_all_four_events_same_timestamp_are_not_deduplicated(self):
        for kind in ("feed", "play", "rest", "pet", "feed"):
            self.assertTrue(self.record(kind))
        events = self.storage.load_pet_interactions(DAY)
        self.assertEqual([event["kind"] for event in events],
                         ["feed", "play", "rest", "pet", "feed"])
        self.assertEqual({event["at"] for event in events}, {AT.isoformat()})
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY),
                         {"feed": 2, "play": 1, "rest": 1, "pet": 1})

    def test_midnight_dates_are_independent_and_keep_occurrence_time_zone(self):
        before = datetime.datetime(2026, 10, 13, 23, 59, 59, tzinfo=ZONE)
        after = before + datetime.timedelta(seconds=1)
        self.record("feed", before)
        self.record("play", after)
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY),
                         {**ZERO_COUNTS, "feed": 1})
        self.assertEqual(self.storage.load_pet_interaction_counts("2026-10-14"),
                         {**ZERO_COUNTS, "play": 1})
        # One instant expressed in another zone is still kept in the date the
        # caller recorded, rather than converted into today's local time zone.
        west = datetime.timezone(datetime.timedelta(hours=-7))
        at_west = AT.astimezone(west)
        self.record("rest", at_west)
        self.assertEqual(self.storage.load_pet_interaction_counts("2026-10-12"),
                         {**ZERO_COUNTS, "rest": 1})
        self.assertEqual(self.storage.load_pet_interactions("2026-10-12")[0]["at"],
                         at_west.isoformat())

    def test_default_and_naive_time_have_explicit_offset(self):
        self.assertTrue(self.storage.record_pet_interaction("feed", STATS))
        naive = datetime.datetime(2026, 10, 13, 12, 0, 0)
        self.assertTrue(self.record("play", naive))
        all_events = [event for events in self.read_disk()["pet_interactions"].values()
                      for event in events]
        self.assertEqual(len(all_events), 2)
        for event in all_events:
            self.assertIsNotNone(datetime.datetime.fromisoformat(event["at"]).utcoffset())
        self.assertEqual(all_events[-1]["at"], naive.astimezone().isoformat())

    def test_legacy_state_does_not_infer_actions_from_stats_or_chat(self):
        raw = self.write_fixture(chat_history=[{"role": "user", "content": "喂食三次"}],
                                 chat_sessions=[{"bubbles": [["pet", "吃饱了"]]}])
        with mock.patch.object(self.storage, "_atomic_write", side_effect=AssertionError("read wrote")):
            self.assertEqual(self.storage.load_pet_interactions(DAY), [])
            self.assertEqual(self.storage.load_pet_interaction_counts(DAY), ZERO_COUNTS)
        self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertNotIn("pet_interactions", self.read_disk())

    def test_missing_state_read_does_not_create_file_or_pending_update(self):
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), ZERO_COUNTS)
        self.assertFalse(self.state_path.exists())
        self.assertEqual(self.storage.get_storage_status().pending_fields, ())

    def test_old_dates_unknown_fields_and_invalid_events_are_preserved(self):
        valid = {"kind": "rest", "at": AT.isoformat(), "future": {"keep": True}}
        invalid = [None, "unrecognized", {"kind": "future_action", "at": AT.isoformat()},
                   {"kind": "feed"}, {"kind": "feed", "at": "invalid"},
                   {"kind": "feed", "at": "2026-10-13T12:00:00"},
                   {"kind": "play", "at": "2026-10-14T12:00:00+08:00"}]
        original = {DAY: [valid, *invalid], "2020-01-01": {"legacy": [1, 2]},
                    "extension": {"unknown": "keep"}}
        self.write_fixture(pet_interactions=original)
        self.assertEqual(self.storage.load_pet_interactions(DAY), [valid])
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), {**ZERO_COUNTS, "rest": 1})
        self.assertTrue(self.record("pet"))
        saved = self.read_disk()
        self.assertEqual(saved["pet_interactions"], {
            **original, DAY: [*original[DAY], {"kind": "pet", "at": AT.isoformat()}],
        })
        self.assertEqual(saved["future_field"], {"keep": ["扩展", 1]})
        self.assertEqual(saved["theme"], "dark")

    def test_malformed_root_or_target_bucket_blocks_writes_without_erasing_data(self):
        for original in ([{"legacy": 1}], None, {DAY: {"legacy": 2}}):
            with self.subTest(original=original):
                self.storage, self.pet_module = self.fresh_services()
                raw = self.write_fixture(pet_interactions=original)
                self.assertEqual(self.storage.load_pet_interaction_counts(DAY), ZERO_COUNTS)
                with mock.patch.object(self.storage, "_atomic_write") as write:
                    self.assertFalse(self.record("feed"))
                write.assert_not_called()
                self.assertEqual(self.state_path.read_bytes(), raw)
                self.assertEqual(self.storage.get_storage_status().pending_fields, ())
                self.assertIn("互动记录格式异常", self.storage.get_storage_status().error)

    def test_returned_events_are_detached_from_pending_and_disk_snapshots(self):
        self.write_fixture()
        with mock.patch.object(self.storage, "_atomic_write", side_effect=PermissionError("read only")):
            self.assertFalse(self.record("feed"))
        events = self.storage.load_pet_interactions(DAY)
        events[0]["kind"] = "play"
        events.append({"kind": "rest", "at": AT.isoformat()})
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), {**ZERO_COUNTS, "feed": 1})
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.fresh_services()[0].load_pet_interaction_counts(DAY),
                         {**ZERO_COUNTS, "feed": 1})

    def test_failed_atomic_replace_preserves_original_and_retry_appends_once(self):
        raw = self.write_fixture()
        updated = {"hunger": 100, "energy": 90, "mood": 75}
        with mock.patch.object(self.storage.os, "replace", side_effect=PermissionError("read only")):
            self.assertFalse(self.record("feed", stats=updated))
        self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertEqual(list(self.state_path.parent.glob(".*.tmp")), [])
        self.assertEqual(set(self.storage.get_storage_status().pending_fields),
                         {"pet_stats", "pet_interactions"})
        self.assertEqual(self.storage.load_pet_stats(), updated)
        with mock.patch.object(self.storage, "_atomic_write", side_effect=AssertionError("read wrote")):
            for _ in range(3):
                self.assertEqual(self.storage.load_pet_interaction_counts(DAY),
                                 {**ZERO_COUNTS, "feed": 1})
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertTrue(self.storage.retry_pending_saves())
        restarted, _ = self.fresh_services()
        self.assertEqual(restarted.load_pet_interaction_counts(DAY), {**ZERO_COUNTS, "feed": 1})
        self.assertEqual(restarted.load_pet_stats(), updated)

    def test_additional_action_while_pending_and_later_stats_save_do_not_duplicate(self):
        raw = self.write_fixture()
        with mock.patch.object(self.storage, "_atomic_write", side_effect=PermissionError("read only")):
            self.assertFalse(self.record("feed"))
            self.assertFalse(self.record("feed"))
            self.assertFalse(self.record("play"))
        self.assertEqual(self.state_path.read_bytes(), raw)
        expected = {**ZERO_COUNTS, "feed": 2, "play": 1}
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), expected)
        self.assertTrue(self.storage.save_pet_stats(70, 60, 80))
        self.assertEqual(self.storage.get_storage_status().pending_fields, ())
        restarted, _ = self.fresh_services()
        self.assertEqual(restarted.load_pet_interaction_counts(DAY), expected)
        self.assertEqual(restarted.load_pet_stats(), {"hunger": 70, "energy": 60, "mood": 80})

    def test_stats_and_event_reach_writer_together_in_one_commit(self):
        self.write_fixture()
        with mock.patch.object(self.storage, "_atomic_write", wraps=self.storage._atomic_write) as write:
            self.assertTrue(self.record("play"))
        write.assert_called_once()
        snapshot = write.call_args.args[0]
        self.assertEqual(snapshot["pet_stats"], STATS)
        self.assertEqual(snapshot["pet_interactions"][DAY], [{"kind": "play", "at": AT.isoformat()}])

    def test_first_transient_read_failure_never_overwrites_unknown_existing_events(self):
        original = {DAY: [{"kind": "play", "at": AT.isoformat()}]}
        raw = self.write_fixture(pet_interactions=original)
        state = self.read_disk()
        # A second read would recover: the failed call must not derive an
        # empty history first and then commit it over that recovered state.
        with mock.patch.object(self.storage, "_read_disk",
                               side_effect=[PermissionError("temporary read failure"), state]) as read:
            with mock.patch.object(self.storage, "_atomic_write") as write:
                self.assertFalse(self.record("feed"))
            self.assertEqual(read.call_count, 1)
            write.assert_not_called()
            self.assertEqual(self.storage.get_storage_status().pending_fields, ())
            self.assertIn("无法读取本地数据", self.storage.get_storage_status().error)
        self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), {**ZERO_COUNTS, "play": 1})
        self.assertTrue(self.record("feed"))
        self.assertEqual(self.fresh_services()[0].load_pet_interaction_counts(DAY),
                         {**ZERO_COUNTS, "feed": 1, "play": 1})

    def test_read_failure_after_known_snapshot_queues_actions_then_recovers_once(self):
        original = {DAY: [{"kind": "play", "at": AT.isoformat()}]}
        raw = self.write_fixture(pet_interactions=original)
        self.assertTrue(self.storage.initialize_storage())
        updated_stats = {"hunger": 75, "energy": 60, "mood": 85}
        with mock.patch.object(self.storage, "_read_disk", side_effect=PermissionError("temporary read failure")) as read:
            with mock.patch.object(self.storage, "_atomic_write") as write:
                self.assertFalse(self.record("feed"))
                self.assertFalse(self.record("feed"))
                self.assertFalse(self.record("pet", stats=updated_stats))
            self.assertEqual(read.call_count, 3)
            write.assert_not_called()
            self.assertEqual(set(self.storage.get_storage_status().pending_fields),
                             {"pet_stats", "pet_interactions"})
            self.assertIn("无法读取本地数据", self.storage.get_storage_status().error)
        self.assertEqual(self.state_path.read_bytes(), raw)
        expected = {"feed": 2, "play": 1, "rest": 0, "pet": 1}
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), expected)
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertTrue(self.storage.retry_pending_saves())
        restarted, _ = self.fresh_services()
        self.assertEqual(restarted.load_pet_interaction_counts(DAY), expected)
        self.assertEqual(restarted.load_pet_stats(), updated_stats)
        self.assertEqual(self.read_disk()["future_field"], {"keep": ["扩展", 1]})

    def test_successful_append_reads_once_and_preserves_other_pending_fields(self):
        self.write_fixture(pet_interactions={DAY: [{"kind": "rest", "at": AT.isoformat()}]})
        with mock.patch.object(self.storage, "_atomic_write", side_effect=PermissionError("read only")):
            self.assertFalse(self.storage.save_theme("light"))
        with mock.patch.object(self.storage, "_read_disk", wraps=self.storage._read_disk) as read:
            self.assertTrue(self.record("feed"))
        self.assertEqual(read.call_count, 1)
        self.assertEqual(self.storage.get_storage_status().pending_fields, ())
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY), {**ZERO_COUNTS, "feed": 1, "rest": 1})
        self.assertEqual(self.read_disk()["theme"], "light")

    def test_threaded_appends_do_not_lose_actions(self):
        self.write_fixture()
        barrier = threading.Barrier(8)
        def add_events(worker):
            barrier.wait(timeout=5)
            kind = ("feed", "play", "rest", "pet")[worker % 4]
            return [self.record(kind) for _ in range(5)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(add_events, range(8)))
        self.assertTrue(all(all(worker) for worker in results))
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY),
                         dict.fromkeys(ZERO_COUNTS, 10))
        self.assertEqual(len(self.read_disk()["pet_interactions"][DAY]), 40)

    def test_pet_stats_actions_record_once_and_chat_decay_do_not_count(self):
        class FrozenDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 13, 12, 0, 0, tzinfo=ZONE)
        self.write_fixture()
        pet = self.pet_module.PetStats()
        with mock.patch.object(self.storage, "datetime", types.SimpleNamespace(datetime=FrozenDateTime)):
            pet.feed()
            pet.feed()
            pet.play()
            pet.rest()
            pet.pet()
            before_non_actions = self.storage.load_pet_interactions(DAY)
            pet.on_chat()
            pet.decay()
            pet._save()
        self.assertEqual(self.storage.load_pet_interactions(DAY), before_non_actions)
        self.assertEqual(self.storage.load_pet_interaction_counts(DAY),
                         {"feed": 2, "play": 1, "rest": 1, "pet": 1})
        self.assertEqual(self.storage.load_pet_stats(), {
            "hunger": round(pet.hunger, 1), "energy": round(pet.energy, 1),
            "mood": round(pet.mood, 1),
        })

    def test_invalid_new_action_inputs_fail_before_writing(self):
        self.write_fixture()
        raw = self.state_path.read_bytes()
        for kind, stats, when, error in (
                ("chat", STATS, AT, ValueError),
                ("feed", [], AT, TypeError),
                ("play", STATS, "2026-10-13", TypeError),
                ("rest", STATS, 0, TypeError)):
            with self.subTest(kind=kind, stats=stats, when=when):
                with self.assertRaises(error):
                    self.storage.record_pet_interaction(kind, stats, when)
        self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertEqual(self.storage.get_storage_status().pending_fields, ())


if __name__ == "__main__":
    unittest.main()
