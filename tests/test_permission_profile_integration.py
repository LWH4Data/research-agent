from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = ROOT / "scripts/personal_registration.py"


@unittest.skipUnless(
    os.environ.get("RESEARCH_AGENT_RUN_SANDBOX_TEST") == "1",
    "set RESEARCH_AGENT_RUN_SANDBOX_TEST=1 outside an existing sandbox",
)
class PermissionProfileIntegrationTests(unittest.TestCase):
    def test_store_write_is_allowed_and_external_write_is_denied(self) -> None:
        codex = shutil.which("codex")
        if codex is None:
            self.skipTest("Codex CLI is not available")

        source_directory = Path(
            tempfile.mkdtemp(prefix=".research-agent-source-probe-", dir=Path.home())
        )
        source = source_directory / "original.txt"
        allowed = ROOT / ".research-store/.permission-profile-probe.txt"
        code_probe = ROOT / ".permission-profile-root-probe.txt"
        source.write_text("original\n", encoding="utf-8")
        try:
            with tempfile.TemporaryDirectory(prefix="research-agent-home-") as directory:
                home = Path(directory).resolve()
                installed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        str(REGISTRATION),
                        "install",
                        "--root",
                        str(ROOT),
                        "--home",
                        str(home),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(installed.returncode, 0, installed.stderr)
                environment = dict(os.environ)
                environment["CODEX_HOME"] = str(
                    home / ".codex/research-library-sandbox"
                )

                permitted = subprocess.run(
                    [
                        codex,
                        "sandbox",
                        "-P",
                        "research-store",
                        "-C",
                        str(ROOT),
                        "--",
                        "/bin/sh",
                        "-c",
                        "printf allowed > " + shlex.quote(str(allowed)),
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                denied = subprocess.run(
                    [
                        codex,
                        "sandbox",
                        "-P",
                        "research-store",
                        "-C",
                        str(ROOT),
                        "--",
                        "/bin/sh",
                        "-c",
                        "printf changed > " + shlex.quote(str(source)),
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                code_denied = subprocess.run(
                    [
                        codex,
                        "sandbox",
                        "-P",
                        "research-store",
                        "-C",
                        str(ROOT),
                        "--",
                        "/bin/sh",
                        "-c",
                        "printf changed > " + shlex.quote(str(code_probe)),
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(permitted.returncode, 0, permitted.stderr)
                self.assertEqual(allowed.read_text(encoding="utf-8"), "allowed")
                self.assertNotEqual(denied.returncode, 0)
                self.assertEqual(source.read_text(encoding="utf-8"), "original\n")
                self.assertNotEqual(code_denied.returncode, 0)
                self.assertFalse(code_probe.exists())
                removed = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        str(REGISTRATION),
                        "uninstall",
                        "--root",
                        str(ROOT),
                        "--home",
                        str(home),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(removed.returncode, 0, removed.stderr)
                self.assertFalse(
                    (home / ".codex/research-library-sandbox").exists(),
                    list((home / ".codex/research-library-sandbox").glob("**/*")),
                )
        finally:
            if allowed.exists():
                allowed.unlink()
            if code_probe.exists():
                code_probe.unlink()
            shutil.rmtree(source_directory)


if __name__ == "__main__":
    unittest.main()
