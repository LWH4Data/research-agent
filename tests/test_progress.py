from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_store.cli import main
from research_store.config import load_config
from research_store.progress import (
    PROGRESS_PREFIX,
    JsonlProgressRenderer,
    ProgressEvent,
    progress_renderer,
    sanitize_progress_text,
)
from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.state import LibraryState
from research_store.sync import sync_library

from test_sync import write_text_pdf


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


class ProgressTests(unittest.TestCase):
    def test_agent_preview_uses_jsonl_stderr_and_one_final_stdout_value(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/demo_progress.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--jsonl", "--delay", "0"],
            capture_output=True,
            text=True,
            check=True,
        )

        final = json.loads(completed.stdout)
        self.assertEqual(final["preview"], "completed")
        self.assertFalse(final["store_modified"])
        events = [
            json.loads(line.removeprefix(PROGRESS_PREFIX))
            for line in completed.stderr.splitlines()
            if line.startswith(PROGRESS_PREFIX)
        ]
        self.assertEqual(
            list(dict.fromkeys(event["phase"] for event in events)),
            ["discover", "documents", "review"],
        )
        self.assertEqual(events[-1]["status"], "completed")

    def test_jsonl_progress_keeps_stdout_as_one_final_json_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            write_text_pdf(source / "paper.pdf", "A short research paper")
            config_path = write_config(project, source)
            stdout = io.StringIO()
            stderr = io.StringIO()

            with patch.object(
                sys,
                "argv",
                [
                    "research-store",
                    "--config",
                    str(config_path),
                    "sync",
                    "--progress",
                    "jsonl",
                ],
            ), redirect_stdout(stdout), redirect_stderr(stderr):
                main()

            final = json.loads(stdout.getvalue())
            self.assertEqual(final["discovered"], 1)
            self.assertEqual(final["converted"], 1)
            lines = [line for line in stderr.getvalue().splitlines() if line]
            self.assertTrue(lines)
            self.assertTrue(all(line.startswith(PROGRESS_PREFIX) for line in lines))
            events = [
                json.loads(line.removeprefix(PROGRESS_PREFIX)) for line in lines
            ]
            self.assertEqual(events[0]["type"], "research_progress")
            self.assertEqual(events[0]["schema_version"], 1)
            self.assertEqual(events[0]["operation"], "sync")
            self.assertEqual(events[-1]["status"], "completed")
            self.assertEqual(events[-1]["current"], 1)
            self.assertEqual(events[-1]["total"], 1)

            with LibraryState(
                project / ".research-store/library.sqlite",
                project,
                read_only=True,
            ) as state:
                run = state.latest_library_run()
            self.assertIsNotNone(run)
            assert run is not None
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["current"], 1)
            self.assertEqual(run["total"], 1)

    def test_non_tty_auto_mode_is_silent(self) -> None:
        self.assertIsNone(progress_renderer("auto", stream=io.StringIO()))

    def test_jsonl_renderer_emits_ten_percent_milestones_not_every_item(self) -> None:
        stream = io.StringIO()
        renderer = JsonlProgressRenderer(stream)
        for current in range(0, 101):
            renderer(
                ProgressEvent(
                    run_id="run-1",
                    phase="documents",
                    status="progress",
                    current=current,
                    total=100,
                    counters={"converted": current},
                )
            )
        payloads = [
            json.loads(line.removeprefix(PROGRESS_PREFIX))
            for line in stream.getvalue().splitlines()
        ]
        self.assertLessEqual(len(payloads), 11)
        self.assertEqual(payloads[0]["current"], 0)
        self.assertEqual(payloads[-1]["current"], 100)
        self.assertEqual(
            [payload["current"] for payload in payloads],
            list(range(0, 101, 10)),
        )

    def test_display_text_removes_control_characters_and_limits_length(self) -> None:
        cleaned = sanitize_progress_text("paper\x1b[31m\nname.pdf" + "x" * 300)
        self.assertIsNotNone(cleaned)
        assert cleaned is not None
        self.assertNotIn("\x1b", cleaned)
        self.assertNotIn("\n", cleaned)
        self.assertLessEqual(len(cleaned), 160)

    def test_document_progress_is_emitted_only_after_durable_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            (source / "paper.pdf").write_bytes(b"source remains read only")
            config = load_config(write_config(project, source))
            observed: list[tuple[int, int, int]] = []

            def observe(event: ProgressEvent) -> None:
                if event.phase != "documents" or event.status != "progress":
                    return
                with sqlite3.connect(config.state) as database:
                    document_count = database.execute(
                        "SELECT COUNT(*) FROM documents"
                    ).fetchone()[0]
                    run_current = database.execute(
                        "SELECT current FROM library_runs WHERE run_id = ?",
                        (event.run_id,),
                    ).fetchone()[0]
                observed.append((event.current, document_count, run_current))

            sync_library(config, lambda _: "converted\n", progress=observe)

            self.assertEqual(observed, [(1, 1, 1)])

    def test_fatal_failure_is_not_reported_as_user_interruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            config = load_config(write_config(project, source))
            events: list[ProgressEvent] = []

            with patch.object(
                LibraryState,
                "mark_missing_except",
                side_effect=RuntimeError("forced finalization failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "forced finalization"):
                    sync_library(config, lambda _: "unused", progress=events.append)

            self.assertEqual(events[-1].status, "failed")
            with LibraryState(config.state, config.root, read_only=True) as state:
                run = state.latest_library_run()
            self.assertIsNotNone(run)
            assert run is not None
            self.assertEqual(run["status"], "failed")


if __name__ == "__main__":
    unittest.main()
