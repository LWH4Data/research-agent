from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from research_store.config import load_config
from research_store.conversations import save_conversation
from research_store.sync import (
    ConversionResult,
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
id = "papers"
path = "{source}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


class SyncLibraryTests(unittest.TestCase):
    def test_pypdf_converts_text_and_flags_table_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "paper.pdf"
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

    def test_sync_is_incremental_and_never_changes_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            pdf = source / "nested" / "paper.PDF"
            pdf.parent.mkdir()
            original = b"unchanged source bytes"
            pdf.write_bytes(original)
            config = load_config(write_config(project, source))
            seen_paths: list[Path] = []

            def fake_converter(path: Path) -> str:
                seen_paths.append(path)
                self.assertFalse(path.is_relative_to(source))
                return "# Parsed paper\n\nUseful content.\n"

            first = sync_library(config, fake_converter)
            second = sync_library(config, fake_converter)

            self.assertEqual(first.converted, 1)
            self.assertEqual(second.unchanged, 1)
            self.assertEqual(len(seen_paths), 1)
            self.assertEqual(pdf.read_bytes(), original)
            output = project / "knowledge/documents/papers/nested/paper.md"
            self.assertIn('source_path: "nested/paper.PDF"', output.read_text())

            with sqlite3.connect(config.state) as database:
                self.assertEqual(database.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 1)

    def test_rejects_output_inside_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "papers"
            source.mkdir()
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                f"""
[store]
documents = "{source / 'generated'}"
conversations = "conversations"
assets = "assets"
state = "library.sqlite"
temporary = "tmp"

[[sources]]
id = "papers"
path = "{source}"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "쓰기 경로가 원본 디렉터리 안"):
                load_config(config_path)

    def test_missing_source_is_marked_without_deleting_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            pdf = source / "paper.pdf"
            pdf.write_bytes(b"pdf")
            config = load_config(write_config(project, source))
            sync_library(config, lambda _: "content\n")
            output = project / "knowledge/documents/papers/paper.md"
            pdf.unlink()

            result = sync_library(config, lambda _: "content\n")

            self.assertEqual(result.missing, 1)
            self.assertTrue(output.is_file())
            with sqlite3.connect(config.state) as database:
                present = database.execute(
                    "SELECT present FROM documents WHERE document_key = ?",
                    ("papers:paper.pdf",),
                ).fetchone()[0]
            self.assertEqual(present, 0)

    def test_review_queue_records_candidate_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            (source / "paper.pdf").write_bytes(b"pdf")
            config = load_config(write_config(project, source))

            result = sync_library(
                config,
                lambda _: ConversionResult(
                    "<!-- page: 1 -->\n\ncontent\n", {1: ["table-caption"]}
                ),
            )
            queue = pending_reviews(config)

            self.assertEqual(result.pages_needing_review, 1)
            self.assertEqual(queue[0]["document_key"], "papers:paper.pdf")
            self.assertEqual(queue[0]["reasons"], ["table-caption"])
            self.assertEqual(queue[0]["original_pdf"], str((source / "paper.pdf").resolve()))

            updated = complete_reviews(
                config,
                "papers:paper.pdf",
                [1],
                status="verified",
                reviewer_model="gpt-5.6-sol",
                notes="Table alignment confirmed.",
            )
            markdown = project / "knowledge/documents/papers/paper.md"

            self.assertEqual(updated, 1)
            self.assertEqual(pending_reviews(config), [])
            self.assertIn('visual_review: "verified"', markdown.read_text())

    @unittest.skipUnless(shutil.which("pdftoppm"), "pdftoppm is required")
    def test_render_review_page_creates_png_outside_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            write_text_pdf(source / "paper.pdf", "Table 1 Results")
            config = load_config(write_config(project, source))
            sync_library(config)

            rendered = render_review_pages(config, "papers:paper.pdf", [1], dpi=120)

            self.assertEqual(len(rendered), 1)
            self.assertTrue(rendered[0].is_file())
            self.assertFalse(rendered[0].is_relative_to(source))

    def test_conversation_saves_summary_and_selected_verbatim_messages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            config = load_config(write_config(project, source))
            payload = project / "conversation.json"
            payload.write_text(
                json.dumps(
                    {
                        "title": "수식 변환 설계",
                        "created_at": "2026-09-15T15:30:00+09:00",
                        "scope": "current-topic",
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
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            output = save_conversation(config, payload)
            saved = output.read_text(encoding="utf-8")

            self.assertIn('type: "conversation"', saved)
            self.assertIn("## 검색용 요약", saved)
            self.assertIn("> 이 대화를 저장해줘.", saved)
            with sqlite3.connect(config.state) as database:
                self.assertEqual(
                    database.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1
                )


if __name__ == "__main__":
    unittest.main()
