from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research_store.config import load_config
from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.state import LibraryState
from research_store.sync import (
    ConversionResult,
    pending_reviews,
    sync_library,
)


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


def child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    source_root = str(Path(__file__).resolve().parents[1] / "src")
    current = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_root if not current else source_root + os.pathsep + current
    )
    return environment


def interrupt_sync_after_markdown_replace(config_path: Path) -> subprocess.CompletedProcess[str]:
    script = r'''
import os
from pathlib import Path
import sys
import research_store.operations as operations
from research_store.config import load_config
from research_store.sync import sync_library

real_atomic_text = operations.atomic_text
def replace_then_stop(path, text, root):
    real_atomic_text(path, text, root)
    os._exit(79)
operations.atomic_text = replace_then_stop
sync_library(
    load_config(Path(sys.argv[1])),
    lambda _: "<!-- page: 1 -->\n\nRecovered conversion marker\n",
)
'''
    return subprocess.run(
        [sys.executable, "-c", script, str(config_path)],
        env=child_environment(),
        capture_output=True,
        text=True,
        check=False,
    )


class DocumentRecoveryTests(unittest.TestCase):
    def test_next_sync_removes_pdf_copy_left_by_abrupt_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            original = b"private read-only source copy"
            pdf = source / "paper.pdf"
            pdf.write_bytes(original)
            config_path = write_config(project, source)
            script = r'''
import os
from pathlib import Path
import sys
from research_store.config import load_config
from research_store.sync import sync_library

def stop_with_copy(copied):
    if not copied.is_file():
        raise RuntimeError("temporary copy missing")
    os._exit(77)

sync_library(load_config(Path(sys.argv[1])), stop_with_copy)
'''
            stopped = subprocess.run(
                [sys.executable, "-c", script, str(config_path)],
                env=child_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(stopped.returncode, 77, stopped.stderr)
            temporary = project / ".research-store/tmp"
            stale = list(temporary.glob("pdf-*"))
            self.assertEqual(len(stale), 1)

            config = load_config(config_path)
            result = sync_library(config, lambda _: "recovered conversion\n")

            self.assertEqual(result.converted, 1)
            self.assertEqual(list(temporary.glob("pdf-*")), [])
            self.assertEqual(pdf.read_bytes(), original)

    def test_uncertain_markdown_write_keeps_recovery_journal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            original = b"read-only source for uncertain write"
            pdf = source / "paper.pdf"
            pdf.write_bytes(original)
            config = load_config(write_config(project, source))

            def corrupt_then_fail(path: Path, text: str, root: Path) -> None:
                del text, root
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("unexpected partial content\n", encoding="utf-8")
                raise OSError("forced uncertain write")

            with patch(
                "research_store.operations.atomic_text",
                side_effect=corrupt_then_fail,
            ), self.assertRaisesRegex(RuntimeError, "안전하게 복구하지 못했습니다"):
                sync_library(config, lambda _: "converted content\n")

            self.assertEqual(pdf.read_bytes(), original)
            with sqlite3.connect(config.state) as db:
                row = db.execute(
                    "SELECT output_path FROM document_operations"
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 0
                )
            assert row is not None
            self.assertEqual(
                (project / row[0]).read_text(encoding="utf-8"),
                "unexpected partial content\n",
            )

    def test_interrupted_sync_rolls_forward_and_skips_durable_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            original = b"read-only original pdf bytes"
            pdf = source / "paper.pdf"
            pdf.write_bytes(original)
            config_path = write_config(project, source)
            script = r'''
import os
from pathlib import Path
import sys
import research_store.operations as operations
from research_store.config import load_config
from research_store.sync import sync_library

real_atomic_text = operations.atomic_text
def replace_then_stop(path, text, root):
    real_atomic_text(path, text, root)
    os._exit(79)
operations.atomic_text = replace_then_stop
sync_library(
    load_config(Path(sys.argv[1])),
    lambda _: "<!-- page: 1 -->\n\nRecovered conversion marker\n",
)
'''
            stopped = subprocess.run(
                [sys.executable, "-c", script, str(config_path)],
                env=child_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(stopped.returncode, 79, stopped.stderr)
            self.assertEqual(pdf.read_bytes(), original)
            with sqlite3.connect(project / ".research-store/library.sqlite") as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM document_operations").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 0
                )

            events = []

            def must_not_convert(_: Path) -> str:
                self.fail("a recovered unchanged document was converted again")

            config = load_config(config_path)
            result = sync_library(config, must_not_convert, progress=events.append)

            self.assertEqual(result.unchanged, 1)
            self.assertEqual(result.converted, 0)
            self.assertEqual(pdf.read_bytes(), original)
            self.assertTrue(
                any(event.phase == "recovery" for event in events),
                events,
            )
            with LibraryState(config.state, config.root, read_only=True) as state:
                document = state.get_document("papers:paper.pdf")
                runs = state.connection.execute(
                    "SELECT status, current, total FROM library_runs ORDER BY rowid"
                ).fetchall()
                pending_operation = state.get_pending_document_operation()
            self.assertIsNotNone(document)
            assert document is not None
            output = config.root / str(document["output_path"])
            self.assertIn("Recovered conversion marker", output.read_text())
            self.assertIsNone(pending_operation)
            self.assertEqual(
                [(row["status"], row["current"], row["total"]) for row in runs],
                [("interrupted", 0, 1), ("completed", 1, 1)],
            )

    def test_recovery_refuses_unexpected_markdown_and_keeps_journal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            original = b"read-only original"
            pdf = source / "paper.pdf"
            pdf.write_bytes(original)
            config_path = write_config(project, source)
            stopped = interrupt_sync_after_markdown_replace(config_path)
            self.assertEqual(stopped.returncode, 79, stopped.stderr)

            with sqlite3.connect(project / ".research-store/library.sqlite") as db:
                relative_output = db.execute(
                    "SELECT output_path FROM document_operations"
                ).fetchone()[0]
            output = project / relative_output
            output.write_text("unexpected external content\n", encoding="utf-8")

            config = load_config(config_path)
            with self.assertRaisesRegex(RuntimeError, "Markdown 내용이 예상과"):
                sync_library(config, lambda _: "must not run")

            self.assertEqual(output.read_text(encoding="utf-8"), "unexpected external content\n")
            self.assertEqual(pdf.read_bytes(), original)
            with sqlite3.connect(config.state) as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM document_operations").fetchone()[0],
                    1,
                )

    def test_recovery_refuses_unexpected_database_state_and_keeps_journal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            original = b"another read-only original"
            pdf = source / "paper.pdf"
            pdf.write_bytes(original)
            config_path = write_config(project, source)
            stopped = interrupt_sync_after_markdown_replace(config_path)
            self.assertEqual(stopped.returncode, 79, stopped.stderr)
            config = load_config(config_path)

            with LibraryState(config.state, config.root) as state:
                operation = state.get_pending_document_operation()
                self.assertIsNotNone(operation)
                assert operation is not None
                unexpected = dict(operation["target_document"])
                unexpected["parser_version"] = "unexpected-external-state"
                state.upsert_document(unexpected)

            with self.assertRaisesRegex(RuntimeError, "SQLite 상태가 예상과"):
                sync_library(config, lambda _: "must not run")

            self.assertEqual(pdf.read_bytes(), original)
            with sqlite3.connect(config.state) as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM document_operations").fetchone()[0],
                    1,
                )

    def test_interrupted_visual_review_rolls_forward_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            original = b"another read-only original pdf"
            pdf = source / "paper.pdf"
            pdf.write_bytes(original)
            config_path = write_config(project, source)
            config = load_config(config_path)
            sync_library(
                config,
                lambda _: ConversionResult(
                    "<!-- page: 1 -->\n\nTable 1\n",
                    {1: ["table-caption"]},
                ),
            )
            with LibraryState(config.state, config.root, read_only=True) as state:
                document = state.get_document("papers:paper.pdf")
            self.assertIsNotNone(document)
            assert document is not None
            digest = str(document["sha256"])
            output = config.root / str(document["output_path"])
            script = r'''
import os
from pathlib import Path
import sys
import research_store.operations as operations
from research_store.config import load_config
from research_store.sync import complete_reviews

real_atomic_text = operations.atomic_text
def replace_then_stop(path, text, root):
    real_atomic_text(path, text, root)
    os._exit(83)
operations.atomic_text = replace_then_stop
complete_reviews(
    load_config(Path(sys.argv[1])),
    "papers:paper.pdf",
    [1],
    expected_sha256=sys.argv[2],
    status="verified",
    reviewer_model="gpt-5.6-sol",
    notes="database note",
    visual_notes="Recovered visual note",
)
'''
            stopped = subprocess.run(
                [sys.executable, "-c", script, str(config_path), digest],
                env=child_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(stopped.returncode, 83, stopped.stderr)
            self.assertEqual(pdf.read_bytes(), original)
            with sqlite3.connect(config.state) as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM document_operations").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM page_reviews WHERE document_key = ?",
                        ("papers:paper.pdf",),
                    ).fetchone()[0],
                    "pending",
                )

            self.assertEqual(pending_reviews(config), [])
            self.assertEqual(pdf.read_bytes(), original)
            content = output.read_text(encoding="utf-8")
            self.assertEqual(content.count("<!-- visual-review-begin: 1 -->"), 1)
            self.assertIn("Recovered visual note", content)
            with LibraryState(config.state, config.root, read_only=True) as state:
                self.assertIsNone(state.get_pending_document_operation())
                review = state.document_reviews("papers:paper.pdf")[0]
            self.assertEqual(review["status"], "verified")


if __name__ == "__main__":
    unittest.main()
