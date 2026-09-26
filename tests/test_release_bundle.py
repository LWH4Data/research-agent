from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1]
ARCHIVE = os.environ.get("RESEARCH_AGENT_RELEASE_ARCHIVE")


class RuntimeManifestTests(unittest.TestCase):
    def test_product_settings_and_instruction_dependencies_are_shipped(self) -> None:
        entries = {}
        for line in (PROJECT / "packaging/runtime-files.txt").read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split()
            self.assertIn(len(fields), (1, 2), line)
            self.assertNotIn(fields[-1], entries, line)
            entries[fields[-1]] = fields[0]
            self.assertTrue((PROJECT / fields[0]).is_file(), line)
        self.assertEqual(entries["AGENTS.md"], "resources/AGENTS.runtime.md")
        self.assertEqual(entries[".codex/config.toml"], "resources/codex.runtime.toml")
        self.assertNotIn("AGENTS.md", entries.values())
        self.assertNotIn(".codex/config.toml", entries.values())
        self.assertNotIn("scripts/check_guides.py", entries)
        runtime = tomllib.loads((PROJECT / entries[".codex/config.toml"]).read_text())
        self.assertEqual(runtime["sandbox_mode"], "workspace-write")
        self.assertEqual(runtime["approval_policy"], "never")
        limits = runtime["sandbox_workspace_write"]
        self.assertEqual(limits["writable_roots"], [])
        self.assertFalse(limits["network_access"])
        self.assertTrue(limits["exclude_slash_tmp"])
        self.assertTrue(limits["exclude_tmpdir_env_var"])
        # A task-specific reference must survive packaging as well as exist in
        # the development checkout, including references linked by references.
        skill = PROJECT / "resources/skills/research-library"
        pending = [skill / "SKILL.md"]
        visited = set()
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            relative = path.relative_to(PROJECT).as_posix()
            self.assertEqual(entries.get(relative), relative, relative)
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                linked = (path.parent / target.split("#", 1)[0]).resolve()
                if linked.suffix == ".md" and linked.is_relative_to(skill):
                    self.assertTrue(linked.is_file(), target)
                    pending.append(linked)


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
            self.assertEqual(
                archive.extractfile("research-agent/.codex/config.toml").read(),
                (PROJECT / "resources/codex.runtime.toml").read_bytes(),
            )
            self.assertNotEqual(
                archive.extractfile("research-agent/.codex/config.toml").read(),
                (PROJECT / ".codex/config.toml").read_bytes(),
            )
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
