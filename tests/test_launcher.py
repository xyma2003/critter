"""Exercise the macOS launcher without starting Qt or installing dependencies.

Run with ``python -m unittest tests.test_launcher``. Each test copies the real
launcher into a temporary checkout and supplies a fake project interpreter.
"""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


LAUNCHER = Path(__file__).resolve().parents[1] / "启动桌面宠物.command"

FAKE_PYTHON = r"""#!/bin/bash
{
    printf 'CALL\t%s\t%s' "$PWD" "$0"
    for launcher_test_arg in "$@"; do
        printf '\t%s' "$launcher_test_arg"
    done
    printf '\n'
} >> "$CRITTER_LAUNCHER_TEST_LOG"

if [[ "$#" -eq 1 && "$1" == "-" ]]; then
    while IFS= read -r launcher_test_line || [[ -n "$launcher_test_line" ]]; do
        printf '%s\n' "$launcher_test_line" >> "$CRITTER_LAUNCHER_TEST_PREFLIGHT_CODE"
    done
    exit "${CRITTER_LAUNCHER_TEST_PREFLIGHT_EXIT:-0}"
fi

exit "${CRITTER_LAUNCHER_TEST_MAIN_EXIT:-0}"
"""

GLOBAL_PYTHON = r"""#!/bin/bash
printf 'global python was invoked\n' > "$CRITTER_LAUNCHER_TEST_GLOBAL_MARKER"
exit 97
"""


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="critter-launcher-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name).resolve()
        self.outside = self.root / "unrelated-working-directory"
        self.outside.mkdir()
        self.log = self.root / "interpreter-calls.tsv"
        self.preflight_code = self.root / "preflight.py"
        self.global_marker = self.root / "global-python-used.txt"

        global_bin = self.root / "global-bin"
        global_bin.mkdir()
        self.write_executable(global_bin / "python3", GLOBAL_PYTHON)
        self.write_executable(global_bin / "python", GLOBAL_PYTHON)
        self.env = os.environ.copy()
        self.env.update(
            PATH=str(global_bin) + os.pathsep + os.defpath,
            CRITTER_LAUNCHER_TEST_LOG=str(self.log),
            CRITTER_LAUNCHER_TEST_PREFLIGHT_CODE=str(self.preflight_code),
            CRITTER_LAUNCHER_TEST_GLOBAL_MARKER=str(self.global_marker),
            CRITTER_LAUNCHER_TEST_PREFLIGHT_EXIT="0",
            CRITTER_LAUNCHER_TEST_MAIN_EXIT="0",
        )

    @staticmethod
    def write_executable(path, content):
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def make_checkout(self, name="checkout", with_venv=True):
        repo = self.root / name
        repo.mkdir()
        shutil.copy2(LAUNCHER, repo / LAUNCHER.name)
        (repo / "main.py").write_text(
            'raise AssertionError("The launcher tests must not run the app")\n',
            encoding="utf-8",
        )
        (repo / "requirements.txt").write_text("", encoding="utf-8")
        if with_venv:
            interpreter = repo / ".venv" / "bin" / "python"
            interpreter.parent.mkdir(parents=True)
            self.write_executable(interpreter, FAKE_PYTHON)
        return repo

    def run_launcher(self, repo):
        # Non-TTY stdin must allow unattended runs to finish without user input.
        # The timeout bounds regressions that would leave the launcher waiting.
        return subprocess.run(
            [str(repo / LAUNCHER.name)],
            cwd=self.outside,
            env=self.env,
            input="",
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=5,
            check=False,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [
            line.split("\t")
            for line in self.log.read_text(encoding="utf-8").splitlines()
        ]

    def assert_successful_launch(self, repo, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 2, calls)
        expected_interpreter = repo / ".venv" / "bin" / "python"
        for call in calls:
            self.assertEqual(call[0], "CALL")
            self.assertEqual(Path(call[1]).resolve(), repo)
            self.assertEqual(Path(call[2]).resolve(), expected_interpreter)
        self.assertEqual(calls[0][3:], ["-"])
        preflight = self.preflight_code.read_text(encoding="utf-8")
        self.assertTrue(preflight.strip())
        compile(preflight, str(self.preflight_code), "exec")
        self.assertEqual(len(calls[1][3:]), 1, calls[1])
        main_argument = Path(calls[1][3])
        if not main_argument.is_absolute():
            main_argument = repo / main_argument
        self.assertEqual(main_argument.resolve(), repo / "main.py")
        self.assertFalse(self.global_marker.exists())

    def test_launches_from_an_unrelated_working_directory(self):
        repo = self.make_checkout()
        self.assert_successful_launch(repo, self.run_launcher(repo))

    def test_checkout_path_can_contain_spaces_and_chinese(self):
        repo = self.make_checkout("我的项目 Critter 桌宠")
        self.assert_successful_launch(repo, self.run_launcher(repo))

    def test_real_preflight_detects_missing_dependencies_before_launch(self):
        repo = self.make_checkout()
        interpreter = repo / ".venv" / "bin" / "python"
        self.write_executable(
            interpreter,
            "#!/bin/bash\n"
            'printf \'CALL\\t%s\\t%s\\t%s\\n\' "$PWD" "$0" "$*" '
            '>> "$CRITTER_LAUNCHER_TEST_LOG"\n'
            f'exec {shlex.quote(sys.executable)} -I -S "$@"\n',
        )
        result = self.run_launcher(repo)
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("缺少依赖", output)
        self.assertIn("PyQt6", output)
        self.assertIn("pip install -r requirements.txt", output)
        calls = self.calls()
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0][3:], ["-"])
        self.assertFalse(self.global_marker.exists())

    def test_missing_venv_explains_setup_without_running_global_python(self):
        repo = self.make_checkout(with_venv=False)
        result = self.run_launcher(repo)
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn(".venv", output)
        self.assertIn("python3 -m venv .venv", output)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.global_marker.exists())

    def test_failed_preflight_explains_dependencies_and_does_not_launch_app(self):
        repo = self.make_checkout()
        self.env["CRITTER_LAUNCHER_TEST_PREFLIGHT_EXIT"] = "23"
        result = self.run_launcher(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pip install -r requirements.txt", result.stdout + result.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0][3:], ["-"])
        self.assertFalse(self.global_marker.exists())

    def test_app_failure_preserves_exit_status_without_waiting_for_input(self):
        repo = self.make_checkout()
        self.env["CRITTER_LAUNCHER_TEST_MAIN_EXIT"] = "37"
        result = self.run_launcher(repo)
        self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
        self.assertIn("37", result.stdout + result.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 2, calls)
        self.assertEqual(calls[0][3:], ["-"])
        self.assertFalse(self.global_marker.exists())


if __name__ == "__main__":
    unittest.main()
