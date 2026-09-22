from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from research_store.config import load_config
from research_store.conversations import save_conversation
from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.sync import sync_library


def make_project(path: Path) -> Path:
    path.mkdir()
    (path / ".research-agent-root").write_text(
        PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
    )
    return path.resolve()


def write_config(project: Path, source: Path) -> Path:
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


def conversation_payload() -> dict[str, object]:
    return {
        "title": "동기화 중 저장한 대화",
        "created_at": "2026-09-21T12:00:00+09:00",
        "scope": "current-topic",
        "capture_status": "complete",
        "summary": "PDF 동기화와 별개로 저장한 대화다.",
        "transcript": [
            {"role": "user", "content": "이 대화를 저장해줘."},
            {"role": "assistant", "content": "저장하겠습니다."},
        ],
    }


class SyncConcurrencyTests(unittest.TestCase):
    def test_second_sync_is_rejected_without_blocking_the_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdf = source / "paper.pdf"
            original = b"one-pdf"
            pdf.write_bytes(original)
            config = load_config(write_config(project, source))
            conversion_started = threading.Event()
            release_conversion = threading.Event()

            def paused_converter(_: Path) -> str:
                conversion_started.set()
                if not release_conversion.wait(timeout=10):
                    raise RuntimeError("test did not release conversion")
                return "converted\n"

            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(sync_library, config, paused_converter)
                self.assertTrue(conversion_started.wait(timeout=5))
                second = executor.submit(sync_library, config, lambda _: "duplicate\n")
                try:
                    with self.assertRaisesRegex(RuntimeError, "이미 진행 중"):
                        second.result(timeout=3)
                finally:
                    release_conversion.set()
                self.assertEqual(first.result(timeout=5).converted, 1)

            self.assertEqual(pdf.read_bytes(), original)

    def test_paused_second_conversion_does_not_block_conversation_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            (source / "01-first.pdf").write_bytes(b"first-pdf")
            (source / "02-second.pdf").write_bytes(b"second-pdf")
            config = load_config(write_config(project, source))

            second_conversion_started = threading.Event()
            release_second_conversion = threading.Event()

            def paused_converter(path: Path) -> str:
                content = path.read_bytes()
                if content == b"second-pdf":
                    second_conversion_started.set()
                    if not release_second_conversion.wait(timeout=10):
                        raise RuntimeError("test did not release the second conversion")
                return f"converted: {content.decode('ascii')}\n"

            with ThreadPoolExecutor(max_workers=2) as executor:
                sync_future = executor.submit(sync_library, config, paused_converter)
                try:
                    self.assertTrue(
                        second_conversion_started.wait(timeout=5),
                        "second PDF conversion did not start",
                    )

                    # Reaching the second converter means the first document's
                    # Markdown and ledger row should already be durable.
                    with sqlite3.connect(config.state) as database:
                        document_keys = database.execute(
                            "SELECT document_key FROM documents ORDER BY document_key"
                        ).fetchall()
                    self.assertEqual(document_keys, [("papers:01-first.pdf",)])

                    conversation_future = executor.submit(
                        save_conversation, config, conversation_payload()
                    )
                    saved = conversation_future.result(timeout=3)
                finally:
                    release_second_conversion.set()

                result = sync_future.result(timeout=5)

            self.assertEqual(result.converted, 2)
            self.assertTrue(saved.is_file())
            with sqlite3.connect(config.state) as database:
                conversation_count = database.execute(
                    "SELECT COUNT(*) FROM conversations"
                ).fetchone()[0]
            self.assertEqual(conversation_count, 1)


if __name__ == "__main__":
    unittest.main()
