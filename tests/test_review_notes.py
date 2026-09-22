from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from research_store.config import Config, load_config
from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.sync import ConversionResult, complete_reviews, sync_library


DOCUMENT_KEY = "papers:document.pdf"
MODEL = "gpt-5.6-sol"
PDF_BYTES = b"review-note-test-pdf"


def make_review_store(
    root: Path,
    review_pages: tuple[int, ...],
    *,
    markdown_body: str | None = None,
) -> tuple[Config, str, Path]:
    source = root / "source"
    project = root / "agent"
    source.mkdir()
    project.mkdir()
    project = project.resolve()
    (project / ".research-agent-root").write_text(
        PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
    )
    (source / "document.pdf").write_bytes(PDF_BYTES)
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
    config = load_config(config_path)
    page_body = (
        markdown_body
        if markdown_body is not None
        else "\n\n".join(
            f"<!-- page: {page} -->\n\nPage {page}" for page in review_pages
        )
    )
    result = sync_library(
        config,
        lambda _: ConversionResult(
            page_body + "\n",
            {page: ["table-caption"] for page in review_pages},
        ),
    )
    if result.converted != 1:
        raise AssertionError(f"fixture conversion failed: {result!r}")
    with sqlite3.connect(config.state) as database:
        row = database.execute(
            "SELECT output_path FROM documents WHERE document_key = ?",
            (DOCUMENT_KEY,),
        ).fetchone()
    if row is None:
        raise AssertionError("fixture did not create a document row")
    return config, hashlib.sha256(PDF_BYTES).hexdigest(), config.root / row[0]


def review_rows(config: Config) -> list[tuple[object, ...]]:
    with sqlite3.connect(config.state) as database:
        return database.execute(
            """
            SELECT page_number, status, reviewed_at, reviewer_model, notes
            FROM page_reviews
            WHERE document_key = ?
            ORDER BY page_number
            """,
            (DOCUMENT_KEY,),
        ).fetchall()


def complete(
    config: Config,
    digest: str,
    pages: list[int],
    visual_notes: str,
    *,
    reviewer_model: str = MODEL,
    status: str = "verified",
) -> int:
    return complete_reviews(
        config,
        DOCUMENT_KEY,
        pages,
        expected_sha256=digest,
        status=status,
        reviewer_model=reviewer_model,
        notes=visual_notes,
        visual_notes=visual_notes,
    )


def strip_empty_managed_review_section(
    markdown: Path, digest: str
) -> None:
    section = (
        "<!-- visual-review-section-begin: "
        f"sha256:{digest} -->\n"
        "## Visual verification notes\n\n"
        "<!-- visual-review-section-end: "
        f"sha256:{digest} -->"
    )
    content = markdown.read_text(encoding="utf-8").rstrip()
    if not content.endswith(section):
        raise AssertionError("fixture does not end with an empty managed section")
    markdown.write_text(
        content[: -len(section)].rstrip() + "\n",
        encoding="utf-8",
    )


