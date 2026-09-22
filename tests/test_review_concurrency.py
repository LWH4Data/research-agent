from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import research_store.sync as sync_module
from research_store.sync import ConversionResult, complete_reviews, sync_library

from test_review_notes import (
    DOCUMENT_KEY,
    MODEL,
    make_review_store,
    review_rows,
)


class ReviewConcurrencyTests(unittest.TestCase):
    def test_concurrent_page_completions_preserve_both_blocks_and_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1, 2))
            start = threading.Barrier(3)

            def finish_page(page: int) -> int:
                start.wait(timeout=5)
                return complete_reviews(
                    config,
                    DOCUMENT_KEY,
                    [page],
                    expected_sha256=digest,
                    status="verified",
                    reviewer_model=MODEL,
                    notes=f"database note {page}",
                    visual_notes=f"visual note {page}",
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(finish_page, page) for page in (1, 2)]
                start.wait(timeout=5)
                updated = [future.result(timeout=10) for future in futures]

            self.assertEqual(updated, [1, 1])
            content = markdown.read_text(encoding="utf-8")
            for page in (1, 2):
                self.assertEqual(
                    content.count(f"<!-- visual-review-begin: {page} -->"), 1
                )
                self.assertEqual(
                    content.count(f"<!-- visual-review-pages: {page} -->"), 1
                )
                self.assertEqual(
                    content.count(f"<!-- visual-review-end: {page} -->"), 1
                )
                self.assertIn(f"visual note {page}", content)

            with sqlite3.connect(config.state) as database:
                rows = database.execute(
                    """
                    SELECT page_number, status, reviewer_model, notes
                    FROM page_reviews
                    WHERE document_key = ?
                    ORDER BY page_number
                    """,
                    (DOCUMENT_KEY,),
                ).fetchall()
            self.assertEqual(
                rows,
                [
                    (1, "verified", MODEL, "database note 1"),
                    (2, "verified", MODEL, "database note 2"),
                ],
            )

    def test_failed_review_restore_cannot_erase_concurrent_page_completion(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1, 2))
            real_commit = sync_module.LibraryState.commit
            failing_thread_id: list[int] = []
            failed_commit_rolled_back = threading.Event()
            release_failed_commit = threading.Event()
            second_review_started = threading.Event()
            second_review_finished = threading.Event()

            def controlled_commit(state: sync_module.LibraryState) -> None:
                if (
                    failing_thread_id
                    and threading.get_ident() == failing_thread_id[0]
                    and not failed_commit_rolled_back.is_set()
                ):
                    state.connection.rollback()
                    failed_commit_rolled_back.set()
                    if not release_failed_commit.wait(timeout=5):
                        raise RuntimeError("test did not release the failed commit")
                    raise OSError("forced commit failure")
                real_commit(state)

            def fail_page_one() -> int:
                failing_thread_id.append(threading.get_ident())
                return complete_reviews(
                    config,
                    DOCUMENT_KEY,
                    [1],
                    expected_sha256=digest,
                    status="verified",
                    reviewer_model=MODEL,
                    notes="failed database note",
                    visual_notes="failed visual note",
                )

            def finish_page_two() -> int:
                second_review_started.set()
                try:
                    return complete_reviews(
                        config,
                        DOCUMENT_KEY,
                        [2],
                        expected_sha256=digest,
                        status="verified",
                        reviewer_model=MODEL,
                        notes="page two database note",
                        visual_notes="page two visual note",
                    )
                finally:
                    second_review_finished.set()

            with patch(
                "research_store.sync.LibraryState.commit",
                autospec=True,
                side_effect=controlled_commit,
            ), ThreadPoolExecutor(max_workers=2) as executor:
                failed_future = executor.submit(fail_page_one)
                self.assertTrue(failed_commit_rolled_back.wait(timeout=5))
                second_future = executor.submit(finish_page_two)
                try:
                    self.assertTrue(second_review_started.wait(timeout=5))
                    self.assertFalse(
                        second_review_finished.wait(timeout=0.25),
                        "second review entered while failed Markdown was restoring",
                    )
                finally:
                    release_failed_commit.set()

                with self.assertRaisesRegex(OSError, "forced commit failure"):
                    failed_future.result(timeout=5)
                self.assertEqual(second_future.result(timeout=5), 1)

            content = markdown.read_text(encoding="utf-8")
            self.assertNotIn("failed visual note", content)
            self.assertNotIn("<!-- visual-review-begin: 1 -->", content)
            self.assertIn("page two visual note", content)
            self.assertEqual(content.count("<!-- visual-review-begin: 2 -->"), 1)
            self.assertEqual(
                [(row[0], row[1], row[4]) for row in review_rows(config)],
                [
                    (1, "pending", None),
                    (2, "verified", "page two database note"),
                ],
            )

    def test_sync_commit_failure_restores_existing_review_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            complete_reviews(
                config,
                DOCUMENT_KEY,
                [1],
                expected_sha256=digest,
                status="verified",
                reviewer_model=MODEL,
                notes="old database note",
                visual_notes="old visual note",
            )
            markdown_before = markdown.read_bytes()
            rows_before = review_rows(config)
            with sqlite3.connect(config.state) as database:
                database.execute(
                    "UPDATE documents SET parser_version = 'force-reconversion'"
                )

            real_commit = sync_module.LibraryState.commit
            failed_once = False

            def fail_target_commit(state: sync_module.LibraryState) -> None:
                nonlocal failed_once
                parser_row = state.connection.execute(
                    "SELECT parser_version FROM documents WHERE document_key = ?",
                    (DOCUMENT_KEY,),
                ).fetchone()
                pending_journal = state.connection.execute(
                    "SELECT operation_id FROM document_operations"
                ).fetchone()
                if (
                    not failed_once
                    and parser_row is not None
                    and parser_row[0] == sync_module.PARSER_VERSION
                    and pending_journal is None
                ):
                    failed_once = True
                    state.connection.rollback()
                    raise OSError("forced sync commit failure")
                real_commit(state)

            with patch(
                "research_store.sync.LibraryState.commit",
                autospec=True,
                side_effect=fail_target_commit,
            ):
                result = sync_library(
                    config,
                    lambda _: ConversionResult(
                        "<!-- page: 1 -->\n\nReconverted page\n",
                        {1: ["table-caption"]},
                    ),
                )

            self.assertEqual(result.failed, 1)
            self.assertTrue(failed_once)
            self.assertEqual(markdown.read_bytes(), markdown_before)
            self.assertEqual(review_rows(config), rows_before)

    def test_sync_markdown_write_holds_lock_until_review_rows_are_replaced(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, digest, markdown = make_review_store(Path(directory), (1,))
            with sqlite3.connect(config.state) as database:
                database.execute(
                    "UPDATE documents SET parser_version = 'force-reconversion'"
                )

            real_atomic_text = sync_module.atomic_text
            sync_thread_id: list[int] = []
            sync_markdown_written = threading.Event()
            release_sync_write = threading.Event()
            review_started = threading.Event()
            review_finished = threading.Event()

            def converter(_: Path) -> ConversionResult:
                sync_thread_id.append(threading.get_ident())
                return ConversionResult(
                    "<!-- page: 1 -->\n\nPage 1\n",
                    {1: ["table-caption"]},
                )

            def paused_atomic_text(path: Path, text: str, root: Path) -> None:
                real_atomic_text(path, text, root)
                if (
                    sync_thread_id
                    and threading.get_ident() == sync_thread_id[0]
                    and not sync_markdown_written.is_set()
                ):
                    sync_markdown_written.set()
                    if not release_sync_write.wait(timeout=5):
                        raise RuntimeError("test did not release the sync write")

            def finish_review() -> int:
                review_started.set()
                try:
                    return complete_reviews(
                        config,
                        DOCUMENT_KEY,
                        [1],
                        expected_sha256=digest,
                        status="verified",
                        reviewer_model=MODEL,
                        notes="database note",
                        visual_notes="visual note",
                    )
                finally:
                    review_finished.set()

            with patch(
                "research_store.operations.atomic_text",
                side_effect=paused_atomic_text,
            ), ThreadPoolExecutor(max_workers=2) as executor:
                sync_future = executor.submit(sync_library, config, converter)
                self.assertTrue(
                    sync_markdown_written.wait(timeout=5),
                    "sync did not reach its Markdown write",
                )
                review_future = executor.submit(finish_review)
                try:
                    self.assertTrue(review_started.wait(timeout=5))
                    self.assertFalse(
                        review_finished.wait(timeout=0.25),
                        "review bypassed the sync writer transaction",
                    )
                finally:
                    release_sync_write.set()

                sync_result = sync_future.result(timeout=5)
                review_result = review_future.result(timeout=5)

            self.assertEqual(sync_result.converted, 1)
            self.assertEqual(review_result, 1)
            content = markdown.read_text(encoding="utf-8")
            self.assertEqual(content.count("<!-- visual-review-begin: 1 -->"), 1)
            self.assertIn("visual note", content)
            self.assertIn("visual_review_pending_pages: []", content)
            with sqlite3.connect(config.state) as database:
                row = database.execute(
                    """
                    SELECT status, reviewer_model, notes
                    FROM page_reviews
                    WHERE document_key = ? AND page_number = 1
                    """,
                    (DOCUMENT_KEY,),
                ).fetchone()
            self.assertEqual(row, ("verified", MODEL, "database note"))


if __name__ == "__main__":
    unittest.main()
