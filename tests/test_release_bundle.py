from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1]
ARCHIVE = os.environ.get("RESEARCH_AGENT_RELEASE_ARCHIVE")


@unittest.skipUnless(ARCHIVE, "Set RESEARCH_AGENT_RELEASE_ARCHIVE to test an assembled release")
class ReleaseBundleTests(unittest.TestCase):
    def test_exact_product_files_and_canonical_rules(self) -> None:
        expected = {}
        for line in (PROJECT / "packaging/runtime-files.txt").read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                fields = line.split()
                expected["research-agent/" + fields[-1]] = PROJECT / fields[0]
        with tarfile.open(ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual(len({item.name for item in members}), len(members))
            self.assertTrue(all(item.isfile() or item.isdir() for item in members))
            actual = {item.name for item in members if item.isfile()}
            self.assertEqual(actual, set(expected))
            for name, path in expected.items():
                self.assertEqual(archive.extractfile(name).read(), path.read_bytes(), name)
            rules = archive.extractfile("research-agent/AGENTS.md").read()
            self.assertNotIn(b"# Research Agent development", rules)
            for path in ("research-store", "resources/skills/research-library/scripts/research-store", "resources/skills/research-library/scripts/research-review"):
                self.assertTrue(archive.getmember("research-agent/" + path).mode & 0o111, path)
        with (PROJECT / "pyproject.toml").open("rb") as stream:
            version = tomllib.load(stream)["project"]["version"]
        self.assertEqual(Path(ARCHIVE).name, f"research-agent-{version}.tar.gz")
        checksum = hashlib.sha256(Path(ARCHIVE).read_bytes()).hexdigest()
        self.assertIn(f"{checksum}  {Path(ARCHIVE).name}", Path(ARCHIVE).with_name("SHA256SUMS").read_text().splitlines())

    @unittest.skipUnless(sys.platform == "darwin", "First-release install/remove check targets macOS")
    def test_install_search_and_remove_in_disposable_home(self) -> None:
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        with tempfile.TemporaryDirectory(prefix="research-release-") as directory:
            temporary = Path(directory).resolve()
            home = temporary / "test home"
            home.mkdir()
            (home / ".Trash").mkdir()
            with tarfile.open(ARCHIVE, "r:gz") as archive:
                archive.extractall(home, filter="data")
            installation = home / "research-agent"
            environment = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
            environment.pop("CODEX_HOME", None)
            environment.pop("PYTHONPATH", None)

            def run(*arguments: str) -> subprocess.CompletedProcess[str]:
                result = subprocess.run(
                    arguments, cwd=home, env=environment, stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, timeout=300, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            run("bash", str(installation / "install.sh"))
            with (PROJECT / "pyproject.toml").open("rb") as stream:
                version = tomllib.load(stream)["project"]["version"]
            self.assertEqual(run(str(installation / "research-store"), "--version").stdout.strip(), f"research-store {version}")
            skill = home / ".agents/skills/research-library"
            self.assertEqual(skill.resolve(), installation / "resources/skills/research-library")
            for name in ("research-library-manager", "research-paper-converter"):
                agent = (home / f".codex/agents/{name}.toml").read_text()
                self.assertIn(str(installation / "resources/AGENTS.runtime.md"), agent)
                self.assertNotIn(str(installation / "AGENTS.md"), agent)

            source = temporary / "original source"
            source.mkdir()
            original = source / "fixture.pdf"
            writer = PdfWriter()
            page = writer.add_blank_page(width=300, height=200)
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            text = DecodedStreamObject()
            text.set_data(b"BT /F1 12 Tf 20 100 Td (Prototype release retrieval fixture) Tj ET")
            page[NameObject("/Contents")] = writer._add_object(text)
            with original.open("wb") as stream:
                writer.write(stream)
            before = original.read_bytes()
            before_stat = original.stat()
            command = str(installation / "research-store")
            run(command, "source-add", str(source))
            run(command, "sync", "--progress", "off")
            search = run(command, "search", "retrieval")
            self.assertIn("retrieval", search.stdout.lower())
            self.assertTrue(any((installation / "knowledge/documents").rglob("*.md")))
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(original.stat().st_mtime_ns, before_stat.st_mtime_ns)
            self.assertEqual(list(source.iterdir()), [original])

            run("bash", str(installation / "uninstall.sh"), "--yes")
            self.assertFalse(installation.exists())
            self.assertFalse(skill.exists())
            self.assertTrue(any((home / ".Trash").iterdir()))
            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(list(source.iterdir()), [original])


if __name__ == "__main__":
    unittest.main()
