from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_store.config import load_config
from research_store.conversations import save_conversation
from research_store.search import search_library
from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.sync import sync_library


def make_config(project: Path, source: Path) -> Path:
    project.mkdir()
    project = project.resolve()
    (project / ".research-agent-root").write_text(
        PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
    )
    (project / ".gitignore").write_text("knowledge/**\n", encoding="utf-8")
    config_path = project / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[store]",
                'documents = "knowledge/documents"',
                'conversations = "knowledge/conversations"',
                'assets = "knowledge/assets"',
                'state = ".research-store/library.sqlite"',
                'temporary = ".research-store/tmp"',
                "",
                "[[sources]]",
                'id = "papers"',
                f"path = {json.dumps(str(source))}",
                'kind = "directory"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


class SearchTests(unittest.TestCase):
    def test_cli_searches_gitignored_documents_and_conversations_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "paper.pdf").write_bytes(b"pdf")
            project = root / "agent"
            config_path = make_config(project, source)
            config = load_config(config_path)
            sync_library(
                config,
                lambda _: (
                    "<!-- page: 1 -->\n\n"
                    "Transformer cavity evidence.\n"
                    "Transformer attention evidence.\n"
                    "Transformer encoder evidence.\n"
                ),
            )
            save_conversation(
                config,
                {
                    "title": "굴절률 보정 대화",
                    "created_at": "2026-09-17T10:00:00+09:00",
                    "scope": "current-topic",
                    "capture_status": "complete",
                    "summary": "굴절률 보정 방법을 저장했다.",
                    "transcript": [
                        {"role": "user", "content": "굴절률 보정을 기억해줘."}
                    ],
                },
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_store.cli",
                    "--config",
                    str(config_path),
                    "search",
                    "--limit",
                    "2",
                    "transformer",
                    "굴절률",
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["truncated"])
            self.assertEqual(
                {match["type"] for match in payload["matches"]},
                {"pdf-document", "conversation"},
            )
            self.assertTrue(
                all(match["path"].startswith("knowledge/") for match in payload["matches"])
            )


class SearchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / "originals"
        self.source.mkdir()
        self.project = self.base / "store"
        self.config_path = make_config(self.project, self.source)
        self.config = load_config(self.config_path)

    def pdfs(self, bodies):
        for name, body in bodies.items():
            (self.source / name).write_text(body)
        sync_library(self.config, lambda copied: copied.read_text())

    def memory(self, text="laser user decision"):
        return save_conversation(self.config, {
            "title": "실험 기록", "summary": text,
            "created_at": "2026-09-22T00:00:00+00:00", "scope": "current-topic",
            "capture_status": "complete",
            "transcript": [{"role": "user", "content": "선택한 연구 기록"}],
        })

    def test_default_limit_does_not_starve_conversation_or_second_pdf(self):
        self.pdfs({
            "a.pdf": "<!-- page: 1 -->\n" + "\n\n".join(f"laser evidence {i}" for i in range(120)),
            "b.pdf": "<!-- page: 3 -->\nlaser alternative",
        })
        self.memory()
        originals = {p: p.read_bytes() for p in self.source.iterdir()}
        result = search_library(self.config, ["laser"])
        self.assertEqual(len(result["matches"]), 50)
        self.assertEqual(len({hit["path"] for hit in result["matches"][:3]}), 3)
        self.assertIn("conversation", {hit["type"] for hit in result["matches"]})
        self.assertEqual(originals, {p: p.read_bytes() for p in self.source.iterdir()})

    def test_scopes_and_citation_metadata(self):
        self.pdfs({"paper.pdf": "<!-- page: 4 -->\nlaser actual evidence"})
        self.memory()
        for scope, kind in (("pdf", "pdf-document"), ("conversation", "conversation")):
            result = search_library(self.config, ["laser"], scope=scope)
            self.assertTrue(result["matches"])
            self.assertEqual({hit["type"] for hit in result["matches"]}, {kind})
        hit = search_library(self.config, ["laser"], scope="pdf")["matches"][0]
        self.assertEqual(hit["pages"], [4])
        self.assertEqual(hit["document_id"], "papers:paper.pdf")
        self.assertEqual(hit["source_path"], "paper.pdf")

    def test_pagination_is_complete_stable_and_has_no_duplicate_positions(self):
        self.pdfs({"a.pdf": "\n\n".join(f"laser item {i}" for i in range(32)),
                   "b.pdf": "\n\n".join(f"laser other {i}" for i in range(7))})
        self.memory()
        whole = search_library(self.config, ["laser"], limit=100)
        accumulated = []
        page = search_library(self.config, ["laser"], limit=3)
        while True:
            accumulated.extend(page["matches"])
            if not page["has_more"]:
                break
            page = search_library(self.config, ["laser"], limit=3,
                                  offset=page["next_offset"], snapshot=page["snapshot"])
        self.assertEqual(accumulated, whole["matches"])
        self.assertEqual(len(accumulated), len({(r["path"], r["line"]) for r in accumulated}))
        self.assertIsNone(page["next_offset"])

    def test_changed_corpus_and_query_reject_continuation(self):
        self.pdfs({"a.pdf": "laser first\n\nlaser second"})
        first = search_library(self.config, ["laser"], limit=1)
        with self.assertRaisesRegex(ValueError, "변경"):
            search_library(self.config, ["first"], offset=1, snapshot=first["snapshot"])
        self.memory()
        with self.assertRaisesRegex(ValueError, "변경"):
            search_library(self.config, ["laser"], offset=1, snapshot=first["snapshot"])

    def test_snapshot_detects_same_length_changes_even_with_restored_mtime(self):
        import os
        self.pdfs({"a.pdf": "laser first\n\nlaser other"})
        first = search_library(self.config, ["laser"], limit=1)
        path = next(self.config.documents.rglob("*.md"))
        info = path.stat()
        path.write_text(path.read_text().replace("first", "newer"))
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "변경"):
            search_library(self.config, ["laser"], offset=1, snapshot=first["snapshot"])

    def test_changes_after_an_earlier_file_was_scanned_are_detected(self):
        import research_store.search as module
        self.pdfs({"a.pdf": "laser first", "b.pdf": "laser second"})
        original = module._scan_document
        seen = []

        def scan(path, *args):
            result = original(path, *args)
            if seen:
                seen[0].write_text(seen[0].read_text() + "\nexternal edit")
            seen.append(path)
            return result

        with patch.object(module, "_scan_document", side_effect=scan):
            with self.assertRaisesRegex(ValueError, "검색 중"):
                search_library(self.config, ["laser"])

    def test_invalid_options_and_empty_results(self):
        self.pdfs({"a.pdf": "nothing related"})
        for options in ({"limit": 0}, {"scope": "unknown"}, {"offset": -1},
                        {"offset": 1}, {"snapshot": "invalid"}, {"offset": 10000}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                search_library(self.config, ["laser"], **options)
        result = search_library(self.config, ["unfindable"])
        self.assertEqual(result["matches"], [])
        self.assertFalse(result["has_more"])

    def test_symlink_skipped_and_hardlink_rejected(self):
        import os
        self.pdfs({"a.pdf": "laser"})
        outside = self.base / "private.md"
        outside.write_text("laser confidential")
        link = self.config.documents / "link.md"
        link.symlink_to(outside)
        self.assertFalse(any("confidential" in hit["text"] for hit in search_library(self.config, ["laser"])["matches"]))
        link.unlink()
        os.link(outside, link)
        with self.assertRaises(ValueError):
            search_library(self.config, ["laser"])

    def test_cli_accepts_scope_and_continuation_parameters(self):
        self.pdfs({"a.pdf": "laser first\n\nlaser second"})
        command = [sys.executable, "-m", "research_store.cli", "--config", str(self.config_path),
                   "search", "laser", "--scope", "pdf", "--limit", "1"]
        first = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(first.stdout)
        following = subprocess.run(command + ["--offset", str(payload["next_offset"]),
                                              "--snapshot", payload["snapshot"]],
                                   capture_output=True, text=True, check=True)
        next_payload = json.loads(following.stdout)
        self.assertNotEqual(payload["matches"][0]["line"], next_payload["matches"][0]["line"])


if __name__ == "__main__":
    unittest.main()
