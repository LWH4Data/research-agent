from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from research_store.cli import (
    CONVERSATION_STDIN_LIMIT,
    STDIN_SENTINEL,
    VISUAL_NOTES_STDIN_LIMIT,
    _read_stdin_text,
)
from research_store.config import load_config
from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.sync import ConversionResult, sync_library


def make_project(path: Path) -> Path:
    path.mkdir()
    (path / ".research-agent-root").write_text(
        PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
    )
    return path.resolve()


def write_config(project: Path, source: Path) -> Path:
    config_path = project / "config.toml"
    config_path.write_text(
        f"""
[store]
documents = "knowledge/documents"
conversations = "knowledge/conversations"
assets = "knowledge/assets"
state = ".research-store/library.sqlite"
temporary = ".research-store/tmp"

[[sources]]
id = "documents"
path = {json.dumps(str(source))}
kind = "directory"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


class StdinProtocolTests(unittest.TestCase):
    def test_stdin_reader_enforces_each_command_byte_limit(self) -> None:
        limits = (
            ("대화 JSON", CONVERSATION_STDIN_LIMIT),
            ("시각 검토 노트", VISUAL_NOTES_STDIN_LIMIT),
        )
        for label, limit in limits:
            with self.subTest(label=label):
                fake_stdin = mock.Mock()
                fake_stdin.buffer = io.BytesIO(b"x" * (limit + 1))
                with mock.patch("research_store.cli.sys.stdin", fake_stdin):
                    with self.assertRaisesRegex(ValueError, "MiB"):
                        _read_stdin_text(label=label, max_bytes=limit)

    def run_with_pipe_held_open(
        self, arguments: list[str], payload: bytes, *, chunk_size: int
    ) -> tuple[str, str]:
        process = subprocess.Popen(
            [sys.executable, "-m", "research_store.cli", *arguments],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertIsNotNone(process.stdin)
        self.assertIsNotNone(process.stdout)
        self.assertIsNotNone(process.stderr)
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None

        try:
            for offset in range(0, len(payload), chunk_size):
                process.stdin.write(payload[offset : offset + chunk_size])
                process.stdin.flush()
            process.stdin.write(b"\n" + STDIN_SENTINEL.encode("ascii") + b"\n")
            process.stdin.flush()

            self.assertFalse(process.stdin.closed)
            try:
                return_code = process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                self.fail("명령이 종료 표시를 받은 뒤 EOF 없이 끝나지 않았습니다")

            self.assertFalse(process.stdin.closed)
            stdout = process.stdout.read().decode("utf-8")
            stderr = process.stderr.read().decode("utf-8")
            self.assertEqual(return_code, 0, stderr)
            return stdout, stderr
        finally:
            if not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()

    def test_save_conversation_exits_on_sentinel_before_eof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config_path = write_config(project, source)
            long_message = "청크로 보낸 긴 대화 내용 " + "가나다라마바사" * 1_500
            payload = {
                "title": "열린 파이프 대화 저장",
                "created_at": "2026-09-17T10:00:00+09:00",
                "scope": "current-topic",
                "capture_status": "complete",
                "summary": "종료 표시를 사용한 긴 대화 저장 확인",
                "transcript": [{"role": "user", "content": long_message}],
            }
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.assertGreater(len(encoded), 10_000)

            stdout, _ = self.run_with_pipe_held_open(
                ["--config", str(config_path), "save-conversation"],
                encoded,
                chunk_size=257,
            )

            response = json.loads(stdout)
            saved = Path(response["saved"])
            self.assertTrue(saved.is_file())
            self.assertIn(long_message, saved.read_text(encoding="utf-8"))

    def test_review_complete_exits_on_sentinel_and_marks_visual_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdf = source / "document.pdf"
            pdf.write_bytes(b"pdf")
            config_path = write_config(project, source)
            config = load_config(config_path)
            sync_library(
                config,
                lambda _: ConversionResult(
                    "<!-- page: 1 -->\n\nbase extraction\n",
                    {1: ["table-caption"]},
                ),
            )
            digest = hashlib.sha256(b"pdf").hexdigest()
            visual_notes = (
                "표의 행과 열을 원본 이미지에서 확인했습니다. "
                + "검증된 셀 내용 " * 900
                + f"\n접두사가 있는 {STDIN_SENTINEL} 문자열도 노트입니다."
            )
            encoded = visual_notes.encode("utf-8")
            self.assertGreater(len(encoded), 10_000)

            self.run_with_pipe_held_open(
                [
                    "--config",
                    str(config_path),
                    "review-complete",
                    "documents:document.pdf",
                    "--page",
                    "1",
                    "--sha256",
                    digest,
                    "--status",
                    "verified",
                    "--visual-notes-stdin",
                ],
                encoded,
                chunk_size=193,
            )

            markdown_files = list((project / "knowledge/documents").rglob("*.md"))
            self.assertEqual(len(markdown_files), 1)
            saved = markdown_files[0].read_text(encoding="utf-8")
            self.assertIn("### Pages 1", saved)
            self.assertIn("<!-- visual-review-pages: 1 -->", saved)
            self.assertIn(f"접두사가 있는 {STDIN_SENTINEL} 문자열", saved)


if __name__ == "__main__":
    unittest.main()
