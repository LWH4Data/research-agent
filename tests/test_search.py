from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from research_store.config import load_config
from research_store.conversations import save_conversation
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


if __name__ == "__main__":
    unittest.main()
