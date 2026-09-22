from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from research_store import safety


GENERATED_PREFIXES = (".tmp-", ".backup-", ".restore-", ".delete-")


def make_project(path: Path) -> Path:
    path.mkdir()
    (path / safety.PROJECT_MARKER).write_text(
        safety.PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
    )
    return path.resolve()


class SafetyFailureTests(unittest.TestCase):
    def assert_no_generated_files(self, directory: Path) -> None:
        generated = sorted(
            path.name
            for path in directory.iterdir()
            if path.name.startswith(GENERATED_PREFIXES)
        )
        self.assertEqual(generated, [])

    def directory_fsync_failure(self, failure_number: int):
        real_fsync = os.fsync
        calls = 0

        def flaky_fsync(descriptor: int) -> None:
            nonlocal calls
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                calls += 1
                if calls == failure_number:
                    raise OSError(f"injected directory fsync failure {calls}")
            real_fsync(descriptor)

        return mock.patch.object(safety.os, "fsync", side_effect=flaky_fsync)

    def test_atomic_text_restores_old_content_when_install_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("old", encoding="utf-8")
            real_replace = os.replace

            def flaky_replace(source, destination, *args, **kwargs):
                if str(source).startswith(".tmp-") and destination == target.name:
                    raise OSError("injected replace failure")
                return real_replace(source, destination, *args, **kwargs)

            with mock.patch.object(
                safety.os, "replace", side_effect=flaky_replace
            ):
                with self.assertRaisesRegex(OSError, "injected replace"):
                    safety.atomic_text(target, "new", project)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assert_no_generated_files(project)

    def test_atomic_text_restores_old_content_after_completed_replace_raises(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("old", encoding="utf-8")
            real_replace = os.replace

            def flaky_replace(source, destination, *args, **kwargs):
                result = real_replace(source, destination, *args, **kwargs)
                if str(source).startswith(".tmp-") and destination == target.name:
                    raise OSError("injected post-replace failure")
                return result

            with mock.patch.object(
                safety.os, "replace", side_effect=flaky_replace
            ):
                with self.assertRaisesRegex(OSError, "post-replace"):
                    safety.atomic_text(target, "new", project)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assert_no_generated_files(project)

    def test_atomic_text_keeps_old_content_when_backup_fsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("old", encoding="utf-8")
            real_fsync = os.fsync
            regular_calls = 0

            def flaky_fsync(descriptor: int) -> None:
                nonlocal regular_calls
                if stat.S_ISREG(os.fstat(descriptor).st_mode):
                    regular_calls += 1
                    if regular_calls == 2:
                        self.assertEqual(
                            target.read_text(encoding="utf-8"), "old"
                        )
                        raise OSError("injected backup fsync failure")
                real_fsync(descriptor)

            with mock.patch.object(safety.os, "fsync", side_effect=flaky_fsync):
                with self.assertRaisesRegex(OSError, "backup fsync"):
                    safety.atomic_text(target, "new", project)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assert_no_generated_files(project)

    def test_atomic_text_restores_old_content_when_target_fsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("old", encoding="utf-8")

            with self.directory_fsync_failure(2):
                with self.assertRaisesRegex(OSError, "fsync failure 2"):
                    safety.atomic_text(target, "new", project)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assert_no_generated_files(project)

    def test_atomic_text_recreates_old_content_when_backup_unlink_then_raises(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("old", encoding="utf-8")
            real_unlink = os.unlink

            def flaky_unlink(path, *args, **kwargs):
                result = real_unlink(path, *args, **kwargs)
                if str(path).startswith(".backup-"):
                    raise OSError("injected post-unlink failure")
                return result

            with mock.patch.object(
                safety.os, "unlink", side_effect=flaky_unlink
            ):
                with self.assertRaisesRegex(OSError, "post-unlink"):
                    safety.atomic_text(target, "new", project)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assert_no_generated_files(project)

    def test_atomic_text_recreates_old_content_when_cleanup_fsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("old", encoding="utf-8")

            with self.directory_fsync_failure(3):
                with self.assertRaisesRegex(OSError, "fsync failure 3"):
                    safety.atomic_text(target, "new", project)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assert_no_generated_files(project)

    def test_atomic_text_removes_new_target_when_directory_fsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"

            with self.directory_fsync_failure(1):
                with self.assertRaisesRegex(OSError, "fsync failure 1"):
                    safety.atomic_text(target, "new", project)

            self.assertFalse(target.exists())
            self.assert_no_generated_files(project)

    def test_removal_restores_target_when_initial_replace_completes_then_raises(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("keep", encoding="utf-8")
            real_replace = os.replace
            entered = False

            def flaky_replace(source, destination, *args, **kwargs):
                result = real_replace(source, destination, *args, **kwargs)
                if source == target.name and str(destination).startswith(".delete-"):
                    raise OSError("injected staging failure")
                return result

            with mock.patch.object(
                safety.os, "replace", side_effect=flaky_replace
            ):
                with self.assertRaisesRegex(OSError, "staging failure"):
                    with safety.staged_owned_file_removal(
                        target, project, label="test record"
                    ):
                        entered = True

            self.assertFalse(entered)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assert_no_generated_files(project)

    def test_removal_restores_target_when_pre_yield_fsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("keep", encoding="utf-8")
            entered = False

            with self.directory_fsync_failure(1):
                with self.assertRaisesRegex(OSError, "fsync failure 1"):
                    with safety.staged_owned_file_removal(
                        target, project, label="test record"
                    ):
                        entered = True

            self.assertFalse(entered)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assert_no_generated_files(project)

    def test_removal_restores_target_when_recovery_open_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("keep", encoding="utf-8")
            real_open = os.open

            def flaky_open(path, *args, **kwargs):
                if str(path).startswith(".delete-"):
                    raise OSError("injected staged open failure")
                return real_open(path, *args, **kwargs)

            with mock.patch.object(safety.os, "open", side_effect=flaky_open):
                with self.assertRaisesRegex(OSError, "staged open failure"):
                    with safety.staged_owned_file_removal(
                        target, project, label="test record"
                    ):
                        self.fail("removal body must not run")

            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assert_no_generated_files(project)

    def test_removal_restores_target_when_body_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "injected body failure"):
                with safety.staged_owned_file_removal(
                    target, project, label="test record"
                ):
                    raise RuntimeError("injected body failure")

            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assert_no_generated_files(project)

    def test_removal_restores_target_when_cleanup_unlink_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("keep", encoding="utf-8")
            real_unlink = os.unlink

            def flaky_unlink(path, *args, **kwargs):
                if str(path).startswith(".delete-"):
                    raise OSError("injected cleanup failure")
                return real_unlink(path, *args, **kwargs)

            with mock.patch.object(
                safety.os, "unlink", side_effect=flaky_unlink
            ):
                with self.assertRaisesRegex(OSError, "cleanup failure"):
                    with safety.staged_owned_file_removal(
                        target, project, label="test record"
                    ):
                        self.assertFalse(target.exists())

            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assert_no_generated_files(project)

    def test_removal_recreates_target_when_cleanup_unlink_then_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("keep", encoding="utf-8")
            real_unlink = os.unlink

            def flaky_unlink(path, *args, **kwargs):
                result = real_unlink(path, *args, **kwargs)
                if str(path).startswith(".delete-"):
                    raise OSError("injected post-cleanup failure")
                return result

            with mock.patch.object(
                safety.os, "unlink", side_effect=flaky_unlink
            ):
                with self.assertRaisesRegex(OSError, "post-cleanup"):
                    with safety.staged_owned_file_removal(
                        target, project, label="test record"
                    ):
                        self.assertFalse(target.exists())

            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assert_no_generated_files(project)

    def test_removal_recreates_target_when_cleanup_fsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("keep", encoding="utf-8")

            with self.directory_fsync_failure(2):
                with self.assertRaisesRegex(OSError, "fsync failure 2"):
                    with safety.staged_owned_file_removal(
                        target, project, label="test record"
                    ):
                        self.assertFalse(target.exists())

            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assert_no_generated_files(project)

    def test_removal_success_unlinks_target_and_staging_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("remove", encoding="utf-8")

            with safety.staged_owned_file_removal(
                target, project, label="test record"
            ):
                self.assertFalse(target.exists())

            self.assertFalse(target.exists())
            self.assert_no_generated_files(project)

    def test_journaled_unlink_is_durable_and_missing_ok_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("remove", encoding="utf-8")

            self.assertTrue(
                safety.unlink_owned_file(
                    target, project, label="journaled record"
                )
            )
            self.assertFalse(target.exists())
            self.assertFalse(
                safety.unlink_owned_file(
                    target,
                    project,
                    label="journaled record",
                    missing_ok=True,
                )
            )
            self.assertFalse(
                safety.unlink_owned_file(
                    project / "missing" / "record.md",
                    project,
                    label="journaled record",
                    missing_ok=True,
                )
            )

    def test_journaled_unlink_rejects_hard_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            linked = project / "linked.md"
            target.write_text("keep", encoding="utf-8")
            os.link(target, linked)

            with self.assertRaisesRegex(ValueError, "하드 링크"):
                safety.unlink_owned_file(
                    target, project, label="journaled record"
                )

            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assertEqual(linked.read_text(encoding="utf-8"), "keep")

    def test_journaled_unlink_leaves_delete_applied_when_fsync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "record.md"
            target.write_text("remove", encoding="utf-8")

            with self.directory_fsync_failure(1):
                with self.assertRaisesRegex(OSError, "fsync failure 1"):
                    safety.unlink_owned_file(
                        target, project, label="journaled record"
                    )

            # The caller has already journaled the deletion intent. Recovery
            # finishes that deletion instead of recreating the old file.
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
