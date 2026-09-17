from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from research_store.config import load_config
from research_store.conversations import save_conversation
from research_store.picker import choose_source, macos_picker_script
from research_store.safety import PROJECT_MARKER_CONTENT, atomic_text
from research_store.sources import (
    add_sources,
    initialize_config,
    remove_sources,
    source_rows,
)
from research_store.state import LibraryState
from research_store.sync import (
    ConversionResult,
    PARSER_VERSION,
    _collision_migration_plan,
    _output_path,
    complete_reviews,
    pending_reviews,
    pdf_converter,
    render_review_pages,
    sync_library,
)


def write_text_pdf(path: Path, text: str) -> None:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode("ascii"))
        content.extend(body)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(content)


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


def tree_snapshot(root: Path) -> dict[str, tuple[object, ...]]:
    snapshot: dict[str, tuple[object, ...]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        common = (
            stat.S_IMODE(info.st_mode),
            info.st_uid,
            info.st_gid,
            info.st_size,
            info.st_mtime_ns,
        )
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path), *common)
        elif path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[relative] = ("file", digest, *common)
        else:
            snapshot[relative] = ("directory", *common)
    return snapshot


def document_output(config, document_key: str) -> Path:
    with LibraryState(config.state, config.root) as state:
        document = state.get_document(document_key)
    if document is None:
        raise AssertionError(f"missing document record: {document_key}")
    return config.root / str(document["output_path"])


