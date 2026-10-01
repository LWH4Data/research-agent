from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from research_store.cli import (
    CONVERSATION_STDIN_LIMIT,
    STDIN_READY,
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
                fake_stdin.isatty.return_value = False
                fake_stdin.buffer = io.BytesIO(b"x" * (limit + 1))
                with mock.patch("research_store.cli.sys.stdin", fake_stdin):
                    with self.assertRaisesRegex(ValueError, "MiB"):
                        _read_stdin_text(label=label, max_bytes=limit)

    def run_with_pty_held_open(
        self, command: list[str], payload: bytes, *, send_end: bool = True,
        interrupt_after_ready: bool = False,
    ) -> tuple[int, bytes]:
        if os.name != "posix":
            self.skipTest("POSIX terminal support is required")
        import pty
        import termios

        master, slave = pty.openpty()
        original = termios.tcgetattr(slave)
        self.assertTrue(original[3] & termios.ICANON)
        self.assertTrue(original[3] & termios.ECHO)
        process = None
        output = bytearray()
        ready = STDIN_READY.encode("ascii") + b"\r\n"
        deadline = time.monotonic() + 8
        try:
            process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave)
            os.set_blocking(master, False)
            # Do not enqueue any body bytes until the child confirms its setup.
            while ready not in output:
                if time.monotonic() >= deadline or process.poll() is not None:
                    self.fail(f"터미널 입력 준비 신호가 없습니다: {bytes(output)!r}")
                readable, _, _ = select.select([master], [], [], 0.05)
                if readable:
                    output.extend(os.read(master, 65536))
            prepared = termios.tcgetattr(slave)
            self.assertFalse(prepared[3] & termios.ICANON)
            self.assertFalse(prepared[3] & (termios.ECHO | termios.ECHONL))
            self.assertTrue(prepared[3] & termios.ISIG)
            if interrupt_after_ready:
                process.send_signal(signal.SIGINT)

            wire = payload
            if send_end:
                wire += b"\n" + STDIN_SENTINEL.encode("ascii") + b"\n"
            offset = 0
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    self.fail("명령이 열린 터미널에서 종료 표시를 받은 뒤 끝나지 않았습니다")
                readable, writable, _ = select.select(
                    [master], [master] if offset < len(wire) else [], [], 0.05
                )
                if readable:
                    output.extend(os.read(master, 65536))
                if writable:
                    # Splitting inside UTF-8 sequences must not change the body.
                    offset += os.write(master, wire[offset : offset + 257])
            while select.select([master], [], [], 0.05)[0]:
                remaining = os.read(master, 65536)
                if not remaining:
                    break
                output.extend(remaining)

            restored = termios.tcgetattr(slave)
            # Darwin sets the transient PENDIN bit when canonical mode returns.
            pending = getattr(termios, "PENDIN", 0)
            restored[3] &= ~pending
            original[3] &= ~pending
            self.assertEqual(restored, original)
            self.assertEqual(output.count(ready), 1)
            self.assertNotIn(b"\x07", output)
            return process.returncode, bytes(output).split(ready, 1)[1]
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)

    def test_save_conversation_preserves_long_json_line_on_a_pty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config_path = write_config(project, source)
            long_message = "정확한 터미널 대화 원문 " + "가나다라마바사" * 1500
            payload = {
                "title": "터미널 대화 저장",
                "created_at": "2026-10-01T10:00:00+09:00",
                "scope": "current-topic",
                "capture_status": "complete",
                "summary": "긴 한 줄 JSON을 터미널로 저장",
                "transcript": [{"role": "user", "content": long_message}],
            }
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.assertGreater(len(encoded), 12_000)
            self.assertNotIn(b"\n", encoded)
            return_code, output = self.run_with_pty_held_open(
                [sys.executable, "-B", "-m", "research_store.cli", "--config",
                 str(config_path), "save-conversation"],
                encoded,
            )
            self.assertEqual(return_code, 0, output.decode("utf-8"))
            self.assertNotIn(long_message.encode("utf-8"), output)
            saved = Path(json.loads(output)["saved"])
            transcript = saved.read_bytes().split("## 선택 범위 원문\n\n".encode(), 1)[1]
            self.assertEqual(
                transcript, ("### 사용자\n\n> " + long_message + "\n\n").encode("utf-8")
            )

    def test_pty_reader_preserves_carriage_returns_and_flow_control_bytes(self) -> None:
        payload = "터미널 원문".encode("utf-8") + b"\r\n\x11\x13"
        command = (
            "import hashlib; from research_store.cli import _read_stdin_text; "
            "body = _read_stdin_text(label='test', max_bytes=1024); "
            "print(hashlib.sha256(body.encode()).hexdigest())"
        )
        return_code, output = self.run_with_pty_held_open(
            [sys.executable, "-B", "-c", command], payload
        )
        self.assertEqual(return_code, 0, output)
        self.assertEqual(output.strip(), hashlib.sha256(payload + b"\n").hexdigest().encode())

    def test_pty_settings_restore_after_invalid_and_oversize_input(self) -> None:
        for payload, limit, expected in (
            (b"\xff", 1024, "UTF-8"),
            (b"x" * 1025, 1024, "MiB"),
        ):
            with self.subTest(expected=expected):
                command = (
                    "from research_store.cli import _read_stdin_text; "
                    f"_read_stdin_text(label='test', max_bytes={limit})"
                )
                return_code, output = self.run_with_pty_held_open(
                    [sys.executable, "-B", "-c", command], payload
                )
                self.assertNotEqual(return_code, 0)
                self.assertIn(expected.encode("ascii"), output)

    def test_pty_settings_restore_after_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config_path = write_config(project, source)
            return_code, output = self.run_with_pty_held_open(
                [sys.executable, "-B", "-m", "research_store.cli", "--config",
                 str(config_path), "save-conversation"],
                b"{invalid-json}",
            )
            self.assertEqual(return_code, 1)
            self.assertIn("대화 JSON을 읽을 수 없습니다".encode("utf-8"), output)
            self.assertFalse((project / "knowledge/conversations").exists())

    def test_pty_sigint_interrupts_and_restores_settings(self) -> None:
        command = (
            "from research_store.cli import _read_stdin_text; "
            "_read_stdin_text(label='test', max_bytes=1024)"
        )
        return_code, output = self.run_with_pty_held_open(
            [sys.executable, "-B", "-c", command], b"", send_end=False,
            interrupt_after_ready=True,
        )
        self.assertNotEqual(return_code, 0)
        self.assertIn(b"KeyboardInterrupt", output)

    def test_unsupported_tty_fails_before_reading_or_emitting_ready(self) -> None:
        fake_stdin = mock.Mock()
        fake_stdin.isatty.return_value = True
        fake_stdin.buffer = io.BytesIO(b"body\n")
        stderr = io.StringIO()
        with (
            mock.patch("research_store.cli.sys.stdin", fake_stdin),
            mock.patch("research_store.cli.sys.stderr", stderr),
            mock.patch.dict(sys.modules, {"termios": None}),
        ):
            with self.assertRaisesRegex(ValueError, "안전한 표준 입력"):
                _read_stdin_text(label="test", max_bytes=1024)
        self.assertEqual(fake_stdin.buffer.tell(), 0)
        self.assertEqual(stderr.getvalue(), "")

    @unittest.skipUnless(os.name == "posix", "POSIX terminal support is required")
    def test_failed_tty_setup_restores_before_reading_or_emitting_ready(self) -> None:
        import pty
        import termios

        master, slave = pty.openpty()
        fake_stdin = mock.Mock()
        fake_stdin.isatty.return_value = True
        fake_stdin.fileno.return_value = slave
        fake_stdin.buffer = io.BytesIO(b"body\n")
        stderr = io.StringIO()
        try:
            with (
                mock.patch("research_store.cli.sys.stdin", fake_stdin),
                mock.patch("research_store.cli.sys.stderr", stderr),
                mock.patch("termios.tcsetattr", side_effect=[termios.error("denied"), None])
                as setter,
            ):
                with self.assertRaisesRegex(ValueError, "안전하게 준비"):
                    _read_stdin_text(label="test", max_bytes=1024)
            self.assertEqual(setter.call_count, 2)
            self.assertEqual(fake_stdin.buffer.tell(), 0)
            self.assertEqual(stderr.getvalue(), "")
        finally:
            os.close(master)
            os.close(slave)

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
            self.assertNotIn(STDIN_READY, stderr)
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
