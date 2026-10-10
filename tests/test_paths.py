"""Check relocatable assets and isolated state paths without starting Qt.

Run with ``python -m unittest tests.test_paths``. Config and storage are imported
in fresh processes from temporary checkouts. A temporary home is injected into
the resolver; these tests never read the user's state or modify ``HOME``.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class PathTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="critter-paths-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name).resolve()
        self.outside = self.root / "unrelated working directory"
        self.outside.mkdir()
        self.fixture_home = self.root / "临时用户 home"
        self.fixture_home.mkdir()
        self.env = os.environ.copy()
        for key in (
            "CRITTER_DATA_DIR", "ANTHROPIC_API_KEY", "PYTHON_DOTENV_DISABLED",
            "PYTHONSTARTUP", "PYTHONPATH",
        ):
            self.env.pop(key, None)
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def make_checkout(self, name="我的项目 Critter 桌宠"):
        checkout = self.root / name
        (checkout / "core").mkdir(parents=True)
        (checkout / "assets").mkdir()
        for name in ("config.py", "paths.py", "core/state_manager.py"):
            shutil.copy2(PROJECT / name, checkout / name)
        (checkout / "core" / "__init__.py").touch()
        return checkout

    def run_python(self, checkout, code, *, env=None, check=True):
        child_env = self.env.copy()
        child_env["PYTHONPATH"] = str(checkout)
        if env:
            child_env.update(env)
        result = subprocess.run(
            [sys.executable, "-B", "-c", textwrap.dedent(code)],
            cwd=self.outside,
            env=child_env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=10,
            check=False,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def isolated_storage(self, code):
        """Inject a home before config resolves the state file, without HOME."""
        return (
            "from pathlib import Path\n"
            "import paths\n"
            "original_resolver = paths.resolve_state_file\n"
            "paths.resolve_state_file = lambda data_dir=None: "
            f"original_resolver(data_dir, home=Path({str(self.fixture_home)!r}))\n"
            "import config\n"
            "from core import state_manager as state\n"
            + textwrap.dedent(code)
        )

    def test_assets_follow_a_checkout_moved_to_a_chinese_path(self):
        checkout = self.make_checkout("original checkout")
        asset = checkout / "assets" / "pet.png"
        asset.write_bytes(b"asset fixture")
        relocated = self.root / "移动后的 中文项目"
        shutil.move(str(checkout), relocated)
        result = self.run_python(relocated, """
            import json
            from paths import PROJECT_ROOT, ASSETS_DIR
            print(json.dumps({"root": str(PROJECT_ROOT), "assets": str(ASSETS_DIR),
                              "content": (ASSETS_DIR / "pet.png").read_text()}))
        """)
        self.assertEqual(json.loads(result.stdout), {
            "root": str(relocated), "assets": str(relocated / "assets"),
            "content": "asset fixture",
        })

    def test_unset_and_blank_directory_preserve_the_legacy_filename(self):
        checkout = self.make_checkout()
        result = self.run_python(checkout, f"""
            import json
            from pathlib import Path
            from paths import resolve_state_file
            home = Path({str(self.fixture_home)!r})
            print(json.dumps([str(resolve_state_file(value, home=home))
                              for value in (None, "", "  ", "\\t")]))
        """)
        self.assertEqual(json.loads(result.stdout),
                         [str(self.fixture_home / ".desktop-pet-state.json")] * 4)

    def test_absolute_and_tilde_directories_resolve_to_state_json(self):
        checkout = self.make_checkout()
        data_dir = self.root / "独立 data" / "nested"
        result = self.run_python(checkout, f"""
            import json
            from pathlib import Path
            from paths import resolve_state_file
            home = Path({str(self.fixture_home)!r})
            print(json.dumps([
                str(resolve_state_file({str(data_dir)!r}, home=home)),
                str(resolve_state_file("~/桌宠 data", home=home)),
                str(resolve_state_file("~", home=home)),
            ]))
        """)
        self.assertEqual(json.loads(result.stdout), [
            str(data_dir / "state.json"),
            str(self.fixture_home / "桌宠 data" / "state.json"),
            str(self.fixture_home / "state.json"),
        ])
        self.assertFalse(data_dir.exists())

    def test_relative_directory_is_rejected_with_an_actionable_error(self):
        checkout = self.make_checkout()
        result = self.run_python(checkout, """
            from paths import resolve_state_file
            for value in ("data", "./data", "../data"):
                try:
                    resolve_state_file(value)
                except ValueError as error:
                    message = str(error)
                    assert "absolute" in message.lower() or "绝对" in message, message
                else:
                    raise AssertionError(f"relative path was accepted: {value}")
        """)
        self.assertEqual(result.stdout, "")
        imported = self.run_python(
            checkout, "import config", env={"CRITTER_DATA_DIR": "./data"}, check=False,
        )
        self.assertNotEqual(imported.returncode, 0)
        self.assertIn("ValueError", imported.stderr)
        self.assertFalse((self.outside / "data").exists())

    def test_project_dotenv_is_used_from_an_unrelated_working_directory(self):
        checkout = self.make_checkout()
        project_data = self.root / "project data"
        (checkout / ".env").write_text(
            f'CRITTER_DATA_DIR="{project_data}"\n'
            'ANTHROPIC_API_KEY="project-fixture-key"\n', encoding="utf-8",
        )
        (self.outside / ".env").write_text(
            'CRITTER_DATA_DIR="./incorrect-cwd"\n'
            'ANTHROPIC_API_KEY="cwd-fixture-key"\n', encoding="utf-8",
        )
        result = self.run_python(checkout, """
            import json
            import config
            print(json.dumps([config.STATE_FILE, config.Config.ANTHROPIC_API_KEY]))
        """, env={"ANTHROPIC_API_KEY": "shell-fixture-key"})
        self.assertEqual(json.loads(result.stdout),
                         [str(project_data / "state.json"), "project-fixture-key"])

    def test_missing_project_dotenv_does_not_search_cwd_or_parent(self):
        checkout = self.make_checkout()
        for location in (self.root, self.outside):
            (location / ".env").write_text(
                'CRITTER_DATA_DIR="./incorrect-parent-or-cwd"\n'
                'ANTHROPIC_API_KEY="unexpected-fixture-key"\n', encoding="utf-8",
            )
        result = self.run_python(checkout, self.isolated_storage("""
            import json
            print(json.dumps([config.STATE_FILE, config.Config.ANTHROPIC_API_KEY]))
        """))
        self.assertEqual(json.loads(result.stdout), [
            str(self.fixture_home / ".desktop-pet-state.json"), "",
        ])

    def test_shell_data_directory_wins_over_project_dotenv(self):
        checkout = self.make_checkout()
        dotenv_data = self.root / "dotenv data"
        shell_data = self.root / "shell data"
        (checkout / ".env").write_text(
            f'CRITTER_DATA_DIR="{dotenv_data}"\n', encoding="utf-8",
        )
        for override, expected in (
            (str(shell_data), shell_data / "state.json"),
            ("", self.fixture_home / ".desktop-pet-state.json"),
        ):
            with self.subTest(override=override):
                result = self.run_python(checkout, self.isolated_storage("""
                    print(config.STATE_FILE)
                """), env={"CRITTER_DATA_DIR": override})
                self.assertEqual(result.stdout.strip(), str(expected))

    def test_importing_config_does_not_create_state_or_directories(self):
        checkout = self.make_checkout()
        data_dir = self.root / "not-created" / "nested"
        before = set(self.root.rglob("*"))
        self.run_python(checkout, "import config", env={"CRITTER_DATA_DIR": str(data_dir)})
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_existing_legacy_state_keeps_settings_and_notes_when_saved(self):
        checkout = self.make_checkout()
        legacy_file = self.fixture_home / ".desktop-pet-state.json"
        legacy = {
            "settings": {"pet_name": "旧伙伴", "auto_refresh_min": 17},
            "notes": [{"text": "已有笔记", "done": False}],
            "chat_history": [{"role": "user", "content": "已有聊天"}],
            "theme": "light",
        }
        legacy_file.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
        result = self.run_python(checkout, self.isolated_storage("""
            import json
            before = {"settings": state.load_settings(), "notes": state.load_notes(),
                      "history": state.load_chat_history()}
            state.save_theme("dark")
            print(json.dumps({"path": state._STATE_FILE, "before": before}))
        """))
        actual = json.loads(result.stdout)
        self.assertEqual(actual["path"], str(legacy_file))
        self.assertEqual(actual["before"]["settings"]["pet_name"], "旧伙伴")
        self.assertEqual(actual["before"]["notes"], legacy["notes"])
        self.assertEqual(actual["before"]["history"], legacy["chat_history"])
        self.assertEqual(json.loads(legacy_file.read_text(encoding="utf-8")),
                         {**legacy, "theme": "dark"})
        self.assertEqual(list(self.fixture_home.iterdir()), [legacy_file])

    def test_custom_storage_creates_parents_and_persists_without_importing_legacy(self):
        checkout = self.make_checkout()
        legacy_file = self.fixture_home / ".desktop-pet-state.json"
        legacy_bytes = b'{"settings": {"pet_name": "legacy"}, "notes": ["keep"]}\n'
        legacy_file.write_bytes(legacy_bytes)
        data_dir = self.root / "独立 state" / "new" / "nested"
        override = {"CRITTER_DATA_DIR": str(data_dir)}
        first = self.run_python(checkout, self.isolated_storage("""
            import json
            before = state._load_state()
            state.save_settings({"pet_name": "新伙伴"})
            state.save_notes([{"text": "独立笔记"}])
            print(json.dumps(before))
        """), env=override)
        self.assertEqual(json.loads(first.stdout), {})
        self.assertTrue((data_dir / "state.json").is_file())
        second = self.run_python(checkout, self.isolated_storage("""
            import json
            print(json.dumps({"name": state.load_settings()["pet_name"],
                              "notes": state.load_notes(), "path": state._STATE_FILE}))
        """), env=override)
        self.assertEqual(json.loads(second.stdout), {
            "name": "新伙伴", "notes": [{"text": "独立笔记"}],
            "path": str(data_dir / "state.json"),
        })
        self.assertEqual(legacy_file.read_bytes(), legacy_bytes)


if __name__ == "__main__":
    unittest.main()
