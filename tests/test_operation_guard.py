from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_store.operation_guard import operation_guard


REPOSITORY = Path(__file__).resolve().parents[1]


def make_project(parent: Path) -> Path:
    project = parent / "agent"
    project.mkdir()
    (project / ".research-agent-root").write_text(
        "research-agent-owned-root-v1\n", encoding="utf-8"
    )
    return project.resolve()


def copy_launcher(project: Path) -> Path:
    launcher = project / "research-store"
    shutil.copy2(REPOSITORY / "research-store", launcher)
    package = project / "src/research_store"
    package.mkdir(parents=True)
    for name in ("operation_guard.py", "__init__.py"):
        shutil.copy2(REPOSITORY / "src/research_store" / name, package / name)
    binaries = project / ".venv/bin"
    binaries.mkdir(parents=True)
    (binaries / "python").symlink_to(Path(sys.executable).resolve())
    cli = binaries / "research-store"
    cli.write_text(
        f"#!{Path(sys.executable).resolve()}\n"
        "import json, os, pathlib, sys\n"
        "root = pathlib.Path(sys.argv[2]).parent.parent\n"
        "sys.path.insert(0, str(root / 'src'))\n"
        "from research_store.operation_guard import operation_guard\n"
        "with operation_guard(root):\n"
        "    print(json.dumps({'args': sys.argv[1:], 'home': os.environ['HOME'], "
        "'tmp': os.environ['TMPDIR'], 'cache': os.environ['XDG_CACHE_HOME'], "
        "'pythonpath': os.environ.get('PYTHONPATH')}), flush=True)\n"
        "    sys.stdin.readline()\n",
        encoding="utf-8",
    )
    cli.chmod(0o700)
    return launcher


class OperationGuardTests(unittest.TestCase):
    def test_public_launcher_rejects_exclusive_lock_before_runtime_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            launcher = copy_launcher(project)
            descriptor = os.open(project, os.O_RDONLY)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(
                    [str(launcher), "init"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("제거가 진행 중", result.stderr)
                self.assertFalse((project / ".research-store").exists())
                self.assertFalse(list(project.rglob("__pycache__")))
            finally:
                os.close(descriptor)

    def test_public_commands_share_lock_keep_arguments_and_hold_it_after_exec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            launcher = copy_launcher(project)
            environment = dict(os.environ)
            outside = Path(directory) / "originals"
            outside.mkdir()
            environment.update(
                PYTHONPATH=str(outside),
                PYTHONPYCACHEPREFIX=str(outside / "pycache"),
                TMPDIR=str(outside / "temporary"),
                XDG_CACHE_HOME=str(outside / "cache"),
            )
            arguments = ["search", "topic with spaces", "$HOME"]
            children: list[subprocess.Popen[str]] = []
            descriptor = os.open(project, os.O_RDONLY)
            try:
                for _ in range(2):
                    child = subprocess.Popen(
                        [str(launcher), *arguments],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=environment,
                    )
                    children.append(child)
                    assert child.stdout is not None
                    ready = json.loads(child.stdout.readline())
                    self.assertEqual(
                        ready["args"],
                        ["--config", str(project / ".research-store/config.toml"), *arguments],
                    )
                    self.assertEqual(ready["home"], str(project / ".research-store/home"))
                    self.assertEqual(ready["tmp"], str(project / ".research-store/tmp"))
                    self.assertEqual(ready["cache"], str(project / ".research-store/xdg-cache"))
                    self.assertIsNone(ready["pythonpath"])
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                for child in children:
                    _, error = child.communicate("finish\n", timeout=5)
                    self.assertEqual(child.returncode, 0, error)
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertEqual(list(outside.iterdir()), [])
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=5)
                os.close(descriptor)

    def test_direct_cli_rejects_exclusive_lock_before_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            descriptor = os.open(project, os.O_RDONLY)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                environment = dict(os.environ)
                environment["PYTHONPATH"] = str(REPOSITORY / "src")
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                result = subprocess.run(
                    [
                        sys.executable, "-B", "-m", "research_store.cli",
                        "--config", str(project / ".research-store/config.toml"), "init",
                    ],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    env=environment,
                    timeout=5,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("제거가 진행 중", result.stderr)
                self.assertFalse((project / ".research-store").exists())
            finally:
                os.close(descriptor)

    def test_guard_rejects_replacement_of_opened_root_before_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            moved = project.with_name("moved-agent")
            real_flock = fcntl.flock

            def move_after_acquiring(descriptor: int, operation: int) -> None:
                real_flock(descriptor, operation)
                if operation == fcntl.LOCK_SH | fcntl.LOCK_NB:
                    project.rename(moved)
                    project.mkdir()

            with patch(
                "research_store.operation_guard.fcntl.flock",
                side_effect=move_after_acquiring,
            ):
                with self.assertRaisesRegex(ValueError, "폴더가 이동"):
                    with operation_guard(project):
                        self.fail("a replaced root must never run a command")
            self.assertEqual(list(project.iterdir()), [])
            self.assertTrue((moved / ".research-agent-root").is_file())

    def test_guard_creates_no_files_and_releases_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            before = list(project.iterdir())
            with self.assertRaisesRegex(RuntimeError, "operation failed"):
                with operation_guard(project):
                    raise RuntimeError("operation failed")
            descriptor = os.open(project, os.O_RDONLY)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(descriptor)
            self.assertEqual(list(project.iterdir()), before)

    def test_public_launcher_rejects_runtime_symlink_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            launcher = copy_launcher(project)
            outside = Path(directory) / "originals"
            outside.mkdir()
            (project / ".research-store").symlink_to(outside, target_is_directory=True)
            result = subprocess.run(
                [str(launcher), "init"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("링크", result.stderr)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