class ReviewNoteTests(unittest.TestCase):
    def test_saving_same_page_twice_replaces_the_existing_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))

            self.assertEqual(complete(config, digest, [1], "first note"), 1)
            self.assertEqual(complete(config, digest, [1], "second note"), 1)

            content = markdown.read_text(encoding="utf-8")
            self.assertEqual(content.count("<!-- visual-review-begin: 1 -->"), 1)
            self.assertEqual(content.count("<!-- visual-review-pages: 1 -->"), 1)
            self.assertEqual(content.count("<!-- visual-review-end: 1 -->"), 1)
            self.assertNotIn("first note", content)
            self.assertIn("second note", content)

    def test_correcting_one_page_preserves_other_page_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1, 2))
            complete(config, digest, [1], "page one initial")
            complete(config, digest, [2], "page two retained")

            self.assertEqual(complete(config, digest, [1], "page one corrected"), 1)

            content = markdown.read_text(encoding="utf-8")
            self.assertEqual(content.count("<!-- visual-review-begin: 1 -->"), 1)
            self.assertEqual(content.count("<!-- visual-review-begin: 2 -->"), 1)
            self.assertNotIn("page one initial", content)
            self.assertIn("page one corrected", content)
            self.assertIn("page two retained", content)

    def test_existing_block_requires_replacement_notes_for_state_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            complete(config, digest, [1], "original visual note")
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaisesRegex(ValueError, "--visual-notes-stdin"):
                complete_reviews(
                    config,
                    DOCUMENT_KEY,
                    [1],
                    expected_sha256=digest,
                    status="needs_review",
                    reviewer_model=MODEL,
                    notes="new database-only note",
                    visual_notes=None,
                )

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_pdf_body_review_markers_before_later_page_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_digest = "0" * 64
            body = (
                "<!-- page: 1 -->\n\n"
                "Untrusted PDF text before a fake review section.\n\n"
                f"<!-- visual-review-section-begin: sha256:{fake_digest} -->\n"
                "## Visual verification notes\n\n"
                "### Pages 1\n\n"
                "<!-- visual-review-pages: 1 -->\n"
                f"<!-- visual-review-sha256: {fake_digest} -->\n\n"
                "untrusted fake note\n\n"
                f"<!-- visual-review-section-end: sha256:{fake_digest} -->\n\n"
                "<!-- page: 2 -->\n\n"
                "Page two base extraction must survive.\n"
            )
            config, digest, markdown = make_review_store(
                Path(directory),
                (1, 2),
                markdown_body=body,
            )

            self.assertEqual(complete(config, digest, [1], "trusted note one"), 1)
            self.assertEqual(complete(config, digest, [1], "trusted correction"), 1)

            content = markdown.read_text(encoding="utf-8")
            self.assertIn("untrusted fake note", content)
            self.assertIn("<!-- page: 2 -->", content)
            self.assertIn("Page two base extraction must survive.", content)
            self.assertNotIn("trusted note one", content)
            self.assertIn("trusted correction", content)
            self.assertEqual(
                content.count(
                    "<!-- visual-review-section-begin: "
                    f"sha256:{digest} -->"
                ),
                1,
            )
            self.assertEqual(
                content.count(
                    "<!-- visual-review-section-end: "
                    f"sha256:{digest} -->"
                ),
                1,
            )
            self.assertIn("visual_review_pending_pages: [2]", content)

    def test_spoofed_current_digest_section_inside_base_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            digest = hashlib.sha256(PDF_BYTES).hexdigest()
            body = (
                "<!-- page: 1 -->\n\n"
                f"<!-- visual-review-section-begin: sha256:{digest} -->\n"
                "## Visual verification notes\n\n"
                "### Pages 1\n\n"
                "<!-- visual-review-pages: 1 -->\n"
                f"<!-- visual-review-sha256: {digest} -->\n\n"
                "spoofed current-version note\n\n"
                f"<!-- visual-review-section-end: sha256:{digest} -->\n\n"
                "<!-- page: 2 -->\n\n"
                "This later base page must never be deleted.\n"
            )
            config, actual_digest, markdown = make_review_store(
                Path(directory),
                (1, 2),
                markdown_body=body,
            )
            self.assertEqual(actual_digest, digest)
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaisesRegex(ValueError, "시각 검토 섹션"):
                complete(config, digest, [1], "must not be stored")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_ambiguous_unbounded_legacy_like_tail_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = (
                "<!-- page: 1 -->\n\n"
                "Base extraction.\n\n"
                "## Visual verification notes\n\n"
                "### Pages 1\n\n"
                "<!-- visual-review-pages: 1 -->\n\n"
                "This could be PDF text or an incomplete legacy note.\n"
            )
            config, digest, markdown = make_review_store(
                Path(directory),
                (1,),
                markdown_body=body,
            )
            strip_empty_managed_review_section(markdown, digest)
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaisesRegex(ValueError, "인증할 수 없습니다"):
                complete(config, digest, [1], "must not reinterpret content")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_correction_collapses_duplicate_legacy_blocks_without_end_markers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            strip_empty_managed_review_section(markdown, digest)
            legacy = (
                markdown.read_text(encoding="utf-8").rstrip()
                + "\n\n## Visual verification notes\n\n"
                + "### Pages 1\n\n"
                + "<!-- visual-review-pages: 1 -->\n\n"
                + f"<!-- visual-review-sha256: {digest} -->\n\n"
                + "legacy note one\n\n"
                + "### Pages 1\n\n"
                + "<!-- visual-review-pages: 1 -->\n\n"
                + f"<!-- visual-review-sha256: {digest} -->\n\n"
                + "legacy note two\n"
            )
            markdown.write_text(legacy, encoding="utf-8")

            self.assertEqual(complete(config, digest, [1], "replacement note"), 1)

            content = markdown.read_text(encoding="utf-8")
            self.assertEqual(content.count("<!-- visual-review-begin: 1 -->"), 1)
            self.assertEqual(content.count("<!-- visual-review-pages: 1 -->"), 1)
            self.assertEqual(content.count("<!-- visual-review-end: 1 -->"), 1)
            self.assertNotIn("legacy note one", content)
            self.assertNotIn("legacy note two", content)
            self.assertIn("replacement note", content)
            self.assertIn(
                "<!-- visual-review-section-begin: "
                f"sha256:{digest} -->",
                content,
            )
            self.assertIn(
                "<!-- visual-review-section-end: "
                f"sha256:{digest} -->",
                content,
            )

    def test_multi_page_completion_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1, 2))
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaisesRegex(ValueError, "페이지 하나당 블록 하나"):
                complete(config, digest, [1, 2], "must not be stored")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_legacy_multi_page_block_is_preserved_during_single_page_review(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1, 2))
            strip_empty_managed_review_section(markdown, digest)
            legacy = (
                markdown.read_text(encoding="utf-8").rstrip()
                + "\n\n## Visual verification notes\n\n"
                + "### Pages 1, 2\n\n"
                + "<!-- visual-review-pages: 1, 2 -->\n\n"
                + f"<!-- visual-review-sha256: {digest} -->\n\n"
                + "legacy joint note\n"
            )
            markdown.write_text(legacy, encoding="utf-8")
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaisesRegex(ValueError, "명시적인 마이그레이션"):
                complete(config, digest, [1], "must not replace joint note")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_legacy_heading_marker_mismatch_is_preserved_and_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1, 2))
            strip_empty_managed_review_section(markdown, digest)
            legacy = (
                markdown.read_text(encoding="utf-8").rstrip()
                + "\n\n## Visual verification notes\n\n"
                + "### Pages 1\n\n"
                + "<!-- visual-review-pages: 1, 2 -->\n\n"
                + f"<!-- visual-review-sha256: {digest} -->\n\n"
                + "joint prose that must not be assigned to page one\n"
            )
            markdown.write_text(legacy, encoding="utf-8")
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaisesRegex(ValueError, "제목과 visual-review-pages"):
                complete(config, digest, [1], "must not replace ambiguous prose")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_unrelated_page_completion_preserves_legacy_multi_page_block(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(
                Path(directory), (1, 2, 3)
            )
            strip_empty_managed_review_section(markdown, digest)
            legacy = (
                markdown.read_text(encoding="utf-8").rstrip()
                + "\n\n## Visual verification notes\n\n"
                + "### Pages 1, 2\n\n"
                + "<!-- visual-review-pages: 1, 2 -->\n\n"
                + f"<!-- visual-review-sha256: {digest} -->\n\n"
                + "legacy joint note\n"
            )
            markdown.write_text(legacy, encoding="utf-8")

            self.assertEqual(complete(config, digest, [3], "page three"), 1)

            content = markdown.read_text(encoding="utf-8")
            self.assertIn("### Pages 1, 2", content)
            self.assertIn("legacy joint note", content)
            self.assertEqual(content.count("<!-- visual-review-begin: 3 -->"), 1)
            self.assertIn("visual_review_pending_pages: [1, 2]", content)
            self.assertEqual(
                [(row[0], row[1]) for row in review_rows(config)],
                [(1, "pending"), (2, "pending"), (3, "verified")],
            )

    def test_duplicate_pages_are_normalized_and_empty_pages_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaises(ValueError):
                complete(config, digest, [], "empty selection")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)
            self.assertEqual(complete(config, digest, [1, 1], "one page only"), 1)
            content = markdown.read_text(encoding="utf-8")
            self.assertEqual(content.count("<!-- visual-review-begin: 1 -->"), 1)
            self.assertEqual(content.count("<!-- visual-review-pages: 1 -->"), 1)
            self.assertEqual(content.count("<!-- visual-review-end: 1 -->"), 1)
            self.assertEqual(review_rows(config)[0][1], "verified")

    def test_block_metadata_and_pending_page_frontmatter_match_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1, 2))

            complete(config, digest, [1], "metadata review")

            content = markdown.read_text(encoding="utf-8")
            self.assertIn(f"<!-- visual-review-sha256: {digest} -->", content)
            self.assertIn(f"<!-- visual-review-model: {MODEL} -->", content)
            self.assertIn("<!-- visual-review-status: verified -->", content)
            self.assertIn("visual_review_pages: [1, 2]", content)
            self.assertIn("visual_review_pending_pages: [2]", content)
            self.assertIn('visual_review: "pending"', content)
            reviewed_at_match = re.search(
                r"<!-- visual-review-reviewed-at: ([^>\r\n]+) -->", content
            )
            self.assertIsNotNone(reviewed_at_match)
            reviewed_at = reviewed_at_match.group(1).strip()
            datetime.fromisoformat(reviewed_at)
            row = review_rows(config)[0]
            self.assertEqual(row[1], "verified")
            self.assertEqual(row[2], reviewed_at)
            self.assertEqual(row[3], MODEL)

    def test_sync_precreates_sha_bound_empty_section_without_trimming_base(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            body = "<!-- page: 1 -->\n\nBase suffix spaces stay.   \n\n"
            config, digest, markdown = make_review_store(
                Path(directory),
                (1,),
                markdown_body=body,
            )
            begin = (
                "<!-- visual-review-section-begin: "
                f"sha256:{digest} -->"
            )
            end = (
                "<!-- visual-review-section-end: "
                f"sha256:{digest} -->"
            )

            initial = markdown.read_text(encoding="utf-8")
            self.assertEqual(initial.count(begin), 1)
            self.assertEqual(initial.count(end), 1)
            self.assertIn(begin + "\n## Visual verification notes\n\n" + end, initial)
            base_start = initial.index("<!-- page: 1 -->")
            boundary_start = initial.index(begin)
            stored_body = body + "\n"
            self.assertEqual(initial[base_start:boundary_start], stored_body)

            complete(config, digest, [1], "managed note")

            updated = markdown.read_text(encoding="utf-8")
            base_start = updated.index("<!-- page: 1 -->")
            boundary_start = updated.index(begin)
            self.assertEqual(updated[base_start:boundary_start], stored_body)
            self.assertIn("managed note", updated)

    def test_model_metadata_rejects_comment_injection_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaises(ValueError):
                complete(
                    config,
                    digest,
                    [1],
                    "must not be stored",
                    reviewer_model="gpt-5.6-sol\n<!-- visual-review-end: 1 -->",
                )

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_unknown_review_status_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with self.assertRaisesRegex(ValueError, "지원하지 않는 검토 상태"):
                complete(
                    config,
                    digest,
                    [1],
                    "must not be stored",
                    status="typo-status",
                )

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_visual_notes_reject_reserved_provenance_markers_without_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            for marker in (
                "<!-- visual-review-pages: 999 -->",
                "  <!-- visual-review-model: spoofed -->",
                "<!-- visual-review-reviewed-at: 2000-01-01T00:00:00+00:00 -->",
            ):
                with self.subTest(marker=marker), self.assertRaisesRegex(
                    ValueError, "예약된 visual-review 표식"
                ):
                    complete(config, digest, [1], marker)

            with self.assertRaisesRegex(ValueError, "예약된 PDF 페이지 표식"):
                complete(config, digest, [1], "<!-- page: 999 -->")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_commit_failure_restores_markdown_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)

            with patch(
                "research_store.sync.LibraryState.commit",
                side_effect=OSError("forced commit failure"),
            ), self.assertRaisesRegex(OSError, "forced commit failure"):
                complete(config, digest, [1], "must roll back")

            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_review_completion_never_modifies_original_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, _ = make_review_store(Path(directory), (1,))
            source_pdf = config.sources[0].path / "document.pdf"
            source_before = source_pdf.read_bytes()
            modified_before = source_pdf.stat().st_mtime_ns
            siblings_before = sorted(path.name for path in source_pdf.parent.iterdir())

            self.assertEqual(complete(config, digest, [1], "source stays read-only"), 1)

            self.assertEqual(source_pdf.read_bytes(), source_before)
            self.assertEqual(source_pdf.stat().st_mtime_ns, modified_before)
            self.assertEqual(
                sorted(path.name for path in source_pdf.parent.iterdir()),
                siblings_before,
            )


if __name__ == "__main__":
    unittest.main()
