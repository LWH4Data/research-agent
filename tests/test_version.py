from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from research_store import __version__
from research_store import cli


PROJECT = Path(__file__).resolve().parents[1]
PACKAGE_INIT = PROJECT / "src/research_store/__init__.py"


class VersionTests(unittest.TestCase):
    def _copy_package(self, import_root: Path) -> None:
        package = import_root / "research_store"
        package.mkdir(parents=True)
        shutil.copyfile(PACKAGE_INIT, package / "__init__.py")

    def _metadata(self, import_root: Path, value: str) -> None:
        info = import_root / f"research_store-{value}.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: research-store\nVersion: {value}\n",
            encoding="utf-8",
        )

    def _import_version(self, import_root: Path, cwd: Path) -> str:
        result = subprocess.run(
            [
                sys.executable, "-I", "-S", "-B", "-c",
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import research_store; print(research_store.__version__)",
                str(import_root),
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_checkout_version_matches_project(self) -> None:
        with (PROJECT / "pyproject.toml").open("rb") as stream:
            expected = tomllib.load(stream)["project"]["version"]
        self.assertEqual(__version__, expected)

    def test_source_version_takes_precedence_over_stale_editable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src"
            self._copy_package(source)
            self._metadata(source, "1.0.0")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "research-store"\nversion = "2.3.4"\n',
                encoding="utf-8",
            )
            self.assertEqual(self._import_version(source, root), "2.3.4")

    def test_wheel_layout_uses_metadata_and_ignores_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "site-packages"
            self._copy_package(installed)
            self._metadata(installed, "3.4.5")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "research-store"\nversion = "9.9.9"\n',
                encoding="utf-8",
            )
            self.assertEqual(self._import_version(installed, root), "3.4.5")

    def test_unrelated_source_project_does_not_override_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src"
            self._copy_package(source)
            self._metadata(source, "4.5.6")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "another-project"\nversion = "9.9.9"\n',
                encoding="utf-8",
            )
            self.assertEqual(self._import_version(source, root), "4.5.6")

    def test_package_copy_without_metadata_reports_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "src"
            self._copy_package(source)
            self.assertEqual(self._import_version(source, root), "0+unknown")

    def test_cli_version_does_not_require_a_library_or_read_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_config = Path(directory) / "missing.toml"
            output = io.StringIO()
            with (
                patch.object(sys, "argv", ["research-store", "--config", str(missing_config), "--version"]),
                patch.object(cli, "_config_path", side_effect=AssertionError("config must not be read")),
                patch.object(cli, "operation_guard", side_effect=AssertionError("library must not be opened")),
                redirect_stdout(output),
                self.assertRaises(SystemExit) as exited,
            ):
                cli.main()
            self.assertEqual(exited.exception.code, 0)
            self.assertEqual(output.getvalue(), f"research-store {__version__}\n")
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
