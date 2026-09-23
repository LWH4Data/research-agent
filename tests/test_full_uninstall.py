from __future__ import annotations

from contextlib import redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts/uninstall_project.py"
REGISTRATIONS = (
    Path(".agents/skills/research-library"),
    Path(".codex/agents/research-library-manager.toml"),
    Path(".codex/agents/research-paper-converter.toml"),
    Path(".codex/rules/research-library.rules"),
    Path(".codex/research-library-sandbox"),
)


def load_uninstaller():
    # Import production code, but NEVER pass the real repository to removal.
    spec = importlib.util.spec_from_file_location("full_uninstall_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def tree_contents(path: Path) -> dict[str, tuple[object, ...]]:
    """Compare content and modes without following links to external files."""
    if not os.path.lexists(path):
        return {}
    entries = [path]
    if path.is_dir() and not path.is_symlink():
        entries.extend(sorted(path.rglob("*")))
    result = {}
    for entry in entries:
        info = entry.lstat()
        if stat.S_ISLNK(info.st_mode):
            content = os.readlink(entry)
        elif stat.S_ISREG(info.st_mode):
            content = entry.read_bytes()
        else:
            content = None
        result[str(entry.relative_to(path))] = (info.st_mode, content)
    return result


class FullUninstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.uninstaller = load_uninstaller()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="research-uninstall-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.trash = self.home / ".Trash"
        self.trash.mkdir(mode=0o700)
        self.project = self.home / "research-agent"
        self.project.mkdir()
        for name in ("resources", "scripts"):
            shutil.copytree(
                REPOSITORY / name,
                self.project / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        for name in (".research-agent-root", "uninstall.sh"):
            shutil.copy2(REPOSITORY / name, self.project / name)
        self.source = self.base / "original research"
        self.source.mkdir()
        self.paper = self.source / "original.pdf"
        self.paper.write_bytes(b"original research must remain unchanged\n")
        (self.project / ".research-store").mkdir()
        (self.project / "knowledge/documents").mkdir(parents=True)
        (self.project / "knowledge/documents/paper.md").write_text(
            "# Converted document\n", encoding="utf-8"
        )
        (self.project / ".research-store/library.sqlite").write_bytes(b"saved state")
        self.write_sources(self.source)
        other_agent = self.home / ".codex/agents/other.toml"
        other_agent.parent.mkdir(parents=True)
        other_agent.write_text("name = 'unrelated'\n", encoding="utf-8")
        self.install()
        self.original_before = tree_contents(self.source)
        self.paper_metadata = self.paper.stat()

    def write_sources(self, path: Path, *, enabled: bool = True) -> None:
        config = self.project / ".research-store/config.toml"
        config.write_text(
            '[store]\n'
            'documents = "knowledge/documents"\n'
            'conversations = "knowledge/conversations"\n'
            'assets = "knowledge/assets"\n'
            'state = ".research-store/library.sqlite"\n'
            'temporary = ".research-store/tmp"\n\n'
            '[[sources]]\n'
            'id = "original"\n'
            f'path = {json.dumps(str(path))}\n'
            'kind = "directory"\n'
            f'enabled = {str(enabled).lower()}\n',
            encoding="utf-8",
        )

    def install(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-B",
             str(self.project / "scripts/personal_registration.py"),
             "install", "--root", str(self.project), "--home", str(self.home)],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def registrations(self):
        return {str(path): tree_contents(self.home / path) for path in REGISTRATIONS}

    def remove(self, **kwargs):
        with redirect_stdout(io.StringIO()):
            return self.uninstaller.remove_project(self.project, self.home, **kwargs)

    def assert_originals_unchanged(self) -> None:
        self.assertEqual(tree_contents(self.source), self.original_before)
        after = self.paper.stat()
        for field in ("st_ino", "st_mode", "st_nlink", "st_mtime_ns", "st_ctime_ns"):
            self.assertEqual(getattr(after, field), getattr(self.paper_metadata, field))
        self.assertEqual(
            (self.home / ".codex/agents/other.toml").read_text(),
            "name = 'unrelated'\n",
        )

    def assert_rejected_without_removal(self, root: Path | None = None) -> None:
        before = self.registrations()
        with self.assertRaises((RuntimeError, OSError, ValueError)):
            with redirect_stdout(io.StringIO()):
                self.uninstaller.remove_project(root or self.project, self.home, yes=True)
        self.assertTrue(self.project.is_dir())
        self.assertEqual(self.registrations(), before)
        self.assert_originals_unchanged()

    def test_full_remove_trashes_install_and_data_preserving_external_files(self) -> None:
        # A link in generated data may point to a source, but must never be followed.
        (self.project / "knowledge/source-link").symlink_to(self.source, target_is_directory=True)
        result = self.remove(yes=True)

        self.assertIsInstance(result, Path)
        self.assertTrue(result.is_relative_to(self.trash))
        self.assertEqual(result.name, self.project.name)
        self.assertFalse(self.project.exists())
        self.assertEqual(
            (result / "knowledge/documents/paper.md").read_text(),
            "# Converted document\n",
        )
        self.assertEqual((result / ".research-store/library.sqlite").read_bytes(), b"saved state")
        self.assertTrue((result / "knowledge/source-link").is_symlink())
        for relative in REGISTRATIONS:
            self.assertFalse(os.path.lexists(self.home / relative), relative)
        self.assert_originals_unchanged()

    def test_keep_files_removes_registrations_only(self) -> None:
        result = self.remove(yes=True, keep_files=True)

        self.assertIsNone(result)
        self.assertTrue((self.project / "knowledge/documents/paper.md").is_file())
        for relative in REGISTRATIONS:
            self.assertFalse(os.path.lexists(self.home / relative), relative)
        self.assertEqual(list(self.trash.iterdir()), [])
        self.assert_originals_unchanged()

    def test_declined_confirmation_changes_nothing(self) -> None:
        before = self.registrations()
        with mock.patch("builtins.input", return_value="n"):
            result = self.remove(yes=False)

        self.assertIsNone(result)
        self.assertTrue(self.project.is_dir())
        self.assertEqual(self.registrations(), before)
        self.assertEqual(list(self.trash.iterdir()), [])
        self.assert_originals_unchanged()

    def test_preexisting_trash_items_are_never_overwritten(self) -> None:
        existing = self.trash / self.project.name
        existing.mkdir()
        (existing / "keep.txt").write_text("older installation\n", encoding="utf-8")
        result = self.remove(yes=True)

        self.assertNotEqual(result, existing)
        self.assertEqual((existing / "keep.txt").read_text(), "older installation\n")
        self.assertTrue((result / ".research-agent-root").is_file())
        self.assert_originals_unchanged()

    def test_other_installation_owner_stops_before_removal(self) -> None:
        other = self.home / ".codex/agents/research-paper-converter.toml"
        other.write_text("# owned by another installation\n", encoding="utf-8")
        self.assert_rejected_without_removal()

    def test_disabled_source_inside_install_is_protected(self) -> None:
        self.write_sources(self.project / "knowledge", enabled=False)
        self.assert_rejected_without_removal()

    def test_source_containing_install_is_protected(self) -> None:
        self.write_sources(self.home)
        self.assert_rejected_without_removal()

    def test_source_overlapping_owned_registration_is_protected(self) -> None:
        self.write_sources(self.home / ".codex/agents")
        self.assert_rejected_without_removal()

    def test_source_overlapping_trash_is_protected(self) -> None:
        self.write_sources(self.trash)
        self.assert_rejected_without_removal()

    def test_symlinked_trash_is_rejected(self) -> None:
        self.trash.rmdir()
        self.trash.symlink_to(self.source, target_is_directory=True)
        self.assert_rejected_without_removal()

    def test_symlinked_install_argument_is_rejected(self) -> None:
        alias = self.home / "installation-alias"
        alias.symlink_to(self.project, target_is_directory=True)
        self.assert_rejected_without_removal(alias)

    def test_missing_install_marker_is_rejected(self) -> None:
        (self.project / ".research-agent-root").unlink()
        self.assert_rejected_without_removal()

    def test_separate_process_holding_project_lock_blocks_removal(self) -> None:
        self.assert_process_lock_blocks_removal(self.project)

    def test_separate_process_holding_sync_lock_blocks_removal(self) -> None:
        lock = self.project / ".research-store/sync.lock"
        lock.touch()
        self.assert_process_lock_blocks_removal(lock)

    def test_separate_process_holding_marker_lock_blocks_removal(self) -> None:
        self.assert_process_lock_blocks_removal(self.project / ".research-agent-root")

    def assert_process_lock_blocks_removal(self, path: Path) -> None:
        child_code = (
            "import fcntl, os, sys; "
            "fd = os.open(sys.argv[1], os.O_RDONLY); "
            "fcntl.flock(fd, fcntl.LOCK_SH); "
            "print('locked', flush=True); sys.stdin.readline()"
        )
        with subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", child_code, str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        ) as child:
            try:
                self.assertEqual(child.stdout.readline().strip(), "locked")
                self.assert_rejected_without_removal()
            finally:
                child.communicate("release\n", timeout=10)
            self.assertEqual(child.returncode, 0)

    def test_staging_failure_restores_all_registrations(self) -> None:
        before = self.registrations()
        original_rename = os.rename
        targets = {self.home / relative for relative in REGISTRATIONS}
        count = 0

        def fail_second_stage(source, destination, *args, **kwargs):
            nonlocal count
            if Path(source) in targets:
                count += 1
                if count == 2:
                    raise OSError(errno.EACCES, "injected staging failure")
            return original_rename(source, destination, *args, **kwargs)

        with mock.patch.object(self.uninstaller.os, "rename", side_effect=fail_second_stage):
            with self.assertRaises((RuntimeError, OSError)):
                self.remove(yes=True)
        self.assertEqual(count, 2)
        self.assertTrue(self.project.is_dir())
        self.assertEqual(self.registrations(), before)
        self.assert_originals_unchanged()
        # The rollback must leave a usable installation, not just matching bytes.
        result = self.remove(yes=True)
        self.assertTrue(result.is_dir())

    def test_cross_volume_trash_failure_restores_registrations_and_data(self) -> None:
        before = self.registrations()
        original_rename = os.rename
        attempted = False

        def fail_final_move(source, destination, *args, **kwargs):
            nonlocal attempted
            if Path(source) == self.project:
                attempted = True
                raise OSError(errno.EXDEV, "injected cross-volume move")
            return original_rename(source, destination, *args, **kwargs)

        with mock.patch.object(self.uninstaller.os, "rename", side_effect=fail_final_move):
            with self.assertRaises((RuntimeError, OSError)):
                self.remove(yes=True)
        self.assertTrue(attempted)
        self.assertEqual(self.registrations(), before)
        self.assertEqual((self.project / ".research-store/library.sqlite").read_bytes(), b"saved state")
        self.assert_originals_unchanged()

    def test_trash_failure_restores_relative_skill_link_exactly(self) -> None:
        skill = self.home / REGISTRATIONS[0]
        target = self.project / "resources/skills/research-library"
        relative_target = os.path.relpath(target, skill.parent)
        skill.unlink()
        skill.symlink_to(relative_target, target_is_directory=True)
        before = self.registrations()
        original_rename = os.rename

        def fail_final_move(source, destination, *args, **kwargs):
            if Path(source) == self.project:
                raise OSError(errno.EACCES, "injected Trash move failure")
            return original_rename(source, destination, *args, **kwargs)

        with mock.patch.object(self.uninstaller.os, "rename", side_effect=fail_final_move):
            with self.assertRaises((RuntimeError, OSError)):
                self.remove(yes=True)

        self.assertEqual(os.readlink(skill), relative_target)
        self.assertEqual(skill.resolve(), target)
        self.assertEqual(self.registrations(), before)
        self.assert_originals_unchanged()

        result = self.remove(yes=True)

        self.assertFalse(self.project.exists())
        self.assertTrue((result / "knowledge/documents/paper.md").is_file())
        self.assert_originals_unchanged()

    def test_public_wrapper_yes_completes_full_removal(self) -> None:
        # Give the copied wrapper its own interpreter link without copying a venv.
        python = self.project / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        environment = dict(os.environ, HOME=str(self.home))
        result = subprocess.run(
            ["sh", str(self.project / "uninstall.sh"), "--yes"],
            env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.project.exists())
        self.assertEqual(len(list(self.trash.glob("*/research-agent/.research-agent-root"))), 1)
        self.assert_originals_unchanged()

    def test_retry_recovers_after_process_exits_during_registration_staging(self) -> None:
        child_code = """
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / 'scripts'))
import uninstall_project
root, home = Path(sys.argv[1]), Path(sys.argv[2])
original_rename = os.rename
targets = {
    home / '.agents/skills/research-library',
    home / '.codex/agents/research-library-manager.toml',
    home / '.codex/agents/research-paper-converter.toml',
    home / '.codex/rules/research-library.rules',
    home / '.codex/research-library-sandbox',
}
def interrupted(source, destination, *args, **kwargs):
    original_rename(source, destination, *args, **kwargs)
    if Path(source) in targets:
        os._exit(87)
uninstall_project.os.rename = interrupted
uninstall_project.remove_project(root, home, yes=True)
"""
        stopped = subprocess.run(
            [sys.executable, "-I", "-B", "-c", child_code, str(self.project), str(self.home)],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(stopped.returncode, 87, stopped.stderr)
        self.assertTrue(self.project.is_dir())
        self.assertTrue(any(not os.path.lexists(self.home / path) for path in REGISTRATIONS))

        result = self.remove(yes=True)

        self.assertFalse(self.project.exists())
        self.assertTrue((result / "knowledge/documents/paper.md").is_file())
        for relative in REGISTRATIONS:
            self.assertFalse(os.path.lexists(self.home / relative), relative)
        self.assert_originals_unchanged()

    def test_retry_recovers_after_process_exits_before_journal_publication(self) -> None:
        before = self.registrations()
        child_code = """
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / 'scripts'))
import uninstall_project
original_replace = os.replace
def interrupted(source, destination, *args, **kwargs):
    if Path(destination).name == 'journal.json':
        os._exit(88)
    original_replace(source, destination, *args, **kwargs)
uninstall_project.registration.os.replace = interrupted
uninstall_project.remove_project(Path(sys.argv[1]), Path(sys.argv[2]), yes=True)
"""
        stopped = subprocess.run(
            [sys.executable, "-I", "-B", "-c", child_code, str(self.project), str(self.home)],
            capture_output=True, text=True, timeout=20,
        )

        self.assertEqual(stopped.returncode, 88, stopped.stderr)
        self.assertTrue(self.project.is_dir())
        self.assertEqual(self.registrations(), before)
        self.assert_originals_unchanged()
        staging = self.project / ".research-agent-uninstall"
        self.assertFalse((staging / "journal.json").exists())
        self.assertEqual(len(list(staging.glob(".journal.json.*"))), 1)

        result = self.remove(yes=True)

        self.assertFalse(self.project.exists())
        self.assertTrue((result / "knowledge/documents/paper.md").is_file())
        for relative in REGISTRATIONS:
            self.assertFalse(os.path.lexists(self.home / relative), relative)
        self.assert_originals_unchanged()


if __name__ == "__main__":
    unittest.main()
