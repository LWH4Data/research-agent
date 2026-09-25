from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from research_store import cli
from research_store.config import load_config
from research_store.sources import (
    add_sources, default_config_path, initialize_config, remove_sources, source_rows,
)


class SourceSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "agent"
        self.project.mkdir()
        (self.project / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
        self.config = default_config_path(self.project)
        self.folders = [self.base / name for name in ("자료 1", "folder two", "folder-three")]
        for folder in self.folders:
            folder.mkdir()
            (folder / "original.pdf").write_bytes(b"original bytes; never parsed during registration")
        self.before = self.source_snapshot()

    def source_snapshot(self):
        return {
            str(path): (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
            for folder in self.folders for path in folder.rglob("*") if path.is_file()
        }

    def run_add(self, *paths: Path):
        output = io.StringIO()
        with mock.patch("sys.argv", ["research-store", "--config", str(self.config), "source-add", *map(str, paths)]):
            with redirect_stdout(output):
                cli.main()
        return json.loads(output.getvalue())

    def assert_sources_unchanged(self):
        self.assertEqual(self.source_snapshot(), self.before)
        for folder in self.folders:
            self.assertEqual([path.name for path in folder.iterdir()], ["original.pdf"])

    def test_picker_registers_three_folders_in_one_call_without_changing_sources(self):
        with mock.patch("research_store.cli.choose_sources", return_value=self.folders) as picker:
            result = self.run_add()
        picker.assert_called_once_with()
        self.assertEqual(len(result["added"]), 3)
        self.assertFalse(result["cancelled"])
        self.assertEqual({row["path"] for row in source_rows(self.config)}, set(map(str, self.folders)))
        self.assertTrue(all(row["access"] == "read-only" for row in source_rows(self.config)))
        self.assert_sources_unchanged()

    def test_multiple_explicit_paths_do_not_open_picker(self):
        with mock.patch("research_store.cli.choose_sources") as picker:
            result = self.run_add(*self.folders)
        picker.assert_not_called()
        self.assertEqual(len(result["added"]), 3)
        self.assert_sources_unchanged()

    def test_cancel_does_not_create_or_change_config(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    add_sources(self.config, [self.folders[0]])
                before = self.config.read_bytes() if self.config.exists() else None
                with mock.patch("research_store.cli.choose_sources", return_value=[]):
                    self.assertEqual(self.run_add(), {"added": [], "cancelled": True})
                after = self.config.read_bytes() if self.config.exists() else None
                self.assertEqual(after, before)
        self.assert_sources_unchanged()

    def test_existing_and_repeated_paths_are_skipped_without_new_ids(self):
        original = add_sources(self.config, [self.folders[0]])[0]
        result = self.run_add(self.folders[0], self.folders[1], self.folders[1], self.folders[2])
        self.assertEqual(len(result["added"]), 2)
        rows = source_rows(self.config)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["id"], original.id)
        before = self.config.read_bytes()
        again = self.run_add(*self.folders)
        self.assertEqual(again, {"added": [], "cancelled": False})
        self.assertEqual(self.config.read_bytes(), before)
        self.assert_sources_unchanged()

    def test_overlap_rejects_entire_batch_in_both_orders(self):
        nested = self.folders[0] / "nested"
        nested.mkdir()
        for parent_first in (True, False):
            with self.subTest(parent_first=parent_first):
                initialize_config(self.config)
                before = self.config.read_bytes()
                pair = [self.folders[0], nested] if parent_first else [nested, self.folders[0]]
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        self.run_add(self.folders[1], *pair)
                self.assertEqual(self.config.read_bytes(), before)
                self.assertEqual(source_rows(self.config), [])
        self.assertEqual(self.source_snapshot(), self.before)

    def test_registered_parent_rejects_nested_folder_without_partial_add(self):
        nested = self.folders[0] / "nested"
        nested.mkdir()
        add_sources(self.config, [self.folders[0]])
        before = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, "겹칩니다"):
            add_sources(self.config, [self.folders[1], nested])
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.source_snapshot(), self.before)

    def test_unavailable_path_prevents_partial_registration(self):
        initialize_config(self.config)
        before = self.config.read_bytes()
        with self.assertRaisesRegex(ValueError, "찾을 수 없습니다"):
            add_sources(self.config, [self.folders[0], self.base / "missing"])
        self.assertEqual(self.config.read_bytes(), before)
        self.assert_sources_unchanged()

    def test_codex_runtime_folder_cannot_be_registered_as_original_source(self):
        pretend_home = self.base / "user-home"
        runtime = pretend_home / ".codex"
        runtime.mkdir(parents=True)
        runtime_pdf = runtime / "paper.pdf"
        runtime_pdf.write_bytes(b"PDF data")
        initialize_config(self.config)
        before = self.config.read_bytes()
        with mock.patch("pathlib.Path.home", return_value=pretend_home):
            for forbidden in (pretend_home, runtime, runtime_pdf):
                with self.subTest(path=forbidden):
                    with self.assertRaisesRegex(ValueError, "Codex 내부 폴더"):
                        add_sources(self.config, [self.folders[0], forbidden])
                    self.assertEqual(self.config.read_bytes(), before)
            self.config.write_text(
                self.config.read_text(encoding="utf-8")
                + f'\n[[sources]]\nid = "tampered"\npath = "{runtime}"\nkind = "directory"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Codex 내부 폴더"):
                load_config(self.config)

    def test_disabled_source_keeps_id_when_reenabled_in_batch(self):
        original = add_sources(self.config, [self.folders[0]])[0]
        remove_sources(self.config, [original.id])
        result = self.run_add(*self.folders)
        self.assertEqual(len(result["added"]), 3)
        rows = source_rows(self.config)
        self.assertEqual(rows[0]["id"], original.id)
        self.assertTrue(all(row["enabled"] for row in rows))
        self.assert_sources_unchanged()


if __name__ == "__main__":
    unittest.main()