class SyncLibraryTests(unittest.TestCase):
    def test_macos_picker_success_cancel_and_failure_are_clean(self) -> None:
        with mock.patch("research_store.picker.sys.platform", "darwin"):
            with mock.patch(
                "research_store.picker.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, "/tmp/Papers\n", ""),
            ):
                self.assertEqual(choose_source(), Path("/tmp/Papers"))
            with mock.patch(
                "research_store.picker.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, "\n", ""),
            ):
                self.assertIsNone(choose_source())
            with mock.patch(
                "research_store.picker.subprocess.run",
                side_effect=subprocess.CalledProcessError(
                    1, ["osascript"], stderr="picker failed"
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "picker failed"):
                    choose_source()

    @unittest.skipUnless(sys.platform == "darwin", "macOS-only picker compiler")
    def test_macos_picker_script_compiles_without_opening_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Picker.scpt"
            result = subprocess.run(
                [
                    "osacompile",
                    "-l",
                    "JavaScript",
                    "-e",
                    macos_picker_script(),
                    "-o",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_pypdf_converts_text_and_flags_table_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "document.pdf"
            write_text_pdf(pdf, "Table 1 Hello Research")

            converted = pdf_converter(pdf)

            self.assertIn("Hello Research", converted.markdown)
            self.assertIn("<!-- page: 1 -->", converted.markdown)
            self.assertIn("table-caption", converted.review_pages[1])

    def test_textless_page_is_queued_for_visual_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "scan.pdf"
            write_text_pdf(pdf, "")

            converted = pdf_converter(pdf)

            self.assertIn("text-extraction: empty", converted.markdown)
            self.assertIn("low-extracted-text", converted.review_pages[1])

    def test_sync_is_incremental_and_source_tree_is_byte_for_byte_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdf = source / "nested" / "document.PDF"
            pdf.parent.mkdir()
            pdf.write_bytes(b"unchanged source bytes")
            (source / "notes.txt").write_text("keep me", encoding="utf-8")
            config = load_config(write_config(project, source))
            before = tree_snapshot(source)
            seen_paths: list[Path] = []

            def fake_converter(path: Path) -> str:
                seen_paths.append(path)
                self.assertFalse(path.is_relative_to(source))
                return "# Parsed document\n\nUseful content.\n"

            first = sync_library(config, fake_converter)
            second = sync_library(config, fake_converter)
            self.assertEqual(tree_snapshot(source), before)
            pdf.write_bytes(b"changed source content with more bytes")
            changed = tree_snapshot(source)
            third = sync_library(config, fake_converter)
            fourth = sync_library(config, fake_converter)

            self.assertEqual(first.converted, 1)
            self.assertEqual(second.unchanged, 1)
            self.assertEqual(third.converted, 1)
            self.assertEqual(fourth.unchanged, 1)
            self.assertEqual(len(seen_paths), 2)
            self.assertEqual(tree_snapshot(source), changed)
            output = document_output(config, "documents:nested/document.PDF")
            self.assertIn('type: "pdf-document"', output.read_text())
            self.assertIn('source_path: "nested/document.PDF"', output.read_text())

    def test_document_storage_key_distinguishes_case_and_unicode_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source"
            project = make_project(root / "agent")
            source_path.mkdir()
            config = load_config(write_config(project, source_path))
            source = config.sources[0]

            relatives = [
                Path("paper.pdf"),
                Path("paper.PDF"),
                Path("Folder/paper.pdf"),
                Path("folder/paper.pdf"),
                Path("café.pdf"),
                Path("cafe\u0301.pdf"),
            ]
            outputs = [_output_path(config, source, item) for item in relatives]

            self.assertEqual(len(outputs), len(set(outputs)))
            self.assertTrue(all(len(path.stem) == 64 for path in outputs))

    def test_case_variant_pdfs_are_converted_to_distinct_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            first_pdf = source / "paper.pdf"
            second_pdf = source / "paper.PDF"
            first_pdf.write_bytes(b"lowercase extension")
            second_pdf.write_bytes(b"uppercase extension")
            if first_pdf.read_bytes() == second_pdf.read_bytes():
                self.skipTest("filesystem does not preserve case-distinct filenames")
            config = load_config(write_config(project, source))

            first = sync_library(
                config,
                lambda path: path.read_text(encoding="utf-8") + "\n",
            )
            first_output = document_output(config, "documents:paper.pdf")
            second_output = document_output(config, "documents:paper.PDF")
            second = sync_library(config, lambda _: self.fail("unexpected conversion"))

            self.assertEqual(first.converted, 2)
            self.assertNotEqual(first_output, second_output)
            self.assertIn("lowercase extension", first_output.read_text())
            self.assertIn("uppercase extension", second_output.read_text())
            self.assertEqual(second.unchanged, 2)

    def test_unique_legacy_document_path_remains_incremental(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdf = source / "document.pdf"
            pdf.write_bytes(b"legacy pdf")
            config = load_config(write_config(project, source))
            legacy = project / "knowledge/documents/documents/document.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("legacy markdown\n", encoding="utf-8")
            file_stat = pdf.stat()
            with LibraryState(config.state, config.root) as state:
                state.upsert_document(
                    {
                        "document_key": "documents:document.pdf",
                        "source_id": "documents",
                        "source_path": "document.pdf",
                        "output_path": str(legacy.relative_to(project)),
                        "size": file_stat.st_size,
                        "modified_ns": file_stat.st_mtime_ns,
                        "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                        "parser_version": PARSER_VERSION,
                        "present": 1,
                        "converted_at": "2026-09-16T00:00:00+09:00",
                        "checked_at": "2026-09-16T00:00:00+09:00",
                        "missing_since": None,
                        "error": None,
                    }
                )

            result = sync_library(config, lambda _: self.fail("unexpected conversion"))

            self.assertEqual(result.unchanged, 1)
            self.assertEqual(
                document_output(config, "documents:document.pdf"), legacy
            )
            self.assertEqual(legacy.read_text(encoding="utf-8"), "legacy markdown\n")

    def test_colliding_legacy_document_paths_migrate_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdfs = [source / "paper.PDF", source / "paper.pdf"]
            pdfs[0].write_bytes(b"uppercase document")
            pdfs[1].write_bytes(b"lowercase document")
            if pdfs[0].read_bytes() == pdfs[1].read_bytes():
                self.skipTest("filesystem does not preserve case-distinct filenames")
            config = load_config(write_config(project, source))
            legacy = project / "knowledge/documents/documents/paper.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("ambiguous legacy markdown\n", encoding="utf-8")
            with LibraryState(config.state, config.root) as state:
                for pdf in pdfs:
                    file_stat = pdf.stat()
                    relative = pdf.name
                    state.upsert_document(
                        {
                            "document_key": f"documents:{relative}",
                            "source_id": "documents",
                            "source_path": relative,
                            "output_path": str(legacy.relative_to(project)),
                            "size": file_stat.st_size,
                            "modified_ns": file_stat.st_mtime_ns,
                            "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                            "parser_version": PARSER_VERSION,
                            "present": 1,
                            "converted_at": "2026-09-16T00:00:00+09:00",
                            "checked_at": "2026-09-16T00:00:00+09:00",
                            "missing_since": None,
                            "error": None,
                        }
                    )

            first = sync_library(
                config,
                lambda path: path.read_text(encoding="utf-8") + "\n",
            )
            outputs = {
                key: document_output(config, key)
                for key in ("documents:paper.PDF", "documents:paper.pdf")
            }
            second = sync_library(config, lambda _: self.fail("unexpected conversion"))

            self.assertEqual(first.converted, 2)
            self.assertEqual(len(set(outputs.values())), 2)
            self.assertIn("uppercase document", outputs["documents:paper.PDF"].read_text())
            self.assertIn("lowercase document", outputs["documents:paper.pdf"].read_text())
            self.assertEqual(second.unchanged, 2)

    def test_legacy_collision_plan_has_a_stable_keeper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config = load_config(write_config(project, source))
            shared = project / "knowledge/documents/documents/paper.md"
            shared.parent.mkdir(parents=True)
            shared.write_text("legacy\n", encoding="utf-8")
            output_path = str(shared.relative_to(project))
            documents = [
                {"document_key": "documents:paper.pdf", "output_path": output_path},
                {"document_key": "documents:paper.PDF", "output_path": output_path},
            ]

            migrate, force = _collision_migration_plan(config, documents)

            self.assertEqual(migrate, {"documents:paper.pdf"})
            self.assertEqual(
                force, {"documents:paper.PDF", "documents:paper.pdf"}
            )

    def test_rejects_every_write_path_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            for key in ("documents", "conversations", "assets", "state", "temporary"):
                with self.subTest(key=key):
                    project = make_project(root / f"agent-{key}")
                    values = {
                        "documents": "knowledge/documents",
                        "conversations": "knowledge/conversations",
                        "assets": "knowledge/assets",
                        "state": ".research-store/library.sqlite",
                        "temporary": ".research-store/tmp",
                    }
                    values[key] = str(root / f"outside-{key}")
                    config_path = project / "config.toml"
                    config_path.write_text(
                        "[store]\n"
                        + "\n".join(
                            f"{name} = {json.dumps(value)}"
                            for name, value in values.items()
                        )
                        + "\n\n[[sources]]\n"
                        + 'id = "source"\n'
                        + f"path = {json.dumps(str(source))}\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(ValueError, "프로젝트 내부"):
                        load_config(config_path)

    def test_rejects_source_and_project_containment_in_both_directions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            inside = project / "originals"
            inside.mkdir()
            with self.assertRaisesRegex(ValueError, "서로 포함"):
                load_config(write_config(project, inside))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            with self.assertRaisesRegex(ValueError, "서로 포함"):
                load_config(write_config(project, root))

    def test_rejects_symlinked_output_directory(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are not supported")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            project = make_project(root / "agent")
            (project / "knowledge").mkdir()
            (project / "knowledge/documents").symlink_to(source, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "프로젝트 내부"):
                load_config(write_config(project, source))

    def test_atomic_write_rejects_internal_symlink_alias(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are not supported")
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            target = project / "config.toml"
            target.write_text("keep", encoding="utf-8")
            alias = project / "knowledge" / "document.md"
            alias.parent.mkdir()
            alias.symlink_to(target)

            with self.assertRaisesRegex(ValueError, "심볼릭 링크"):
                atomic_text(alias, "replace", project)

            self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_atomic_write_rejects_hard_link_to_source(self) -> None:
        if not hasattr(os, "link"):
            self.skipTest("hard links are not supported")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            original = source / "document.pdf"
            original.write_bytes(b"keep original")
            output = project / "knowledge" / "document.md"
            output.parent.mkdir()
            os.link(original, output)
            before = tree_snapshot(source)

            with self.assertRaisesRegex(ValueError, "하드 링크"):
                atomic_text(output, "replace", project)

            self.assertEqual(tree_snapshot(source), before)

    def test_missing_source_is_marked_without_deleting_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdf = source / "document.pdf"
            pdf.write_bytes(b"pdf")
            config = load_config(write_config(project, source))
            sync_library(config, lambda _: "content\n")
            output = document_output(config, "documents:document.pdf")
            pdf.unlink()

            result = sync_library(config, lambda _: "content\n")

            self.assertEqual(result.missing, 1)
            self.assertTrue(output.is_file())
            with sqlite3.connect(config.state) as database:
                present = database.execute(
                    "SELECT present FROM documents WHERE document_key = ?",
                    ("documents:document.pdf",),
                ).fetchone()[0]
            self.assertEqual(present, 0)

    def test_review_queue_records_candidate_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            (source / "document.pdf").write_bytes(b"pdf")
            config = load_config(write_config(project, source))

            result = sync_library(
                config,
                lambda _: ConversionResult(
                    "<!-- page: 1 -->\n\ncontent\n", {1: ["table-caption"]}
                ),
            )
            queue = pending_reviews(config)

            self.assertEqual(result.pages_needing_review, 1)
            self.assertEqual(queue[0]["document_key"], "documents:document.pdf")
            self.assertEqual(queue[0]["reasons"], ["table-caption"])
            self.assertEqual(
                queue[0]["original_pdf"], str((source / "document.pdf").resolve())
            )
            digest = hashlib.sha256(b"pdf").hexdigest()

            updated = complete_reviews(
                config,
                "documents:document.pdf",
                [1],
                expected_sha256=digest,
                status="needs_review",
                reviewer_model="gpt-5.6-sol",
                notes="One cell is still unclear.",
            )
            markdown = document_output(config, "documents:document.pdf")

            self.assertEqual(updated, 1)
            self.assertEqual(pending_reviews(config)[0]["status"], "needs_review")
            self.assertIn('visual_review: "needs-review"', markdown.read_text())

            updated = complete_reviews(
                config,
                "documents:document.pdf",
                [1],
                expected_sha256=digest,
                status="verified",
                reviewer_model="gpt-5.6-sol",
                notes="Table alignment confirmed.",
                visual_notes="표의 열 정렬과 단위를 원본 이미지에서 확인했습니다.",
            )
            self.assertEqual(updated, 1)
            self.assertEqual(pending_reviews(config), [])
            saved_markdown = markdown.read_text()
            self.assertIn('visual_review: "verified"', saved_markdown)
            self.assertIn("## Visual verification notes", saved_markdown)
            self.assertIn("### Pages 1", saved_markdown)
            self.assertIn(digest, saved_markdown)

    def test_visual_notes_reject_hard_link_to_source_note(self) -> None:
        if not hasattr(os, "link"):
            self.skipTest("hard links are not supported")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdf = source / "document.pdf"
            pdf.write_bytes(b"pdf")
            victim = source / "research-note.md"
            victim.write_text("original note\n", encoding="utf-8")
            config = load_config(write_config(project, source))
            sync_library(
                config,
                lambda _: ConversionResult(
                    "<!-- page: 1 -->\n\ncontent\n", {1: ["table-caption"]}
                ),
            )
            markdown = document_output(config, "documents:document.pdf")
            markdown.unlink()
            os.link(victim, markdown)

            with self.assertRaisesRegex(ValueError, "하드 링크"):
                complete_reviews(
                    config,
                    "documents:document.pdf",
                    [1],
                    expected_sha256=hashlib.sha256(b"pdf").hexdigest(),
                    status="verified",
                    reviewer_model="gpt-5.6-sol",
                    notes=None,
                    visual_notes="이 내용은 저장되면 안 됩니다.",
                )

            self.assertEqual(victim.read_text(encoding="utf-8"), "original note\n")
            self.assertEqual(pending_reviews(config)[0]["status"], "pending")

    def test_visual_notes_reject_markdown_bound_to_another_document(self) -> None:
        replacements = {
            "document_id": (
                'document_id: "sha256:' + "0" * 64 + '"',
                "document_id",
            ),
            "source_id": ('source_id: "another-source"', "source_id"),
            "source_path": ('source_path: "another.pdf"', "source_path"),
        }
        for field, (replacement, message) in replacements.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "source"
                project = make_project(root / "agent")
                source.mkdir()
                pdf = source / "document.pdf"
                pdf.write_bytes(b"pdf")
                config = load_config(write_config(project, source))
                sync_library(
                    config,
                    lambda _: ConversionResult(
                        "<!-- page: 1 -->\n\ncontent\n", {1: ["table-caption"]}
                    ),
                )
                markdown = document_output(config, "documents:document.pdf")
                lines = markdown.read_text(encoding="utf-8").splitlines()
                lines = [
                    replacement if line.startswith(f"{field}:") else line
                    for line in lines
                ]
                markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")

                with self.assertRaisesRegex(ValueError, message):
                    complete_reviews(
                        config,
                        "documents:document.pdf",
                        [1],
                        expected_sha256=hashlib.sha256(b"pdf").hexdigest(),
                        status="verified",
                        reviewer_model="gpt-5.6-sol",
                        notes=None,
                        visual_notes="저장되면 안 됩니다.",
                    )

                self.assertNotIn(
                    "저장되면 안 됩니다.", markdown.read_text(encoding="utf-8")
                )
                self.assertEqual(pending_reviews(config)[0]["status"], "pending")

    def test_review_complete_cli_accepts_visual_notes_only_from_stdin(self) -> None:
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
                    "<!-- page: 1 -->\n\ncontent\n", {1: ["table-caption"]}
                ),
            )
            digest = hashlib.sha256(b"pdf").hexdigest()

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_store.cli",
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
                input="원본 이미지에서 표의 정렬을 확인했습니다.",
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            markdown = document_output(config, "documents:document.pdf")
            self.assertIn("표의 정렬을 확인", markdown.read_text(encoding="utf-8"))

    @unittest.skipUnless(
        importlib.util.find_spec("pypdfium2"), "pypdfium2 is required"
    )
    def test_render_review_page_stays_inside_project_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            write_text_pdf(source / "document.pdf", "Table 1 Results")
            before = tree_snapshot(source)
            config = load_config(write_config(project, source))
            sync_library(config)

            rendered = render_review_pages(
                config, "documents:document.pdf", [1], dpi=120
            )

            self.assertEqual(len(rendered.paths), 1)
            self.assertEqual(
                rendered.sha256,
                hashlib.sha256((source / "document.pdf").read_bytes()).hexdigest(),
            )
            self.assertTrue(rendered.paths[0].is_file())
            self.assertTrue(rendered.paths[0].is_relative_to(project))
            self.assertEqual(tree_snapshot(source), before)

    @unittest.skipUnless(
        importlib.util.find_spec("pypdfium2"), "pypdfium2 is required"
    )
    def test_review_completion_rejects_a_changed_pdf_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            pdf = source / "document.pdf"
            write_text_pdf(pdf, "Table 1 Original")
            config = load_config(write_config(project, source))
            sync_library(config)
            rendered = render_review_pages(
                config, "documents:document.pdf", [1], dpi=120
            )
            write_text_pdf(pdf, "Table 1 Changed version")

            with self.assertRaisesRegex(ValueError, "검토 중 변경"):
                complete_reviews(
                    config,
                    "documents:document.pdf",
                    [1],
                    expected_sha256=rendered.sha256,
                    status="verified",
                    reviewer_model="gpt-5.6-sol",
                    notes=None,
                )

    def test_tampered_database_output_path_cannot_escape_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            (source / "document.pdf").write_bytes(b"pdf")
            victim = source / "victim.md"
            victim.write_text("unchanged", encoding="utf-8")
            config = load_config(write_config(project, source))
            sync_library(
                config,
                lambda _: ConversionResult("content\n", {1: ["table-caption"]}),
            )
            with sqlite3.connect(config.state) as database:
                database.execute(
                    "UPDATE documents SET output_path = '../source/victim.md'"
                )

            with self.assertRaisesRegex(ValueError, "출력 경로"):
                complete_reviews(
                    config,
                    "documents:document.pdf",
                    [1],
                    expected_sha256=hashlib.sha256(b"pdf").hexdigest(),
                    status="verified",
                    reviewer_model="gpt-5.6-sol",
                    notes=None,
                )
            self.assertEqual(victim.read_text(encoding="utf-8"), "unchanged")

    def test_tampered_database_source_path_cannot_escape_registered_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            write_text_pdf(source / "document.pdf", "Table 1 Results")
            outside = root / "outside.pdf"
            write_text_pdf(outside, "Outside")
            config = load_config(write_config(project, source))
            sync_library(config)
            with sqlite3.connect(config.state) as database:
                database.execute(
                    "UPDATE documents SET source_path = '../../outside.pdf'"
                )

            with self.assertRaisesRegex(ValueError, "상대 경로"):
                render_review_pages(config, "documents:document.pdf", [1], dpi=120)

    def test_sqlite_hard_link_cannot_modify_external_file(self) -> None:
        if not hasattr(os, "link"):
            self.skipTest("hard links are not supported")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            victim = source / "victim.pdf"
            victim.write_bytes(b"must stay unchanged")
            config = load_config(write_config(project, source))
            config.state.parent.mkdir(parents=True)
            os.link(victim, config.state)

            with self.assertRaisesRegex(ValueError, "하드 링크"):
                sync_library(config, lambda _: "content\n")
            self.assertEqual(victim.read_bytes(), b"must stay unchanged")

    def test_sqlite_temporary_storage_stays_in_memory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory) / "agent")
            state_path = project / ".research-store/library.sqlite"

            with LibraryState(state_path, project) as state:
                temp_store = state.connection.execute(
                    "PRAGMA temp_store"
                ).fetchone()[0]

            self.assertEqual(temp_store, 2)

    def test_source_pdf_symlink_is_ignored(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are not supported")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            outside = root / "outside.pdf"
            outside.write_bytes(b"outside")
            (source / "linked.pdf").symlink_to(outside)
            config = load_config(write_config(project, source))

            result = sync_library(config, lambda _: "content\n")

            self.assertEqual(result.discovered, 0)

    def test_source_add_and_remove_only_change_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            (source / "document.pdf").write_bytes(b"original")
            before = tree_snapshot(source)
            config_path = project / "config.toml"

            initialize_config(config_path)
            self.assertEqual(load_config(config_path).sources, ())
            added = add_sources(config_path, [source])
            self.assertEqual(len(added), 1)
            sync_library(load_config(config_path), lambda _: "content\n")
            generated = next((project / "knowledge/documents").rglob("*.md"))
            removed = remove_sources(config_path, [added[0].id])

            self.assertEqual([item.id for item in removed], [added[0].id])
            self.assertTrue(generated.is_file())
            stopped = load_config(config_path).sources
            self.assertEqual(len(stopped), 1)
            self.assertFalse(stopped[0].enabled)
            reenabled = add_sources(config_path, [source])
            self.assertEqual([item.id for item in reenabled], [added[0].id])
            self.assertTrue(load_config(config_path).sources[0].enabled)
            self.assertEqual(tree_snapshot(source), before)

    def test_offline_source_remains_listable_removable_and_not_marked_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            offline = root / "source-offline"
            project = make_project(root / "agent")
            source.mkdir()
            (source / "document.pdf").write_bytes(b"original")
            config_path = project / "config.toml"
            initialize_config(config_path)
            added = add_sources(config_path, [source])[0]
            sync_library(load_config(config_path), lambda _: "content\n")
            source.rename(offline)

            rows = source_rows(config_path)
            result = sync_library(load_config(config_path), lambda _: "content\n")
            removed = remove_sources(config_path, [added.id])

            self.assertFalse(rows[0]["available"])
            self.assertEqual(result.unavailable_sources, 1)
            self.assertEqual(result.missing, 0)
            self.assertEqual([item.id for item in removed], [added.id])
            self.assertFalse(load_config(config_path).sources[0].enabled)

    @unittest.skipIf(os.name == "nt", "POSIX permission test")
    def test_unreadable_source_is_reported_without_marking_documents_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            (source / "document.pdf").write_bytes(b"original")
            config = load_config(write_config(project, source))
            sync_library(config, lambda _: "content\n")
            source.chmod(0)
            try:
                result = sync_library(config, lambda _: "content\n")
            finally:
                source.chmod(0o700)

            self.assertEqual(result.unavailable_sources, 1)
            self.assertEqual(result.missing, 0)
            self.assertIn("읽기 권한", result.source_errors[0]["error"])

    def test_conversation_saves_inside_project_from_stdin_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config = load_config(write_config(project, source))
            payload = {
                "title": "수식 변환 설계",
                "created_at": "2026-09-15T15:30:00+09:00",
                "scope": "current-topic",
                "capture_status": "complete",
                "summary": "수식이 있는 페이지만 이미지로 검토한다.",
                "tags": ["PDF", "수식"],
                "aliases": ["equation extraction"],
                "user_points": ["Sol high를 사용한다."],
                "decisions": ["원본 PDF는 읽기 전용이다."],
                "unverified": ["Luna xhigh 검색 품질은 평가가 필요하다."],
                "open_questions": [],
                "transcript": [
                    {"role": "user", "content": "이 대화를 저장해줘."},
                    {"role": "assistant", "content": "범위를 선택해 주세요."},
                ],
            }

            output = save_conversation(config, payload)
            saved = output.read_text(encoding="utf-8")

            self.assertTrue(output.is_relative_to(project))
            self.assertIn('type: "conversation"', saved)
            self.assertIn("## 검색용 요약", saved)
            self.assertIn("> 이 대화를 저장해줘.", saved)

    def test_conversation_output_rejects_hard_link_to_source_note(self) -> None:
        if not hasattr(os, "link"):
            self.skipTest("hard links are not supported")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            victim = source / "research-note.md"
            victim.write_text("original note\n", encoding="utf-8")
            config = load_config(write_config(project, source))
            payload = {
                "title": "수식 변환 설계",
                "created_at": "2026-09-15T15:30:00+09:00",
                "scope": "current-topic",
                "capture_status": "complete",
                "summary": "요약",
                "transcript": [{"role": "user", "content": "원문"}],
            }
            identity = hashlib.sha256(
                json.dumps(
                    {
                        "title": payload["title"],
                        "created_at": payload["created_at"],
                        "transcript": payload["transcript"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            output = (
                config.conversations
                / "2026/09"
                / f"15-{identity}.md"
            )
            output.parent.mkdir(parents=True)
            os.link(victim, output)

            with self.assertRaisesRegex(ValueError, "하드 링크"):
                save_conversation(config, payload)

            self.assertEqual(victim.read_text(encoding="utf-8"), "original note\n")

    def test_conversation_hash_prefix_collision_keeps_both_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config = load_config(write_config(project, source))

            def payload(message: str) -> dict[str, object]:
                return {
                    "title": "collision",
                    "created_at": "2026-09-17T10:00:00+09:00",
                    "scope": "current-topic",
                    "capture_status": "complete",
                    "summary": message,
                    "transcript": [{"role": "user", "content": message}],
                }

            first = save_conversation(config, payload("message 965"))
            first_content = first.read_text(encoding="utf-8")
            second = save_conversation(config, payload("message 1486"))

            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(encoding="utf-8"), first_content)
            self.assertIn("message 1486", second.read_text(encoding="utf-8"))
            with sqlite3.connect(config.state) as database:
                count = database.execute(
                    "SELECT COUNT(*) FROM conversations"
                ).fetchone()[0]
            self.assertEqual(count, 2)

    def test_legacy_conversation_record_keeps_its_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config = load_config(write_config(project, source))
            payload = {
                "title": "수식 변환 설계",
                "created_at": "2026-09-15T15:30:00+09:00",
                "scope": "current-topic",
                "capture_status": "complete",
                "summary": "legacy summary",
                "transcript": [{"role": "user", "content": "legacy transcript"}],
            }
            identity = hashlib.sha256(
                json.dumps(
                    {
                        "title": payload["title"],
                        "created_at": payload["created_at"],
                        "transcript": payload["transcript"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            legacy_id = f"conversation-20260915-{identity[:12]}"
            legacy = (
                config.conversations
                / "2026/09"
                / f"15-수식-변환-설계-{identity[:6]}.md"
            )
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                f"---\nid: {json.dumps(legacy_id)}\n---\nlegacy\n",
                encoding="utf-8",
            )
            with LibraryState(config.state, config.root) as state:
                state.register_conversation(
                    conversation_id=legacy_id,
                    output_path=str(legacy.relative_to(project)),
                    title=str(payload["title"]),
                    scope="current-topic",
                    created_at=str(payload["created_at"]),
                    tags=[],
                    aliases=[],
                )

            saved = save_conversation(config, payload)

            self.assertEqual(saved, legacy)
            self.assertIn(f'id: "{legacy_id}"', saved.read_text(encoding="utf-8"))
            self.assertFalse((config.conversations / "2026/09" / f"15-{identity}.md").exists())
            with LibraryState(config.state, config.root) as state:
                self.assertIsNotNone(state.get_conversation(legacy_id))
                self.assertEqual(state.status()["conversations"], 1)

    def test_conversation_db_conflict_is_checked_before_markdown_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config = load_config(write_config(project, source))
            payload = {
                "title": "ordering",
                "created_at": "2026-09-17T10:00:00+09:00",
                "scope": "current-topic",
                "capture_status": "complete",
                "summary": "must not be written",
                "transcript": [{"role": "user", "content": "ordering check"}],
            }
            identity = hashlib.sha256(
                json.dumps(
                    {
                        "title": payload["title"],
                        "created_at": payload["created_at"],
                        "transcript": payload["transcript"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            output = config.conversations / "2026/09" / f"17-{identity}.md"
            with LibraryState(config.state, config.root) as state:
                state.register_conversation(
                    conversation_id="different-conversation",
                    output_path=str(output.relative_to(project)),
                    title="different",
                    scope="current-topic",
                    created_at="2026-09-17T09:00:00+09:00",
                    tags=[],
                    aliases=[],
                )

            with self.assertRaises(sqlite3.IntegrityError):
                save_conversation(config, payload)

            self.assertFalse(output.exists())

    def test_save_conversation_cli_reads_json_from_stdin_without_payload_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            config_path = write_config(project, source)
            payload = {
                "title": "stdin 대화 저장",
                "created_at": "2026-09-17T10:00:00+09:00",
                "scope": "current-topic",
                "capture_status": "complete",
                "summary": "표준 입력 저장 확인",
                "transcript": [{"role": "user", "content": "이 내용을 저장해줘."}],
            }

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "research_store.cli",
                    "--config",
                    str(config_path),
                    "save-conversation",
                ],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            response = json.loads(result.stdout)
            saved = Path(response["saved"])
            self.assertTrue(saved.is_file())
            self.assertIn("이 내용을 저장해줘.", saved.read_text(encoding="utf-8"))
            self.assertEqual(list(project.rglob("*.json")), [])

    def test_deleting_agent_project_leaves_external_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = make_project(root / "agent")
            source.mkdir()
            (source / "document.pdf").write_bytes(b"original")
            before = tree_snapshot(source)
            config = load_config(write_config(project, source))
            sync_library(config, lambda _: "content\n")

            shutil.rmtree(project)

            self.assertFalse(project.exists())
            self.assertEqual(tree_snapshot(source), before)

    def test_installer_rejects_managed_path_links_before_network_access(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        for managed_name in (".tools", ".python", ".venv"):
            with self.subTest(managed_name=managed_name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    project = make_project(root / "agent")
                    source = root / "source"
                    source.mkdir()
                    (source / "original.pdf").write_bytes(b"keep")
                    before = tree_snapshot(source)
                    shutil.copy2(repository / "install.sh", project / "install.sh")
                    (project / managed_name).symlink_to(
                        source, target_is_directory=True
                    )

                    result = subprocess.run(
                        ["sh", str(project / "install.sh")],
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("링크", result.stderr)
                    self.assertEqual(tree_snapshot(source), before)

    def test_installer_rejects_hard_linked_uv_before_network_access(self) -> None:
        if not hasattr(os, "link"):
            self.skipTest("hard links are not supported")
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root / "agent")
            source = root / "source"
            source.mkdir()
            victim = source / "original.pdf"
            victim.write_bytes(b"keep")
            before = tree_snapshot(source)
            shutil.copy2(repository / "install.sh", project / "install.sh")
            (project / ".tools").mkdir()
            os.link(victim, project / ".tools" / "uv")

            result = subprocess.run(
                ["sh", str(project / "install.sh")],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("하드 링크", result.stderr)
            self.assertEqual(tree_snapshot(source), before)

    def test_installer_has_no_predictable_download_script(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        installer = (repository / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("research-store-uv-installer", installer)
        self.assertIn("actual_checksum", installer)
        self.assertIn("curl -q --proto '=https'", installer)
        self.assertIn("unset SSLKEYLOGFILE QLOGDIR TAR_OPTIONS", installer)
        self.assertIn("unset PYTHONINSPECT PYTHONSTARTUP PYTHON_HISTORY", installer)
        self.assertIn("unset PERL5OPT PERL5LIB PERLLIB", installer)
        self.assertNotIn("awk '{print $1}'", installer)
        self.assertIn('"$VENV/bin/python" -I -B -c', installer)

    def test_installer_keeps_build_temporary_files_inside_project(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        installer = (repository / "install.sh").read_text(encoding="utf-8")

        self.assertIn('INSTALL_TMP="$BOOTSTRAP/tmp"', installer)
        self.assertIn('export TMPDIR="$INSTALL_TMP"', installer)
        self.assertIn('export TMP="$INSTALL_TMP"', installer)
        self.assertIn('export TEMP="$INSTALL_TMP"', installer)
        self.assertIn(
            'UV_PYTHON_CACHE_DIR="$BOOTSTRAP/python-cache"', installer
        )
        self.assertIn("env -i", installer)

    def test_launcher_ignores_external_python_cache_and_temp_locations(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "source"
            outside.mkdir()
            environment = os.environ.copy()
            environment["PYTHONPYCACHEPREFIX"] = str(outside / "pycache")
            environment["TMPDIR"] = str(outside / "tmp")
            environment["XDG_CACHE_HOME"] = str(outside / "cache")
            before = tree_snapshot(outside)

            result = subprocess.run(
                [str(repository / "research-store"), "--help"],
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(tree_snapshot(outside), before)

    def test_launcher_without_project_marker_writes_nothing(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            unowned = Path(directory) / "source"
            unowned.mkdir()
            launcher = unowned / "research-store"
            shutil.copy2(repository / "research-store", launcher)
            before = tree_snapshot(unowned)

            result = subprocess.run(
                [str(launcher), "--help"],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("프로젝트 루트", result.stderr)
            self.assertEqual(tree_snapshot(unowned), before)


if __name__ == "__main__":
    unittest.main()
