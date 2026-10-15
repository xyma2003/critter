"""Conversation persistence regressions using synthetic files, without Qt/AI."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]


def session(session_id, text, *, messages=None, **extra):
    return {"id": session_id, "title": text,
            "messages": messages if messages is not None else [
                {"role": "user", "content": text},
                {"role": "pet", "content": f"回复 {text}", "include_in_context": True},
            ], **extra}


class ChatSessionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="critter-sessions-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.state_path = self.directory / "独立会话数据" / "state.json"
        self.storage, self.chats = self.fresh_services()
        self.unrelated = {"notes": [{"id": "n1", "content": "保留便签"}],
                          "settings": {"pet_name": "测试边牧"},
                          "pet_stats": {"hunger": 33},
                          "future_field": {"preserve": ["扩展数据", 7]}}

    def load_module(self, relative_path):
        name = "_critter_chat_sessions_" + uuid.uuid4().hex
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
            chats = self.load_module("services/chat_history/__init__.py")
        return storage, chats

    def write_fixture(self, **chat_fields):
        state = {**deepcopy(self.unrelated), **deepcopy(chat_fields)}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
        self.state_path.write_bytes(raw)
        return raw

    def read_disk(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def assert_unrelated_kept(self):
        saved = self.read_disk()
        for key, value in self.unrelated.items():
            self.assertEqual(saved[key], value)

    def test_full_messages_take_precedence_and_preserve_flags_timestamps_and_extensions(self):
        messages = [
            {"role": "pet", "content": "欢迎", "include_in_context": False, "ts": "2026-10-15"},
            {"role": "user", "content": "你好", "provider_metadata": {"keep": [1]}},
            {"role": "assistant", "content": "失败提示", "include_in_context": False},
        ]
        original = session(1, "元数据", messages=messages, bubbles=[["user", "过期内容"]])
        actual = self.chats.session_messages(original)
        self.assertEqual(actual, messages)
        actual[1]["provider_metadata"]["keep"].append(2)
        self.assertEqual(original["messages"], messages)
        self.assertEqual(self.chats.session_messages({"messages": [], "bubbles": [["user", "旧内容"]]}), [])

    def test_legacy_bubbles_keep_roles_and_text_without_guessing_success(self):
        old = {"id": "old", "bubbles": [["pet", "欢迎"], ["user", "一问"],
                    ["pet", "连接失败是我们讨论的主题"], ["assistant", "另一个回答"],
                    None, ["system", "不可用"], ["user", 4], ["user"]]}
        self.assertEqual(self.chats.session_messages(old), [
            {"role": "pet", "content": "欢迎"}, {"role": "user", "content": "一问"},
            {"role": "pet", "content": "连接失败是我们讨论的主题"},
            {"role": "assistant", "content": "另一个回答"},
        ])

    def test_normal_load_is_read_only_and_handles_mixed_legacy_ids(self):
        original = [session(20, "整数"), session("20", "字符串"), session(3, "保留顺序")]
        raw = self.write_fixture(chat_sessions=original)
        with mock.patch.object(self.storage, "_atomic_write", side_effect=AssertionError("unexpected write")):
            self.assertEqual(self.chats.load_sessions(), original)
        self.assertEqual(self.state_path.read_bytes(), raw)

    def test_save_updates_three_chat_fields_together_and_preserves_other_data(self):
        original = session(12, "旧会话", extension={"keep": True})
        self.write_fixture(chat_sessions=[original], active_chat_session_id=None, chat_history=[])
        update = session(12, "新标题", messages=[{"role": "user", "content": "新消息", "ts": "time"}])
        with mock.patch.object(self.storage, "_atomic_write", wraps=self.storage._atomic_write) as writes:
            self.assertTrue(self.chats.save_session(update))
        self.assertEqual(writes.call_count, 1)
        saved = self.read_disk()
        self.assertEqual(saved["active_chat_session_id"], 12)
        self.assertEqual(saved["chat_history"], update["messages"])
        self.assertEqual(saved["chat_sessions"][0]["messages"], update["messages"])
        self.assertEqual(saved["chat_sessions"][0]["bubbles"], [["user", "新消息"]])
        self.assertEqual(saved["chat_sessions"][0]["extension"], {"keep": True})
        self.assert_unrelated_kept()

    def test_more_than_200_messages_survive_selection_restart_and_resave(self):
        messages = [{"role": "user" if index % 2 == 0 else "pet", "content": f"消息 {index}",
                     "ts": f"时间 {index}", "include_in_context": index % 17 != 0,
                     "extension": {"index": index}} for index in range(257)]
        self.write_fixture(chat_sessions=[])
        self.assertTrue(self.chats.save_session(session(1, "完整长会话", messages=messages)))
        saved = self.read_disk()
        self.assertEqual(saved["chat_sessions"][0]["messages"], messages)
        self.assertEqual(saved["chat_history"], messages[-50:])
        restarted = self.fresh_services()[1]
        current, restored = restarted.restore_current_session()
        self.assertEqual(restored, messages)
        restored.append({"role": "user", "content": "继续"})
        current["messages"] = restored
        self.assertTrue(restarted.save_session(current))
        again = self.fresh_services()[1].restore_current_session()
        self.assertEqual(again[1], messages + [{"role": "user", "content": "继续"}])

    def test_more_than_50_sessions_are_not_silently_deleted(self):
        original = [session(index, f"会话 {index}") for index in range(61)]
        self.write_fixture(chat_sessions=original)
        self.assertTrue(self.chats.save_session(session(100, "第 62 个")))
        loaded = self.chats.load_sessions()
        self.assertEqual(len(loaded), 62)
        self.assertEqual(loaded[:61], original)

    def test_activate_restores_full_history_and_selection_after_restart(self):
        first, second = session(1, "第一场"), session(2, "第二场")
        self.write_fixture(chat_sessions=[first, second], active_chat_session_id=2,
                           chat_history=second["messages"])
        current, messages = self.chats.activate_session(1)
        self.assertEqual(current["id"], 1)
        self.assertEqual(messages, first["messages"])
        self.assertEqual(self.fresh_services()[1].restore_current_session(), (current, messages))
        saved = self.read_disk()
        self.assertEqual(saved["chat_sessions"][1], second)
        self.assertEqual(saved["chat_history"], first["messages"])
        self.assert_unrelated_kept()

    def test_missing_activation_and_deletion_do_not_change_file(self):
        first = session(1, "保留")
        raw = self.write_fixture(chat_sessions=[first], active_chat_session_id=1,
                                 chat_history=first["messages"])
        self.assertIsNone(self.chats.activate_session("missing"))
        self.assertFalse(self.chats.delete_session("missing"))
        self.assertIsNone(self.chats.activate_session(True))
        self.assertFalse(self.chats.delete_session(True))
        self.assertEqual(self.state_path.read_bytes(), raw)

    def test_delete_other_session_changes_only_session_list(self):
        first, second = session(1, "当前"), session(2, "将删除")
        self.write_fixture(chat_sessions=[first, second], active_chat_session_id=1,
                           chat_history=first["messages"])
        before = self.read_disk()
        self.assertTrue(self.chats.delete_session(2))
        after = self.read_disk()
        self.assertEqual(after, {**before, "chat_sessions": [first]})

    def test_delete_current_clears_flat_history_but_does_not_open_another(self):
        first, second = session(1, "当前"), session(2, "其他")
        self.write_fixture(chat_sessions=[first, second], active_chat_session_id=1,
                           chat_history=first["messages"])
        self.assertTrue(self.chats.delete_session(1))
        after = self.read_disk()
        self.assertEqual(after["chat_sessions"], [second])
        self.assertIsNone(after["active_chat_session_id"])
        self.assertEqual(after["chat_history"], [])
        self.assertEqual(self.fresh_services()[1].restore_current_session(), (None, []))
        self.assert_unrelated_kept()

    def test_delete_last_session_does_not_resurrect_it_on_restart(self):
        only = session("last", "最后一场")
        self.write_fixture(chat_sessions=[only], active_chat_session_id="last", chat_history=only["messages"])
        self.assertTrue(self.chats.delete_session("last"))
        restarted = self.fresh_services()[1]
        self.assertEqual(restarted.load_sessions(), [])
        self.assertEqual(restarted.restore_current_session(), (None, []))
        self.assert_unrelated_kept()

    def test_new_draft_persists_selection_and_preserves_saved_sessions(self):
        previous = session(1, "原会话")
        self.write_fixture(chat_sessions=[previous], active_chat_session_id=1,
                           chat_history=previous["messages"])
        welcome = [{"role": "pet", "content": "新对话欢迎", "include_in_context": False}]
        self.assertTrue(self.chats.start_new_session(welcome))
        self.assertEqual(self.fresh_services()[1].restore_current_session(), (None, welcome))
        self.assertEqual(self.chats.load_sessions(), [previous])
        self.assertTrue(self.chats.start_new_session())
        self.assertEqual(self.fresh_services()[1].restore_current_session(), (None, []))

    def test_legacy_flat_suffix_matches_session_and_recovers_metadata_without_new_id(self):
        previous = {"id": 172, "title": "原会话", "bubbles": [["user", "开头"], ["pet", "回应"],
                    ["user", "后来"], ["pet", "错误提示"]], "extension": "keep"}
        flat = [{"role": "user", "content": "后来", "ts": "old-time"},
                {"role": "pet", "content": "错误提示", "include_in_context": False}]
        self.write_fixture(chat_sessions=[previous], chat_history=flat)
        current, messages = self.chats.restore_current_session()
        self.assertEqual(current["id"], 172)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[-2:], flat)
        self.assertEqual(current["extension"], "keep")
        self.assertEqual(len(self.chats.load_sessions()), 1)
        self.assertEqual(self.fresh_services()[1].restore_current_session(), (current, messages))
        self.assert_unrelated_kept()

    def test_legacy_unmatched_flat_becomes_its_own_session_once(self):
        previous = session(1, "另一段")
        flat = [{"role": "user", "content": "未存档的独立问题", "include_in_context": True},
                {"role": "pet", "content": "未存档回答", "ts": "t"}]
        self.write_fixture(chat_sessions=[previous], chat_history=flat)
        current, messages = self.chats.restore_current_session()
        self.assertNotEqual(current["id"], 1)
        self.assertEqual(messages, flat)
        self.assertEqual(self.chats.load_sessions()[0], previous)
        restarted = self.fresh_services()[1]
        self.assertEqual(restarted.restore_current_session(), (current, flat))
        self.assertEqual(len(restarted.load_sessions()), 2)

    def test_legacy_with_no_flat_selects_latest_and_explicit_none_never_does(self):
        first, second = session(1, "早"), session(2, "晚")
        self.write_fixture(chat_sessions=[first, second])
        current, messages = self.chats.restore_current_session()
        self.assertEqual(current["id"], 2)
        self.assertEqual(messages, second["messages"])
        self.assertTrue(self.chats.start_new_session())
        self.assertEqual(self.fresh_services()[1].restore_current_session(), (None, []))

    def test_legacy_welcome_alone_stays_a_draft_not_a_saved_conversation(self):
        welcome = [{"role": "pet", "content": "欢迎", "include_in_context": False}]
        self.write_fixture(chat_sessions=[session(1, "旧会话")], chat_history=welcome)
        self.assertEqual(self.chats.restore_current_session(), (None, welcome))
        self.assertEqual(len(self.chats.load_sessions()), 1)
        self.assertEqual(self.fresh_services()[1].restore_current_session(), (None, welcome))

    def test_unknown_records_are_not_deleted_when_saving_or_removing_a_valid_session(self):
        unknown = [None, "unrecognized", {"id": "broken", "payload": [1, 2]},
                   {"id": [], "bubbles": [["user", "不可识别 ID"]]},
                   {"id": True, "messages": [{"role": "user", "content": "布尔 ID"}]}]
        self.write_fixture(chat_sessions=[unknown[0], session(1, "有效"), *unknown[1:]])
        self.assertEqual(len(self.chats.load_sessions()), 1)
        self.assertTrue(self.chats.save_session(session(2, "新增")))
        self.assertTrue(self.chats.delete_session(1))
        self.assertEqual(self.read_disk()["chat_sessions"][:-1], unknown)
        self.assert_unrelated_kept()

    def test_duplicate_ids_are_all_repaired_and_can_be_deleted_individually(self):
        old = [session(17, "冲突 A"), session("unique", "唯一", extension={"keep": True}),
               session(17, "冲突 B"), session("17", "独立字符串")]
        self.write_fixture(chat_sessions=old)
        repaired = self.chats.load_sessions()
        self.assertEqual(len({item["id"] for item in repaired}), 4)
        self.assertEqual(repaired[1], old[1])
        self.assertEqual(repaired[3], old[3])
        for index in (0, 2):
            self.assertEqual(uuid.UUID(hex=repaired[index]["id"]).version, 4)
            self.assertEqual({k: v for k, v in repaired[index].items() if k != "id"},
                             {k: v for k, v in old[index].items() if k != "id"})
        self.assertFalse(self.chats.delete_session(17))
        self.assertIsNone(self.chats.activate_session(17))
        self.assertTrue(self.chats.delete_session(repaired[0]["id"]))
        self.assertEqual(self.chats.load_sessions(), repaired[1:])
        self.assert_unrelated_kept()

    def test_duplicate_active_id_uses_unique_flat_match_or_becomes_draft(self):
        first, second = session(17, "A"), session(17, "B")
        self.write_fixture(chat_sessions=[first, second], active_chat_session_id=17,
                           chat_history=second["messages"])
        repaired = self.chats.load_sessions()
        self.assertEqual(self.chats.restore_current_session()[0]["id"], repaired[1]["id"])
        self.write_fixture(chat_sessions=[first, second], active_chat_session_id=17,
                           chat_history=[{"role": "user", "content": "无法确定哪一场"}])
        storage, chats = self.fresh_services()
        current, messages = chats.restore_current_session()
        self.assertIsNone(current)
        self.assertEqual(messages, [{"role": "user", "content": "无法确定哪一场"}])
        self.assertIsNone(self.read_disk()["active_chat_session_id"])

    def test_failed_duplicate_repair_retains_stable_ids_until_retry(self):
        raw = self.write_fixture(chat_sessions=[session(17, "A"), session(17, "B")])
        with mock.patch.object(self.storage.os, "replace", side_effect=PermissionError("只读")):
            repaired = self.chats.load_sessions()
            self.assertEqual(self.state_path.read_bytes(), raw)
            with mock.patch.object(self.chats.uuid, "uuid4", side_effect=AssertionError("IDs changed")):
                self.assertEqual(self.chats.load_sessions(), repaired)
            self.assertEqual(self.storage.get_storage_status().pending_fields, ("chat_sessions",))
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.fresh_services()[1].load_sessions(), repaired)

    def test_failed_save_is_atomic_and_retry_restores_all_three_fields(self):
        original = session(1, "原场")
        raw = self.write_fixture(chat_sessions=[original], active_chat_session_id=1,
                                 chat_history=original["messages"])
        new = session(2, "新场")
        with mock.patch.object(self.storage.os, "replace", side_effect=OSError("磁盘已满")):
            self.assertFalse(self.chats.save_session(new))
            self.assertEqual(self.state_path.read_bytes(), raw)
            self.assertEqual(set(self.storage.get_storage_status().pending_fields),
                             {"chat_sessions", "active_chat_session_id", "chat_history"})
            self.assertEqual(self.chats.restore_current_session()[0]["id"], 2)
            self.assertEqual(self.chats.restore_current_session()[1], new["messages"])
            new["messages"][0]["content"] = "调用方修改"
            self.assertEqual(self.chats.restore_current_session()[1][0]["content"], "新场")
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.fresh_services()[1].restore_current_session()[0]["id"], 2)
        self.assert_unrelated_kept()

    def test_failed_delete_current_does_not_resurrect_during_retry_or_after_restart(self):
        current, other = session(1, "删除"), session(2, "保留")
        raw = self.write_fixture(chat_sessions=[current, other], active_chat_session_id=1,
                                 chat_history=current["messages"])
        with mock.patch.object(self.storage.os, "replace", side_effect=OSError("磁盘已满")):
            self.assertFalse(self.chats.delete_session(1))
            self.assertEqual(self.state_path.read_bytes(), raw)
            self.assertEqual(self.chats.restore_current_session(), (None, []))
            self.assertEqual(self.chats.load_sessions(), [other])
        self.assertTrue(self.storage.retry_pending_saves())
        restarted = self.fresh_services()[1]
        self.assertEqual(restarted.restore_current_session(), (None, []))
        self.assertEqual(restarted.load_sessions(), [other])
        self.assert_unrelated_kept()

    def test_failed_migration_keeps_one_pending_legacy_session_without_duplicate_retry(self):
        flat = [{"role": "user", "content": "旧版聊天"}]
        raw = self.write_fixture(chat_history=flat)
        with mock.patch.object(self.storage.os, "replace", side_effect=OSError("磁盘已满")):
            first = self.chats.restore_current_session()
            with mock.patch.object(self.chats.uuid, "uuid4", side_effect=AssertionError("duplicate migration")):
                self.assertEqual(self.chats.restore_current_session(), first)
            self.assertEqual(len(self.chats.load_sessions()), 1)
            self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertTrue(self.storage.retry_pending_saves())
        self.assertEqual(self.fresh_services()[1].restore_current_session(), first)

    def test_first_unreadable_snapshot_never_derives_a_write_even_if_next_read_would_work(self):
        first = session(1, "原来的会话")
        raw = self.write_fixture(chat_sessions=[first], active_chat_session_id=1,
                                 chat_history=first["messages"])
        actions = (
            ("save", lambda chats: chats.save_session(session(2, "新增")), False),
            ("activate", lambda chats: chats.activate_session(1), None),
            ("delete", lambda chats: chats.delete_session(1), False),
            ("draft", lambda chats: chats.start_new_session(), False),
            ("restore", lambda chats: chats.restore_current_session(), (None, [])),
        )
        for name, action, expected in actions:
            with self.subTest(operation=name):
                storage, chats = self.fresh_services()
                read_disk = storage._read_disk
                calls = []

                def fail_first(runtime):
                    calls.append(runtime)
                    if len(calls) == 1:
                        raise PermissionError("短暂不可读")
                    return read_disk(runtime)

                with mock.patch.object(storage, "_read_disk", side_effect=fail_first), \
                        mock.patch.object(storage, "_atomic_write") as write:
                    self.assertEqual(action(chats), expected)
                    write.assert_not_called()
                self.assertEqual(len(calls), 1)
                self.assertEqual(storage.get_storage_status().pending_fields, ())
                self.assertIn("无法读取", storage.get_storage_status().error)
                self.assertEqual(self.state_path.read_bytes(), raw)
                self.assertEqual(chats.load_sessions(), [first])

    def test_unreadable_known_snapshot_queues_only_then_explicit_retry_commits(self):
        first = session(1, "原来的会话")
        raw = self.write_fixture(chat_sessions=[first], active_chat_session_id=1,
                                 chat_history=first["messages"])
        self.assertTrue(self.storage.initialize_storage())
        read_disk = self.storage._read_disk
        calls = []

        def fail_first(runtime):
            calls.append(runtime)
            if len(calls) == 1:
                raise PermissionError("短暂不可读")
            return read_disk(runtime)

        with mock.patch.object(self.storage, "_read_disk", side_effect=fail_first), \
                mock.patch.object(self.storage, "_atomic_write") as write:
            self.assertFalse(self.chats.save_session(session(2, "新会话")))
            write.assert_not_called()
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertEqual(set(self.storage.get_storage_status().pending_fields),
                         {"chat_sessions", "active_chat_session_id", "chat_history"})
        self.assertIn("无法读取", self.storage.get_storage_status().error)
        self.assertEqual(self.chats.restore_current_session()[0]["id"], 2)
        self.assertEqual(self.state_path.read_bytes(), raw)
        self.assertTrue(self.storage.retry_pending_saves())
        restarted = self.fresh_services()[1]
        self.assertEqual({item["id"] for item in restarted.load_sessions()}, {1, 2})
        self.assertEqual(restarted.restore_current_session()[0]["id"], 2)
        self.assert_unrelated_kept()

    def test_concurrent_session_saves_keep_both_records_under_shared_lock(self):
        self.write_fixture(chat_sessions=[])
        start = threading.Barrier(2)
        def save(index):
            start.wait(timeout=10)
            return self.chats.save_session(session(index, f"线程 {index}"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(save, (1, 2))), [True, True])
        saved = self.read_disk()
        self.assertEqual({item["id"] for item in saved["chat_sessions"]}, {1, 2})
        current = next(item for item in saved["chat_sessions"]
                       if item["id"] == saved["active_chat_session_id"])
        self.assertEqual(saved["chat_history"], current["messages"])
        self.assert_unrelated_kept()


if __name__ == "__main__":
    unittest.main()
