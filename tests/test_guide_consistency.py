from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1]
FILES = ("pyproject.toml", "README.md", "docs/en/user-guide.md", "docs/site/config.js", "docs/site/app.js", "docs/site/content-en.js")


class GuideConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in FILES:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT / relative, target)

    def check(self, expected_error: str | None = None) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(PROJECT / "scripts/check_guides.py"), "--root", str(self.root)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1 if expected_error else 0, result.stdout + result.stderr)
        if expected_error:
            self.assertIn(expected_error, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def replace(self, relative: str, old: str, new: str) -> None:
        path = self.root / relative
        path.write_text(path.read_text().replace(old, new))

    def test_current_guides(self) -> None:
        self.check()

    def test_one_translation_command_drifts(self) -> None:
        self.replace("docs/en/user-guide.md", "--tlsv1.2", "--tlsv1.3")
        self.check("docs/en/user-guide.md: installation command differs")

    def test_all_copies_can_agree_on_wrong_download(self) -> None:
        for relative in ("README.md", "docs/en/user-guide.md", "docs/site/config.js"):
            self.replace(relative, "https://github.com/LWH4Data", "https://example.invalid/LWH4Data")
        self.check("Installation download must be exactly")

    def test_missing_or_duplicate_installation_block(self) -> None:
        path = self.root / "README.md"
        original = path.read_text()
        for content in ("# Guide\n", original + "\n```sh\ncurl install-release.sh\n```\n"):
            with self.subTest(content=content[:20]):
                path.write_text(content)
                self.check("expected exactly one")

    def test_release_config_version_drift(self) -> None:
        path = self.root / "docs/site/config.js"
        config = json.loads(path.read_text().split("=", 1)[1].strip().removesuffix(";"))
        config["version"] = "999.0.0"
        path.write_text("window.RESEARCH_GUIDE_RELEASE = " + json.dumps(config) + ";\n")
        self.check("version must match pyproject.toml")

    def test_all_invocations_must_use_project_version(self) -> None:
        for relative in ("README.md", "docs/en/user-guide.md", "docs/site/config.js"):
            path = self.root / relative
            path.write_text(re.sub(r"--version \d+\.\d+\.\d+", "--version 999.0.0", path.read_text()))
        self.check("Installation must invoke")

    def test_stale_visible_web_label(self) -> None:
        version = tomllib.loads((self.root / "pyproject.toml").read_text())["project"]["version"]
        self.replace("docs/site/content-en.js", f"v{version}", "v999.0.0")
        self.check("visible release label differs")

    def test_malformed_config_reports_error(self) -> None:
        (self.root / "docs/site/config.js").write_text("window.RESEARCH_GUIDE_RELEASE = {broken};")
        self.check("Guide check failed")
