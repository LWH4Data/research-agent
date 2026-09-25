"""Opt-in command-level sandbox test; never registers a production installation.

Run outside an enclosing sandbox with RESEARCH_AGENT_RUN_IMPORT_SANDBOX_TEST=1.
RESEARCH_AGENT_SANDBOX_TEST_DIR can select a writable fixture parent outside
the OS temporary directory, which the real generated profile denies reading.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import venv

from pypdf import PdfWriter


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    os.environ.get("RESEARCH_AGENT_RUN_IMPORT_SANDBOX_TEST") == "1",
    "set RESEARCH_AGENT_RUN_IMPORT_SANDBOX_TEST=1 outside an existing sandbox",
)
class ImportPermissionIntegrationTests(unittest.TestCase):
    def test_real_launcher_imports_attachment_without_temporary_read_grant(self) -> None:
        codex = shutil.which("codex")
        if codex is None:
            self.skipTest("Codex CLI is not available")
        base = Path(os.environ.get("RESEARCH_AGENT_SANDBOX_TEST_DIR", Path.cwd())).resolve()
        if not base.is_dir():
            self.fail("RESEARCH_AGENT_SANDBOX_TEST_DIR must be an existing directory")
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if base == temporary_root or base.is_relative_to(temporary_root):
            self.fail("The disposable store must be outside the denied OS temporary directory")

        with tempfile.TemporaryDirectory(prefix=".research-import-sandbox-", dir=base) as directory, \
             tempfile.TemporaryDirectory(prefix="research-attachment-") as attachments:
            fixture = Path(directory).resolve()
            store = fixture / "store"
            home = fixture / "home"
            store.mkdir()
            home.mkdir()
            for name in (".research-agent-root", "AGENTS.md", "research-store"):
                shutil.copy2(ROOT / name, store / name)
            for name in ("src", "resources", "scripts"):
                shutil.copytree(ROOT / name, store / name,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

            # Use the real store/launcher code with an offline disposable runtime.
            # Dependencies are read from this test interpreter, never installed.
            venv.EnvBuilder(with_pip=False, symlinks=False).create(store / ".venv")
            python = store / ".venv/bin/python"
            sites = list((store / ".venv/lib").glob("python*/site-packages"))
            self.assertEqual(len(sites), 1)
            dependencies = [path for path in sys.path if Path(path).name == "site-packages"]
            (sites[0] / "fixture.pth").write_text(
                str(store / "src") + "\n" + "\n".join(dependencies) + "\n",
                encoding="utf-8",
            )
            entry = store / ".venv/bin/research-store"
            entry.write_text(
                "#!/bin/sh\nexec " + shlex.quote(str(python))
                + " -I -B -c 'from research_store.cli import main; raise SystemExit(main())' \"$@\"\n",
                encoding="utf-8",
            )
            entry.chmod(0o700)
            initialized = subprocess.run(
                [str(store / "research-store"), "init"],
                capture_output=True, text=True,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            registered = subprocess.run(
                [str(python), "-I", "-B", str(store / "scripts/personal_registration.py"),
                 "install", "--root", str(store), "--home", str(home)],
                capture_output=True, text=True,
            )
            self.assertEqual(registered.returncode, 0, registered.stderr)

            sandbox = home / ".codex/research-library-sandbox"
            profile = tomllib.loads((sandbox / "config.toml").read_text())["permissions"]["research-store"]
            self.assertEqual(profile["filesystem"][":tmpdir"], "deny")
            self.assertEqual(profile["filesystem"][":slash_tmp"], "deny")
            self.assertEqual(profile["filesystem"][":root"], "read")
            self.assertEqual(
                {path for path, access in profile["filesystem"].items() if access == "write"},
                {str(store / ".research-store"), str(store / "knowledge")},
            )
            self.assertFalse(profile["network"]["enabled"])

            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            data = io.BytesIO()
            writer.write(data)
            source = Path(attachments).resolve() / "attached.pdf"
            source.write_bytes(data.getvalue())
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            environment = dict(os.environ)
            environment["HOME"] = str(home)
            environment.pop("CODEX_HOME", None)
            launcher = home / ".agents/skills/research-library/scripts/research-store"

            # The ordinary path form must not acquire a temporary read grant.
            direct = subprocess.run(
                [str(launcher), "import-pdf", str(source)], env=environment,
                capture_output=True, timeout=60,
            )
            self.assertNotEqual(direct.returncode, 0, direct.stdout.decode(errors="replace"))
            self.assertRegex(direct.stderr.decode(errors="replace"),
                             r"(?i)(permission denied|operation not permitted)")
            imported = subprocess.run(
                [str(launcher), "import-pdf", "--attachment", str(source)],
                env=environment,
                capture_output=True, timeout=60,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr.decode(errors="replace"))
            result = json.loads(imported.stdout)
            self.assertTrue(result["stored"])
            self.assertFalse(result["duplicate"])
            stored_pdf = Path(result["stored_pdf"])
            self.assertTrue(stored_pdf.is_relative_to(store / ".research-store/imports"))
            self.assertEqual(hashlib.sha256(stored_pdf.read_bytes()).hexdigest(), original_hash)

            # The low-level stdin interface stays available to non-shell callers.
            duplicate = subprocess.run(
                [str(launcher), "import-pdf", "--stdin", "--name", source.name],
                input=source.read_bytes(), env=environment,
                capture_output=True, timeout=60,
            )
            self.assertEqual(duplicate.returncode, 0, duplicate.stderr.decode(errors="replace"))
            self.assertTrue(json.loads(duplicate.stdout)["duplicate"])

            # Deliberately attempt an overwrite only on the disposable original.
            # The generated permission profile must prevent it.
            sandbox_environment = dict(environment)
            sandbox_environment["CODEX_HOME"] = str(sandbox)
            write_attempt = subprocess.run(
                [codex, "sandbox", "-P", "research-store", "-C", str(sandbox), "--",
                 "/bin/sh", "-c", 'printf changed > "$1"', "sh", str(source)],
                env=sandbox_environment, capture_output=True, timeout=60,
            )
            self.assertNotEqual(write_attempt.returncode, 0)
            self.assertRegex(write_attempt.stderr.decode(errors="replace"),
                             r"(?i)(permission denied|operation not permitted)")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)


if __name__ == "__main__":
    unittest.main()
