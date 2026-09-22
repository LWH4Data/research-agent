from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.state import LibraryState, SCHEMA_VERSION, StateBusyError


def make_project(path: Path) -> Path:
    path.mkdir()
    (path / ".research-agent-root").write_text(
        PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
    )
    return path.resolve()


class ConversationOperationJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = make_project(Path(self.temporary.name) / "agent")
        self.database = self.project / ".research-store" / "library.sqlite"

    @staticmethod
    def target_record(*, revision: int = 2) -> dict[str, object]:
        return {
            "conversation_id": "conversation-1",
            "output_path": "knowledge/conversations/conversation-1.md",
            "title": "광소자 메모",
            "scope": "current-topic",
            "created_at": "2026-09-20T10:00:00+09:00",
            "updated_at": "2026-09-21T10:00:00+09:00",
            "revision": revision,
            "tags": json.dumps(["광소자"], ensure_ascii=False),
            "aliases": json.dumps(["optical device"], ensure_ascii=False),
        }

    def prepare(
        self,
        state: LibraryState,
        *,
        operation_id: str = "operation-1",
        operation: str = "update",
        target_markdown: bytes | str | None = "# 목표\n\n정확한 원문\n",
    ) -> dict[str, object]:
        base_record = self.target_record(revision=1)
        target_record = self.target_record(revision=2)
        return state.prepare_conversation_operation(
            operation_id=operation_id,
            operation=operation,
            conversation_id="conversation-1",
            output_path="knowledge/conversations/conversation-1.md",
            expected_revision=1,
            base_record=base_record,
            target_record=None if operation == "delete" else target_record,
            base_markdown_sha256="a" * 64,
            target_markdown=None if operation == "delete" else target_markdown,
        )

    def test_new_store_uses_current_singleton_journals_and_secure_delete(self) -> None:
        with LibraryState(self.database, self.project) as state:
            self.assertEqual(
                state.get_metadata("schema_version"), str(SCHEMA_VERSION)
            )
            self.assertEqual(
                state.connection.execute("PRAGMA secure_delete").fetchone()[0],
                1,
            )
            self.assertEqual(
                state.connection.execute("PRAGMA busy_timeout").fetchone()[0],
                3_000,
            )
            columns = {
                row["name"]
                for row in state.connection.execute(
                    "PRAGMA table_info(conversation_operations)"
                )
            }
            self.assertIn("target_markdown", columns)
            self.assertIn("base_record_json", columns)
            run_columns = {
                row["name"]
                for row in state.connection.execute(
                    "PRAGMA table_info(library_runs)"
                )
            }
            self.assertTrue({"run_id", "current", "total"} <= run_columns)
            document_operation_columns = {
                row["name"]
                for row in state.connection.execute(
                    "PRAGMA table_info(document_operations)"
                )
            }
            self.assertIn("target_markdown", document_operation_columns)
            self.assertIn("target_reviews_json", document_operation_columns)

            with self.assertRaises(sqlite3.IntegrityError):
                state.connection.execute(
                    """
                    INSERT INTO conversation_operations(
                        singleton, operation_id, operation_type,
                        conversation_id, output_path, prepared_at
                    ) VALUES(2, 'invalid', 'delete', 'id', 'path', 'now')
                    """
                )
            state.connection.rollback()

    def test_prepare_is_durable_and_get_decodes_json_and_utf8_bytes(self) -> None:
        with LibraryState(self.database, self.project) as state:
            prepared = self.prepare(state)
            expected_bytes = "# 목표\n\n정확한 원문\n".encode()
            self.assertEqual(prepared["operation"], "update")
            self.assertEqual(prepared["base_record"]["revision"], 1)
            self.assertEqual(prepared["target_record"]["revision"], 2)
            self.assertEqual(prepared["target_markdown"], expected_bytes)
            self.assertEqual(
                prepared["target_markdown_sha256"],
                hashlib.sha256(expected_bytes).hexdigest(),
            )
            self.assertNotIn("singleton", prepared)
            self.assertNotIn("base_record_json", prepared)

            # prepare_conversation_operation() commits before returning, so a
            # separate connection can recover it while this context is open.
            with sqlite3.connect(self.database) as observer:
                stored = observer.execute(
                    """
                    SELECT operation_id, typeof(target_markdown)
                    FROM conversation_operations
                    """
                ).fetchone()
            self.assertEqual(stored, ("operation-1", "blob"))

        with LibraryState(self.database, self.project, read_only=True) as state:
            recovered = state.get_pending_conversation_operation()
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertEqual(recovered["target_markdown"], expected_bytes)

    def test_prepare_reuses_active_immediate_transaction_as_recovery_boundary(
        self,
    ) -> None:
        with LibraryState(self.database, self.project) as state:
            state.begin_immediate()
            self.assertTrue(state.connection.in_transaction)
            self.prepare(state)
            self.assertFalse(state.connection.in_transaction)

            # The prepare commit is visible before any file mutation/final row
            # transaction begins, even when validation opened the transaction.
            with sqlite3.connect(self.database) as observer:
                operation_id = observer.execute(
                    "SELECT operation_id FROM conversation_operations"
                ).fetchone()[0]
            self.assertEqual(operation_id, "operation-1")

    def test_prepare_rejects_a_second_operation_without_replacing_first(self) -> None:
        with LibraryState(self.database, self.project) as state:
            self.prepare(state, operation_id="first")
            with self.assertRaisesRegex(RuntimeError, "완료되지 않은 대화 작업"):
                self.prepare(state, operation_id="second")
            pending = state.get_pending_conversation_operation()
            self.assertIsNotNone(pending)
            assert pending is not None
            self.assertEqual(pending["operation_id"], "first")

    def test_prepare_rejects_mismatched_target_hash_without_writing(self) -> None:
        with LibraryState(self.database, self.project) as state:
            with self.assertRaisesRegex(ValueError, "일치하지 않습니다"):
                state.prepare_conversation_operation(
                    operation_id="operation-1",
                    operation="save",
                    conversation_id="conversation-1",
                    output_path="knowledge/conversations/conversation-1.md",
                    expected_revision=None,
                    base_record=None,
                    target_record=self.target_record(revision=1),
                    base_markdown_sha256=None,
                    target_markdown=b"target",
                    target_markdown_sha256="0" * 64,
                )
            self.assertIsNone(state.get_pending_conversation_operation())

    def test_finish_and_row_update_commit_as_one_transaction(self) -> None:
        with LibraryState(self.database, self.project) as state:
            base = self.target_record(revision=1)
            state.register_conversation(
                conversation_id=str(base["conversation_id"]),
                output_path=str(base["output_path"]),
                title=str(base["title"]),
                scope=str(base["scope"]),
                created_at=str(base["created_at"]),
                updated_at=str(base["updated_at"]),
                revision=1,
                tags=["광소자"],
                aliases=["optical device"],
            )
            state.commit()
            self.prepare(state)
            state.update_conversation(
                "conversation-1",
                title="수정된 제목",
                updated_at="2026-09-21T11:00:00+09:00",
                revision=2,
                expected_revision=1,
                tags=["수정"],
                aliases=["updated"],
            )
            state.finish_conversation_operation("operation-1")

            # Neither half is visible before the shared transaction commits.
            with sqlite3.connect(self.database) as observer:
                revision = observer.execute(
                    "SELECT revision FROM conversations WHERE conversation_id = ?",
                    ("conversation-1",),
                ).fetchone()[0]
                pending_count = observer.execute(
                    "SELECT COUNT(*) FROM conversation_operations"
                ).fetchone()[0]
            self.assertEqual(revision, 1)
            self.assertEqual(pending_count, 1)

        with sqlite3.connect(self.database) as observer:
            revision = observer.execute(
                "SELECT revision FROM conversations WHERE conversation_id = ?",
                ("conversation-1",),
            ).fetchone()[0]
            pending_count = observer.execute(
                "SELECT COUNT(*) FROM conversation_operations"
            ).fetchone()[0]
        self.assertEqual(revision, 2)
        self.assertEqual(pending_count, 0)

    def test_failed_final_transaction_keeps_base_row_and_durable_journal(self) -> None:
        with LibraryState(self.database, self.project) as state:
            base = self.target_record(revision=1)
            state.register_conversation(
                conversation_id="conversation-1",
                output_path=str(base["output_path"]),
                title=str(base["title"]),
                scope=str(base["scope"]),
                created_at=str(base["created_at"]),
                updated_at=str(base["updated_at"]),
                revision=1,
                tags=[],
                aliases=[],
            )
        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            with LibraryState(self.database, self.project) as state:
                self.prepare(state)
                state.update_conversation(
                    "conversation-1",
                    title="수정된 제목",
                    updated_at="2026-09-21T11:00:00+09:00",
                    revision=2,
                    expected_revision=1,
                    tags=[],
                    aliases=[],
                )
                state.finish_conversation_operation("operation-1")
                raise RuntimeError("simulated crash")

        with LibraryState(self.database, self.project, read_only=True) as state:
            self.assertEqual(state.get_conversation("conversation-1")["revision"], 1)
            pending = state.get_pending_conversation_operation()
            self.assertIsNotNone(pending)

    def test_finish_requires_exact_operation_id_and_does_not_commit(self) -> None:
        with LibraryState(self.database, self.project) as state:
            self.prepare(state)
            with self.assertRaisesRegex(ValueError, "ID가 현재 작업과 다릅니다"):
                state.finish_conversation_operation("wrong-operation")
            self.assertIsNotNone(state.get_pending_conversation_operation())
            state.clear_pending_conversation_operation("operation-1")
            state.connection.rollback()
            self.assertIsNotNone(state.get_pending_conversation_operation())

    def test_writer_migrates_v2_and_read_only_validates_journal_table(self) -> None:
        self.database.parent.mkdir(parents=True)
        with sqlite3.connect(self.database) as database:
            database.executescript(
                """
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT INTO metadata(key, value) VALUES('schema_version', '2');
                CREATE TABLE conversations (
                    conversation_id TEXT PRIMARY KEY,
                    output_path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    tags TEXT NOT NULL,
                    aliases TEXT NOT NULL
                );
                """
            )

        with LibraryState(self.database, self.project) as state:
            self.assertEqual(
                state.get_metadata("schema_version"), str(SCHEMA_VERSION)
            )
            self.assertIsNone(state.get_pending_conversation_operation())
        with LibraryState(self.database, self.project, read_only=True):
            pass

        with sqlite3.connect(self.database) as database:
            database.execute("DROP TABLE conversation_operations")
        with self.assertRaisesRegex(RuntimeError, "대화 작업 기록 구조"):
            LibraryState(self.database, self.project, read_only=True)

    def test_writer_lock_timeout_has_a_clean_domain_error(self) -> None:
        with LibraryState(self.database, self.project):
            pass
        with patch("research_store.state.BUSY_TIMEOUT_MS", 10):
            state = LibraryState(self.database, self.project)
            self.addCleanup(state.connection.close)
            locker = sqlite3.connect(self.database)
            self.addCleanup(locker.close)
            locker.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(StateBusyError, "다른 작업에서 사용 중"):
                state.begin_immediate()
            locker.rollback()


if __name__ == "__main__":
    unittest.main()
