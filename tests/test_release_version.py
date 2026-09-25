from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "scripts/check_release_version.py"
PROJECT = '[project]\nname = "research-store"\nversion = "0.3.0"\n'
LOCK = '''version = 1
[[package]]
name = "research-store"
version = "0.3.0"
source = { editable = "." }
'''


class ReleaseVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "pyproject.toml"
        self.lock = self.root / "uv.lock"
        self.project.write_text(PROJECT, encoding="utf-8")
        self.lock.write_text(LOCK, encoding="utf-8")

    def run_checker(self, *args: str) -> subprocess.CompletedProcess[str]:
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        result = subprocess.run(
            [sys.executable, "-B", str(CHECKER), "--root", str(self.root), *args],
            capture_output=True, text=True, check=False,
        )
        after = {path.name: path.read_bytes() for path in self.root.iterdir()}
        self.assertEqual(after, before, "Release preflight must not create or alter files.")
        return result

    def assert_rejected(self, expected: str, *args: str) -> None:
        result = self.run_checker(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(expected, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_valid_metadata_without_tag(self) -> None:
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Version: 0.3.0", result.stdout)
        self.assertIn("Expected tag: v0.3.0", result.stdout)
        self.assertIn("Runtime archive name (not created): research-agent-0.3.0.tar.gz", result.stdout)

    def test_matching_tag(self) -> None:
        result = self.run_checker("--tag", "v0.3.0")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_incorrect_tag_and_missing_prefix(self) -> None:
        for tag in ("v0.4.0", "0.3.0", "v0.3.0-extra", "", "v0.3.0\n"):
            with self.subTest(tag=tag):
                self.assert_rejected("Tag mismatch", "--tag", tag)

    def test_root_lock_version_mismatch(self) -> None:
        self.lock.write_text(LOCK.replace('version = "0.3.0"', 'version = "0.2.0"'), encoding="utf-8")
        self.assert_rejected("Version mismatch")

    def test_matches_editable_root_instead_of_dependency_with_same_name(self) -> None:
        dependency = '''
[[package]]
name = "research-store"
version = "9.9.9"
source = { registry = "https://example.invalid/simple" }
[[package]]
name = "other-package"
version = "0.3.0"
source = { editable = "./other" }
'''
        self.lock.write_text(LOCK + dependency, encoding="utf-8")
        result = self.run_checker("--tag", "v0.3.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.lock.write_text(LOCK.replace('version = "0.3.0"', 'version = "0.2.0"') + dependency, encoding="utf-8")
        self.assert_rejected("Version mismatch")

    def test_registry_package_cannot_replace_editable_root(self) -> None:
        self.lock.write_text(LOCK.replace('editable = "."', 'registry = "https://example.invalid/simple"'), encoding="utf-8")
        self.assert_rejected("exactly one research-store package")

    def test_duplicate_editable_root_is_ambiguous(self) -> None:
        self.lock.write_text(LOCK + LOCK.removeprefix("version = 1\n"), encoding="utf-8")
        self.assert_rejected("exactly one research-store package")

    def test_missing_metadata_files(self) -> None:
        for path in (self.project, self.lock):
            with self.subTest(file=path.name):
                content = path.read_bytes()
                path.unlink()
                self.assert_rejected(f"Cannot read {path.name}")
                path.write_bytes(content)

    def test_malformed_toml(self) -> None:
        for path in (self.project, self.lock):
            with self.subTest(file=path.name):
                content = path.read_bytes()
                path.write_text("[unfinished", encoding="utf-8")
                self.assert_rejected(f"Cannot read {path.name}")
                path.write_bytes(content)

    def test_missing_or_invalid_project_version(self) -> None:
        for version_line in ("", "version = 3", 'version = ""', 'version = "0.3"', 'version = "00.3.0"', 'version = "../bad"'):
            with self.subTest(version_line=version_line):
                self.project.write_text('[project]\nname = "research-store"\n' + version_line, encoding="utf-8")
                self.assert_rejected("[project].version must use X.Y.Z")

    def test_missing_or_invalid_lock_version(self) -> None:
        for version_line in ("", "version = 3", 'version = "bad"'):
            with self.subTest(version_line=version_line):
                self.lock.write_text(LOCK.replace('version = "0.3.0"', version_line), encoding="utf-8")
                self.assert_rejected("editable research-store version in uv.lock must use X.Y.Z")

    def test_invalid_lock_structure(self) -> None:
        for lock in ('version = 1\n', 'version = 1\npackage = "wrong"', 'version = 1\npackage = [1]', LOCK.replace('version = 1', 'version = "1"'), LOCK.replace('version = 1\n', '')):
            with self.subTest(lock=lock):
                self.lock.write_text(lock, encoding="utf-8")
                self.assert_rejected("uv.lock")

    def test_missing_or_wrong_project_name(self) -> None:
        for project in ('version = "0.3.0"', '[project]\nversion = "0.3.0"', PROJECT.replace('"research-store"', '"other-package"')):
            with self.subTest(project=project):
                self.project.write_text(project, encoding="utf-8")
                self.assert_rejected("[project].name")

    def test_dynamic_version_is_not_authoritative(self) -> None:
        self.project.write_text(PROJECT + 'dynamic = ["version"]\n', encoding="utf-8")
        self.assert_rejected("must be static")

    def test_malformed_dynamic_metadata(self) -> None:
        for dynamic in ('3', '"version"', '[1]'):
            with self.subTest(dynamic=dynamic):
                self.project.write_text(PROJECT + f'dynamic = {dynamic}\n', encoding="utf-8")
                self.assert_rejected("[project].dynamic must be a list")


if __name__ == "__main__":
    unittest.main()
