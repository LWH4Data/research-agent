from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from .safety import ensure_owned_directory, reject_linked_file, require_owned_path


SCHEMA_VERSION = 4
BUSY_TIMEOUT_MS = 3_000

RUN_KINDS = {"sync"}
RUN_STATUSES = {
    "running",
    "interrupted",
    "completed",
    "completed_with_errors",
    "failed",
}


class StateBusyError(RuntimeError):
    """Raised when another process holds the SQLite writer lock too long."""


def _is_lock_error(error: sqlite3.OperationalError) -> bool:
    code = getattr(error, "sqlite_errorcode", None)
    if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        return True
    message = str(error).casefold()
    return "database is locked" in message or "database table is locked" in message


def _state_busy_error() -> StateBusyError:
    return StateBusyError(
        "연구 저장소가 다른 작업에서 사용 중입니다. 잠시 후 다시 시도하세요."
    )


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_review_pages(pages: list[int]) -> list[int]:
    """Return a stable, non-empty set of positive review page numbers."""

    try:
        values = list(pages)
    except TypeError as error:
        raise ValueError("검토할 페이지 목록이 필요합니다") from error
    if not values:
        raise ValueError("검토할 페이지를 하나 이상 지정해야 합니다")
    for page in values:
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValueError("검토 페이지 번호는 1 이상의 정수여야 합니다")
    return sorted(set(values))


def validate_reviewer_model(reviewer_model: str) -> str:
    """Validate a model identifier before it reaches SQLite or Markdown."""

    if not isinstance(reviewer_model, str):
        raise ValueError("검토 모델 이름은 문자열이어야 합니다")
    if not 1 <= len(reviewer_model) <= 128:
        raise ValueError("검토 모델 이름은 1자 이상 128자 이하여야 합니다")
    if not reviewer_model[0].isalnum() or not all(
        character.isascii()
        and (character.isalnum() or character in "-._:/+")
        for character in reviewer_model
    ):
        raise ValueError("검토 모델 이름에 안전하지 않은 문자가 있습니다")
    return reviewer_model


def _validate_reviewed_at(reviewed_at: str) -> str:
    if not isinstance(reviewed_at, str) or not reviewed_at or len(reviewed_at) > 64:
        raise ValueError("검토 시각이 올바르지 않습니다")
    try:
        parsed = datetime.fromisoformat(reviewed_at)
    except ValueError as error:
        raise ValueError("검토 시각이 ISO 8601 형식이 아닙니다") from error
    if parsed.tzinfo is None:
        raise ValueError("검토 시각에는 시간대가 필요합니다")
    return reviewed_at


class LibraryState(AbstractContextManager["LibraryState"]):
    """SQLite-backed sync ledger. Source documents are never opened for writing."""

    def __init__(self, path: Path, root: Path, *, read_only: bool = False):
        self.root = root
        self.read_only = read_only
        self.path = require_owned_path(path, root, label="SQLite 저장 경로")
        if read_only:
            if not self.path.is_file():
                raise ValueError(f"SQLite 저장 파일을 찾을 수 없습니다: {self.path}")
        else:
            ensure_owned_directory(self.path.parent, root, label="SQLite 저장 폴더")
        self.path = reject_linked_file(self.path, root, label="SQLite 저장 경로")
        for suffix in ("-journal", "-wal", "-shm"):
            reject_linked_file(
                Path(f"{self.path}{suffix}"),
                root,
                label="SQLite 보조 파일 경로",
            )
        if read_only:
            self.connection = sqlite3.connect(
                f"{self.path.as_uri()}?mode=ro",
                uri=True,
                timeout=BUSY_TIMEOUT_MS / 1_000,
            )
        else:
            self.connection = sqlite3.connect(
                self.path,
                timeout=BUSY_TIMEOUT_MS / 1_000,
            )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        # Keep SQLite's sort/index spill files in memory so every persistent
        # write remains beside the project-owned database.
        self.connection.execute("PRAGMA temp_store = MEMORY")
        self.connection.execute("PRAGMA foreign_keys = ON")
        if read_only:
            self.connection.execute("PRAGMA query_only = ON")
        else:
            # The operation journal can briefly contain captured conversation
            # text. Overwrite deleted SQLite cells instead of leaving those
            # bytes on the freelist after a journal entry is finished.
            self.connection.execute("PRAGMA secure_delete = ON")
            # A prepare commit is the recovery boundary before a Markdown file
            # is changed, so use SQLite's durable rollback-journal setting.
            self.connection.execute("PRAGMA synchronous = FULL")
        try:
            if read_only:
                self._validate_read_only_schema()
            else:
                self._initialize()
        except sqlite3.OperationalError as error:
            self.connection.close()
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise
        except BaseException:
            self.connection.close()
            raise

    def _validate_read_only_schema(self) -> None:
        try:
            version_row = self.connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
        except sqlite3.DatabaseError as error:
            raise RuntimeError("SQLite 저장소 구조를 읽을 수 없습니다") from error
        if version_row is None:
            raise RuntimeError("SQLite 스키마 버전이 없습니다")
        try:
            stored_version = int(version_row["value"])
        except (TypeError, ValueError) as error:
            raise RuntimeError("SQLite 스키마 버전이 올바르지 않습니다") from error
        if stored_version > SCHEMA_VERSION:
            raise RuntimeError(
                "현재 프로그램보다 새로운 SQLite 스키마입니다: "
                f"{stored_version} > {SCHEMA_VERSION}"
            )
        if stored_version < SCHEMA_VERSION:
            raise RuntimeError(
                "SQLite 저장소를 먼저 최신 형식으로 갱신해야 합니다: "
                f"{stored_version} < {SCHEMA_VERSION}"
            )
        try:
            conversation_columns = {
                str(row["name"])
                for row in self.connection.execute(
                    "PRAGMA table_info(conversations)"
                )
            }
        except sqlite3.DatabaseError as error:
            raise RuntimeError("SQLite 대화 저장소 구조를 읽을 수 없습니다") from error
        required_columns = {
            "conversation_id",
            "output_path",
            "title",
            "scope",
            "created_at",
            "updated_at",
            "revision",
            "tags",
            "aliases",
        }
        if not required_columns.issubset(conversation_columns):
            raise RuntimeError("SQLite 대화 저장소 구조가 올바르지 않습니다")
        try:
            operation_columns = {
                str(row["name"])
                for row in self.connection.execute(
                    "PRAGMA table_info(conversation_operations)"
                )
            }
        except sqlite3.DatabaseError as error:
            raise RuntimeError("SQLite 대화 작업 기록 구조를 읽을 수 없습니다") from error
        required_operation_columns = {
            "singleton",
            "operation_id",
            "operation_type",
            "conversation_id",
            "output_path",
            "expected_revision",
            "base_record_json",
            "target_record_json",
            "base_markdown_sha256",
            "target_markdown",
            "target_markdown_sha256",
            "prepared_at",
        }
        if not required_operation_columns.issubset(operation_columns):
            raise RuntimeError("SQLite 대화 작업 기록 구조가 올바르지 않습니다")
        try:
            run_columns = {
                str(row["name"])
                for row in self.connection.execute(
                    "PRAGMA table_info(library_runs)"
                )
            }
        except sqlite3.DatabaseError as error:
            raise RuntimeError("SQLite 작업 진행 기록 구조를 읽을 수 없습니다") from error
        required_run_columns = {
            "run_id",
            "kind",
            "status",
            "phase",
            "current",
            "total",
            "counters_json",
            "last_item",
            "started_at",
            "updated_at",
            "finished_at",
            "error",
        }
        if not required_run_columns.issubset(run_columns):
            raise RuntimeError("SQLite 작업 진행 기록 구조가 올바르지 않습니다")
        try:
            document_operation_columns = {
                str(row["name"])
                for row in self.connection.execute(
                    "PRAGMA table_info(document_operations)"
                )
            }
        except sqlite3.DatabaseError as error:
            raise RuntimeError("SQLite 문서 복구 기록 구조를 읽을 수 없습니다") from error
        required_document_operation_columns = {
            "singleton",
            "operation_id",
            "operation_type",
            "document_key",
            "output_path",
            "base_document_json",
            "target_document_json",
            "base_reviews_json",
            "target_reviews_json",
            "base_markdown_sha256",
            "target_markdown",
            "target_markdown_sha256",
            "prepared_at",
        }
        if not required_document_operation_columns.issubset(
            document_operation_columns
        ):
            raise RuntimeError("SQLite 문서 복구 기록 구조가 올바르지 않습니다")

    def _initialize(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        version_row = self.connection.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        if version_row is not None:
            try:
                stored_version = int(version_row["value"])
            except (TypeError, ValueError) as error:
                raise RuntimeError("SQLite 스키마 버전이 올바르지 않습니다") from error
            if stored_version > SCHEMA_VERSION:
                raise RuntimeError(
                    "현재 프로그램보다 새로운 SQLite 스키마입니다: "
                    f"{stored_version} > {SCHEMA_VERSION}"
                )

        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_key TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                output_path TEXT NOT NULL,
                size INTEGER NOT NULL,
                modified_ns INTEGER NOT NULL,
                sha256 TEXT,
                parser_version TEXT,
                present INTEGER NOT NULL DEFAULT 1,
                converted_at TEXT,
                checked_at TEXT,
                missing_since TEXT,
                error TEXT
            );

            CREATE INDEX IF NOT EXISTS documents_sha256
                ON documents(sha256);
            CREATE INDEX IF NOT EXISTS documents_present
                ON documents(present);

            CREATE TABLE IF NOT EXISTS page_reviews (
                document_key TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                reasons TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_at TEXT,
                reviewer_model TEXT,
                notes TEXT,
                PRIMARY KEY(document_key, page_number),
                FOREIGN KEY(document_key)
                    REFERENCES documents(document_key) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS conversations (
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

            CREATE TABLE IF NOT EXISTS conversation_operations (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                operation_id TEXT NOT NULL UNIQUE,
                operation_type TEXT NOT NULL CHECK(
                    operation_type IN ('save', 'update', 'delete')
                ),
                conversation_id TEXT NOT NULL,
                output_path TEXT NOT NULL,
                expected_revision INTEGER,
                base_record_json TEXT,
                target_record_json TEXT,
                base_markdown_sha256 TEXT,
                target_markdown BLOB,
                target_markdown_sha256 TEXT,
                prepared_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS library_runs (
                run_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL CHECK(kind IN ('sync')),
                status TEXT NOT NULL CHECK(status IN (
                    'running', 'interrupted', 'completed',
                    'completed_with_errors', 'failed'
                )),
                phase TEXT NOT NULL,
                current INTEGER NOT NULL CHECK(current >= 0),
                total INTEGER NOT NULL CHECK(total >= 0),
                counters_json TEXT NOT NULL,
                last_item TEXT,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT,
                error TEXT
            );

            CREATE INDEX IF NOT EXISTS library_runs_kind_started
                ON library_runs(kind, started_at DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS library_runs_one_active_kind
                ON library_runs(kind)
                WHERE status = 'running';

            CREATE TABLE IF NOT EXISTS document_operations (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                operation_id TEXT NOT NULL UNIQUE,
                operation_type TEXT NOT NULL CHECK(
                    operation_type IN ('sync-document', 'review-page')
                ),
                document_key TEXT NOT NULL,
                output_path TEXT NOT NULL,
                base_document_json TEXT,
                target_document_json TEXT NOT NULL,
                base_reviews_json TEXT NOT NULL,
                target_reviews_json TEXT NOT NULL,
                base_markdown_sha256 TEXT,
                target_markdown BLOB NOT NULL,
                target_markdown_sha256 TEXT NOT NULL,
                prepared_at TEXT NOT NULL
            );
            """
        )
        conversation_columns = {
            str(row["name"])
            for row in self.connection.execute("PRAGMA table_info(conversations)")
        }
        if "updated_at" not in conversation_columns:
            self.connection.execute(
                "ALTER TABLE conversations ADD COLUMN updated_at TEXT"
            )
        if "revision" not in conversation_columns:
            self.connection.execute(
                "ALTER TABLE conversations "
                "ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"
            )
        self.connection.execute(
            """
            UPDATE conversations
            SET updated_at = created_at
            WHERE updated_at IS NULL OR updated_at = ''
            """
        )
        self.connection.execute(
            "UPDATE conversations SET revision = 1 WHERE revision < 1"
        )
        self.set_metadata("schema_version", str(SCHEMA_VERSION))
        self.connection.commit()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.read_only:
            self.connection.close()
            return
        try:
            if exc_type is None:
                self.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()

    def _require_writer(self) -> None:
        if self.read_only:
            raise RuntimeError("읽기 전용 SQLite 저장소는 수정할 수 없습니다")

    def set_metadata(self, key: str, value: str) -> None:
        self._require_writer()
        self.connection.execute(
            """
            INSERT INTO metadata(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def get_metadata(self, key: str) -> str | None:
        row = self.connection.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row["value"])

    @staticmethod
    def _encode_run_counters(counters: dict[str, int]) -> str:
        if not isinstance(counters, dict):
            raise ValueError("작업 진행 집계는 JSON 객체여야 합니다")
        normalized: dict[str, int] = {}
        for key, value in counters.items():
            if not isinstance(key, str) or not key:
                raise ValueError("작업 진행 집계 이름이 올바르지 않습니다")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("작업 진행 집계 값은 0 이상의 정수여야 합니다")
            normalized[key] = value
        return json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def _decode_run(cls, row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        try:
            counters = json.loads(str(result.pop("counters_json")))
            # Reuse the strict encoder for validation without changing the
            # stored representation returned to callers.
            cls._encode_run_counters(counters)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("SQLite 작업 진행 집계가 손상되었습니다") from error
        result["counters"] = counters
        return result

    def begin_library_run(
        self,
        *,
        kind: str,
        phase: str,
        total: int,
        counters: dict[str, int],
    ) -> dict[str, Any]:
        """Durably start one run and mark a stale run of the same kind interrupted."""

        self._require_writer()
        if kind not in RUN_KINDS:
            raise ValueError(f"지원하지 않는 작업 종류입니다: {kind}")
        if not isinstance(phase, str) or not phase:
            raise ValueError("작업 단계가 필요합니다")
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise ValueError("전체 작업 수는 0 이상의 정수여야 합니다")
        counters_json = self._encode_run_counters(counters)
        run_id = uuid.uuid4().hex
        timestamp = now()
        try:
            self.begin_immediate()
            stale_rows = self.connection.execute(
                """
                SELECT * FROM library_runs
                WHERE kind = ? AND status = 'running'
                ORDER BY started_at, run_id
                """,
                (kind,),
            ).fetchall()
            self.connection.execute(
                """
                UPDATE library_runs
                SET status = 'interrupted', updated_at = ?, finished_at = ?,
                    error = COALESCE(error, '이전 작업이 완료되기 전에 중단되었습니다')
                WHERE kind = ? AND status = 'running'
                """,
                (timestamp, timestamp, kind),
            )
            self.connection.execute(
                """
                INSERT INTO library_runs(
                    run_id, kind, status, phase, current, total,
                    counters_json, last_item, started_at, updated_at,
                    finished_at, error
                ) VALUES(?, ?, 'running', ?, 0, ?, ?, NULL, ?, ?, NULL, NULL)
                """,
                (run_id, kind, phase, total, counters_json, timestamp, timestamp),
            )
            self.commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        return {
            "run_id": run_id,
            "interrupted": [self._decode_run(row) for row in stale_rows],
        }

    def update_library_run(
        self,
        run_id: str,
        *,
        phase: str,
        current: int,
        total: int,
        counters: dict[str, int],
        last_item: str | None = None,
    ) -> None:
        """Update progress inside the caller's transaction without committing it."""

        self._require_writer()
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("작업 ID가 필요합니다")
        if not isinstance(phase, str) or not phase:
            raise ValueError("작업 단계가 필요합니다")
        for label, value in (("완료 작업 수", current), ("전체 작업 수", total)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{label}는 0 이상의 정수여야 합니다")
        if total and current > total:
            raise ValueError("완료 작업 수가 전체 작업 수보다 클 수 없습니다")
        if last_item is not None:
            if not isinstance(last_item, str) or len(last_item) > 512:
                raise ValueError("현재 작업 이름은 512자 이하여야 합니다")
        cursor = self.connection.execute(
            """
            UPDATE library_runs
            SET phase = ?, current = ?, total = ?, counters_json = ?,
                last_item = ?, updated_at = ?
            WHERE run_id = ? AND status = 'running'
            """,
            (
                phase,
                current,
                total,
                self._encode_run_counters(counters),
                last_item,
                now(),
                run_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"진행 중인 작업을 찾을 수 없습니다: {run_id}")

    def finish_library_run(
        self,
        run_id: str,
        *,
        status: str,
        phase: str,
        current: int,
        total: int,
        counters: dict[str, int],
        last_item: str | None = None,
        error: str | None = None,
    ) -> None:
        """Finish one run inside the caller's transaction without committing it."""

        if status not in RUN_STATUSES - {"running"}:
            raise ValueError(f"지원하지 않는 작업 완료 상태입니다: {status}")
        # Validate all common fields and ensure the row is still active.
        self.update_library_run(
            run_id,
            phase=phase,
            current=current,
            total=total,
            counters=counters,
            last_item=last_item,
        )
        timestamp = now()
        cursor = self.connection.execute(
            """
            UPDATE library_runs
            SET status = ?, updated_at = ?, finished_at = ?, error = ?
            WHERE run_id = ? AND status = 'running'
            """,
            (status, timestamp, timestamp, error, run_id),
        )
        if cursor.rowcount != 1:  # pragma: no cover - update_library_run guards it.
            raise RuntimeError(f"작업 완료 상태를 저장하지 못했습니다: {run_id}")

    def latest_library_run(self, kind: str = "sync") -> dict[str, Any] | None:
        if kind not in RUN_KINDS:
            raise ValueError(f"지원하지 않는 작업 종류입니다: {kind}")
        row = self.connection.execute(
            """
            SELECT * FROM library_runs
            WHERE kind = ?
            ORDER BY started_at DESC, rowid DESC
            LIMIT 1
            """,
            (kind,),
        ).fetchone()
        return None if row is None else self._decode_run(row)

    def commit(self) -> None:
        self._require_writer()
        try:
            self.connection.commit()
        except sqlite3.OperationalError as error:
            self.connection.rollback()
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise

    def begin_immediate(self) -> None:
        self._require_writer()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise

    @staticmethod
    def _record_json(
        record: dict[str, Any] | None, *, label: str
    ) -> str | None:
        if record is None:
            return None
        if not isinstance(record, dict):
            raise ValueError(f"{label}은 JSON 객체여야 합니다")
        try:
            return json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label}을 JSON으로 저장할 수 없습니다") from error

    @staticmethod
    def _validate_sha256(value: str | None, *, label: str) -> None:
        if value is None:
            return
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError(f"{label}은 소문자 SHA-256 값이어야 합니다")

    def prepare_conversation_operation(
        self,
        *,
        operation_id: str,
        operation: str,
        conversation_id: str,
        output_path: str,
        expected_revision: int | None,
        base_record: dict[str, Any] | None,
        target_record: dict[str, Any] | None,
        base_markdown_sha256: str | None,
        target_markdown: bytes | str | None,
        target_markdown_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Durably record one file/row operation before the file is changed.

        This method obtains the writer lock when the caller has not already
        started a transaction, and commits the singleton journal row before
        returning. The caller may then mutate the Markdown file. A later row
        mutation followed by :meth:`finish_conversation_operation` remains one
        SQLite transaction.
        """

        self._require_writer()
        if not operation_id or not isinstance(operation_id, str):
            raise ValueError("대화 작업 ID가 필요합니다")
        if operation not in {"save", "update", "delete"}:
            raise ValueError(f"지원하지 않는 대화 작업입니다: {operation}")
        if not conversation_id or not isinstance(conversation_id, str):
            raise ValueError("대화 ID가 필요합니다")
        if not output_path or not isinstance(output_path, str):
            raise ValueError("대화 Markdown 경로가 필요합니다")
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 1
        ):
            raise ValueError("expected_revision은 1 이상의 정수여야 합니다")

        base_json = self._record_json(base_record, label="기존 대화 레코드")
        target_json = self._record_json(target_record, label="목표 대화 레코드")
        self._validate_sha256(base_markdown_sha256, label="기존 Markdown 해시")

        if isinstance(target_markdown, str):
            target_bytes: bytes | None = target_markdown.encode("utf-8")
        elif isinstance(target_markdown, bytes) or target_markdown is None:
            target_bytes = target_markdown
        else:
            raise ValueError("목표 Markdown은 UTF-8 문자열 또는 바이트여야 합니다")
        computed_target_hash = (
            None
            if target_bytes is None
            else hashlib.sha256(target_bytes).hexdigest()
        )
        self._validate_sha256(target_markdown_sha256, label="목표 Markdown 해시")
        if (
            target_markdown_sha256 is not None
            and target_markdown_sha256 != computed_target_hash
        ):
            raise ValueError("목표 Markdown 내용과 SHA-256 값이 일치하지 않습니다")
        target_hash = target_markdown_sha256 or computed_target_hash

        if not self.connection.in_transaction:
            self.begin_immediate()
        try:
            pending = self.connection.execute(
                "SELECT operation_id FROM conversation_operations WHERE singleton = 1"
            ).fetchone()
            if pending is not None:
                raise RuntimeError(
                    "완료되지 않은 대화 작업이 있습니다: "
                    f"{pending['operation_id']}"
                )
            self.connection.execute(
                """
                INSERT INTO conversation_operations(
                    singleton, operation_id, operation_type, conversation_id,
                    output_path, expected_revision, base_record_json,
                    target_record_json, base_markdown_sha256, target_markdown,
                    target_markdown_sha256, prepared_at
                ) VALUES(1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    operation,
                    conversation_id,
                    output_path,
                    expected_revision,
                    base_json,
                    target_json,
                    base_markdown_sha256,
                    target_bytes,
                    target_hash,
                    now(),
                ),
            )
            self.commit()
        except sqlite3.OperationalError as error:
            if self.connection.in_transaction:
                self.connection.rollback()
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

        pending_operation = self.get_pending_conversation_operation()
        if pending_operation is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("준비한 대화 작업 기록을 다시 읽을 수 없습니다")
        return pending_operation

    def get_pending_conversation_operation(self) -> dict[str, Any] | None:
        try:
            row = self.connection.execute(
                "SELECT * FROM conversation_operations WHERE singleton = 1"
            ).fetchone()
        except sqlite3.OperationalError as error:
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise
        if row is None:
            return None

        result = dict(row)
        for column in ("base_record_json", "target_record_json"):
            raw = result.pop(column)
            key = column.removesuffix("_json")
            if raw is None:
                result[key] = None
                continue
            try:
                decoded = json.loads(str(raw))
            except (TypeError, ValueError) as error:
                raise RuntimeError("SQLite 대화 작업의 JSON 기록이 손상되었습니다") from error
            if not isinstance(decoded, dict):
                raise RuntimeError("SQLite 대화 작업의 JSON 기록이 올바르지 않습니다")
            result[key] = decoded

        target_markdown = result.get("target_markdown")
        if isinstance(target_markdown, memoryview):
            target_markdown = target_markdown.tobytes()
        elif target_markdown is not None and not isinstance(target_markdown, bytes):
            raise RuntimeError("SQLite 대화 작업의 Markdown 기록이 올바르지 않습니다")
        result["target_markdown"] = target_markdown

        try:
            self._validate_sha256(
                result.get("base_markdown_sha256"),
                label="기존 Markdown 해시",
            )
        except ValueError as error:
            raise RuntimeError(
                "SQLite 대화 작업의 기존 Markdown 해시가 손상되었습니다"
            ) from error
        expected_hash = result.get("target_markdown_sha256")
        actual_hash = (
            None
            if target_markdown is None
            else hashlib.sha256(target_markdown).hexdigest()
        )
        if expected_hash != actual_hash:
            raise RuntimeError("SQLite 대화 작업의 Markdown 기록이 손상되었습니다")

        result["operation"] = result.pop("operation_type")
        result.pop("singleton", None)
        return result

    def finish_conversation_operation(self, operation_id: str) -> None:
        """Delete the matching journal row without committing the transaction."""

        self._require_writer()
        try:
            row = self.connection.execute(
                "SELECT operation_id FROM conversation_operations WHERE singleton = 1"
            ).fetchone()
        except sqlite3.OperationalError as error:
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise
        if row is None:
            raise ValueError("완료할 대화 작업이 없습니다")
        if str(row["operation_id"]) != operation_id:
            raise ValueError(
                "완료하려는 대화 작업 ID가 현재 작업과 다릅니다: "
                f"expected={row['operation_id']}, received={operation_id}"
            )
        try:
            cursor = self.connection.execute(
                """
                DELETE FROM conversation_operations
                WHERE singleton = 1 AND operation_id = ?
                """,
                (operation_id,),
            )
        except sqlite3.OperationalError as error:
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise
        if cursor.rowcount != 1:  # pragma: no cover - guarded above
            raise RuntimeError("대화 작업 기록을 완료하지 못했습니다")

    def clear_pending_conversation_operation(self, operation_id: str) -> None:
        """Compatibility name for finishing a journal row without committing."""

        self.finish_conversation_operation(operation_id)

    @staticmethod
    def _json_payload(value: Any, *, label: str, expected: type) -> str:
        if not isinstance(value, expected):
            expected_name = "객체" if expected is dict else "목록"
            raise ValueError(f"{label}은 JSON {expected_name}이어야 합니다")
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label}을 JSON으로 저장할 수 없습니다") from error

    def prepare_document_operation(
        self,
        *,
        operation_id: str,
        operation: str,
        document_key: str,
        output_path: str,
        base_document: dict[str, Any] | None,
        target_document: dict[str, Any],
        base_reviews: list[dict[str, Any]],
        target_reviews: list[dict[str, Any]],
        base_markdown_sha256: str | None,
        target_markdown: bytes | str,
    ) -> dict[str, Any]:
        """Durably journal one generated Markdown/SQLite replacement."""

        self._require_writer()
        if operation not in {"sync-document", "review-page"}:
            raise ValueError(f"지원하지 않는 문서 작업입니다: {operation}")
        if not operation_id or not isinstance(operation_id, str):
            raise ValueError("문서 작업 ID가 필요합니다")
        if not document_key or not isinstance(document_key, str):
            raise ValueError("문서 키가 필요합니다")
        if not output_path or not isinstance(output_path, str):
            raise ValueError("문서 Markdown 경로가 필요합니다")
        if base_document is None:
            base_document_json = None
        else:
            base_document_json = self._json_payload(
                base_document, label="기존 문서 레코드", expected=dict
            )
        target_document_json = self._json_payload(
            target_document, label="목표 문서 레코드", expected=dict
        )
        base_reviews_json = self._json_payload(
            base_reviews, label="기존 페이지 검토 레코드", expected=list
        )
        target_reviews_json = self._json_payload(
            target_reviews, label="목표 페이지 검토 레코드", expected=list
        )
        self._validate_sha256(base_markdown_sha256, label="기존 Markdown 해시")
        if isinstance(target_markdown, str):
            target_bytes = target_markdown.encode("utf-8")
        elif isinstance(target_markdown, bytes):
            target_bytes = target_markdown
        else:
            raise ValueError("목표 Markdown은 UTF-8 문자열 또는 바이트여야 합니다")
        target_hash = hashlib.sha256(target_bytes).hexdigest()

        if not self.connection.in_transaction:
            self.begin_immediate()
        try:
            pending = self.connection.execute(
                "SELECT operation_id FROM document_operations WHERE singleton = 1"
            ).fetchone()
            if pending is not None:
                raise RuntimeError(
                    "완료되지 않은 문서 작업이 있습니다: "
                    f"{pending['operation_id']}"
                )
            self.connection.execute(
                """
                INSERT INTO document_operations(
                    singleton, operation_id, operation_type, document_key,
                    output_path, base_document_json, target_document_json,
                    base_reviews_json, target_reviews_json,
                    base_markdown_sha256, target_markdown,
                    target_markdown_sha256, prepared_at
                ) VALUES(1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    operation,
                    document_key,
                    output_path,
                    base_document_json,
                    target_document_json,
                    base_reviews_json,
                    target_reviews_json,
                    base_markdown_sha256,
                    target_bytes,
                    target_hash,
                    now(),
                ),
            )
            self.commit()
        except sqlite3.OperationalError as error:
            if self.connection.in_transaction:
                self.connection.rollback()
            if _is_lock_error(error):
                raise _state_busy_error() from error
            raise
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
        pending_operation = self.get_pending_document_operation()
        if pending_operation is None:  # pragma: no cover - defensive invariant.
            raise RuntimeError("준비한 문서 작업 기록을 다시 읽을 수 없습니다")
        return pending_operation

    def get_pending_document_operation(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM document_operations WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        for column, expected in (
            ("base_document_json", dict),
            ("target_document_json", dict),
            ("base_reviews_json", list),
            ("target_reviews_json", list),
        ):
            raw = result.pop(column)
            key = column.removesuffix("_json")
            if raw is None:
                if column != "base_document_json":
                    raise RuntimeError("SQLite 문서 복구 JSON 기록이 없습니다")
                result[key] = None
                continue
            try:
                decoded = json.loads(str(raw))
            except (TypeError, ValueError) as error:
                raise RuntimeError("SQLite 문서 복구 JSON 기록이 손상되었습니다") from error
            if not isinstance(decoded, expected):
                raise RuntimeError("SQLite 문서 복구 JSON 기록이 올바르지 않습니다")
            result[key] = decoded

        target_markdown = result.get("target_markdown")
        if isinstance(target_markdown, memoryview):
            target_markdown = target_markdown.tobytes()
        if not isinstance(target_markdown, bytes):
            raise RuntimeError("SQLite 문서 복구 Markdown 기록이 올바르지 않습니다")
        result["target_markdown"] = target_markdown
        try:
            self._validate_sha256(
                result.get("base_markdown_sha256"), label="기존 Markdown 해시"
            )
            self._validate_sha256(
                result.get("target_markdown_sha256"), label="목표 Markdown 해시"
            )
        except ValueError as error:
            raise RuntimeError("SQLite 문서 복구 해시가 손상되었습니다") from error
        if hashlib.sha256(target_markdown).hexdigest() != result.get(
            "target_markdown_sha256"
        ):
            raise RuntimeError("SQLite 문서 복구 Markdown 내용이 손상되었습니다")
        result["operation"] = result.pop("operation_type")
        result.pop("singleton", None)
        return result

    def finish_document_operation(self, operation_id: str) -> None:
        """Delete the matching journal row without committing the transaction."""

        self._require_writer()
        row = self.connection.execute(
            "SELECT operation_id FROM document_operations WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise ValueError("완료할 문서 작업이 없습니다")
        if str(row["operation_id"]) != operation_id:
            raise ValueError(
                "완료하려는 문서 작업 ID가 현재 작업과 다릅니다: "
                f"expected={row['operation_id']}, received={operation_id}"
            )
        cursor = self.connection.execute(
            """
            DELETE FROM document_operations
            WHERE singleton = 1 AND operation_id = ?
            """,
            (operation_id,),
        )
        if cursor.rowcount != 1:  # pragma: no cover - guarded above.
            raise RuntimeError("문서 작업 기록을 완료하지 못했습니다")

    def get_document(self, document_key: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM documents WHERE document_key = ?", (document_key,)
        ).fetchone()
        return None if row is None else dict(row)

    def document_reviews(self, document_key: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT document_key, page_number, reasons, status, reviewed_at,
                   reviewer_model, notes
            FROM page_reviews
            WHERE document_key = ?
            ORDER BY page_number
            """,
            (document_key,),
        ).fetchall()
        return [dict(row) for row in rows]

    def replace_review_records(
        self, document_key: str, reviews: list[dict[str, Any]]
    ) -> None:
        self.connection.execute(
            "DELETE FROM page_reviews WHERE document_key = ?", (document_key,)
        )
        columns = (
            "document_key",
            "page_number",
            "reasons",
            "status",
            "reviewed_at",
            "reviewer_model",
            "notes",
        )
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError("페이지 검토 레코드가 올바르지 않습니다")
            if str(review.get("document_key")) != document_key:
                raise ValueError("페이지 검토 레코드의 문서 키가 일치하지 않습니다")
            self.connection.execute(
                """
                INSERT INTO page_reviews(
                    document_key, page_number, reasons, status, reviewed_at,
                    reviewer_model, notes
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(review.get(column) for column in columns),
            )

    def documents(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM documents ORDER BY document_key"
        ).fetchall()
        return [dict(row) for row in rows]

    def upsert_document(self, document: dict[str, Any]) -> None:
        columns = (
            "document_key",
            "source_id",
            "source_path",
            "output_path",
            "size",
            "modified_ns",
            "sha256",
            "parser_version",
            "present",
            "converted_at",
            "checked_at",
            "missing_since",
            "error",
        )
        values = [document.get(column) for column in columns]
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{column} = excluded.{column}" for column in columns[1:]
        )
        self.connection.execute(
            f"""
            INSERT INTO documents({', '.join(columns)})
            VALUES({placeholders})
            ON CONFLICT(document_key) DO UPDATE SET {updates}
            """,
            values,
        )

    def mark_missing_except(
        self, seen: set[str], scanned_source_ids: set[str]
    ) -> int:
        missing = 0
        for document in self.documents():
            if (
                document["source_id"] not in scanned_source_ids
                or document["document_key"] in seen
                or not document["present"]
            ):
                continue
            document["present"] = 0
            document["missing_since"] = now()
            document["checked_at"] = now()
            self.upsert_document(document)
            missing += 1
        return missing

    def replace_reviews(
        self, document_key: str, reviews: dict[int, list[str]]
    ) -> None:
        self.connection.execute(
            "DELETE FROM page_reviews WHERE document_key = ?", (document_key,)
        )
        for page_number, reasons in sorted(reviews.items()):
            self.connection.execute(
                """
                INSERT INTO page_reviews(
                    document_key, page_number, reasons, status
                ) VALUES(?, ?, ?, 'pending')
                """,
                (document_key, page_number, json.dumps(reasons, ensure_ascii=False)),
            )

    def pending_reviews(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT
                r.document_key,
                r.page_number,
                r.reasons,
                r.status,
                d.source_id,
                d.source_path,
                d.output_path
            FROM page_reviews AS r
            JOIN documents AS d USING(document_key)
            WHERE r.status IN ('pending', 'needs_review') AND d.present = 1
            ORDER BY r.document_key, r.page_number
            """
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["reasons"] = json.loads(item["reasons"])
            result.append(item)
        return result

    def complete_reviews(
        self,
        document_key: str,
        pages: list[int],
        *,
        status: str,
        reviewer_model: str,
        notes: str | None,
        reviewed_at: str | None = None,
    ) -> int:
        if status not in {"verified", "needs_review"}:
            raise ValueError(f"지원하지 않는 검토 상태입니다: {status}")
        normalized_pages = normalize_review_pages(pages)
        reviewer_model = validate_reviewer_model(reviewer_model)
        review_time = _validate_reviewed_at(reviewed_at or now())
        count = 0
        for page in normalized_pages:
            cursor = self.connection.execute(
                """
                UPDATE page_reviews
                SET status = ?, reviewed_at = ?, reviewer_model = ?, notes = ?
                WHERE document_key = ? AND page_number = ?
                """,
                (status, review_time, reviewer_model, notes, document_key, page),
            )
            count += cursor.rowcount
        return count

    def pending_review_pages(self, document_key: str) -> list[int]:
        rows = self.connection.execute(
            """
            SELECT page_number
            FROM page_reviews
            WHERE document_key = ? AND status IN ('pending', 'needs_review')
            ORDER BY page_number
            """,
            (document_key,),
        ).fetchall()
        return [int(row["page_number"]) for row in rows]

    def review_counts(self, document_key: str) -> dict[str, int]:
        rows = self.connection.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM page_reviews
            WHERE document_key = ?
            GROUP BY status
            """,
            (document_key,),
        ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def register_conversation(
        self,
        *,
        conversation_id: str,
        output_path: str,
        title: str,
        scope: str,
        created_at: str,
        tags: list[str],
        aliases: list[str],
        updated_at: str | None = None,
        revision: int = 1,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO conversations(
                conversation_id, output_path, title, scope,
                created_at, updated_at, revision, tags, aliases
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                output_path = excluded.output_path,
                title = excluded.title,
                scope = excluded.scope,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                revision = excluded.revision,
                tags = excluded.tags,
                aliases = excluded.aliases
            """,
            (
                conversation_id,
                output_path,
                title,
                scope,
                created_at,
                updated_at or created_at,
                revision,
                json.dumps(tags, ensure_ascii=False),
                json.dumps(aliases, ensure_ascii=False),
            ),
        )

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def conversations(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT * FROM conversations
            ORDER BY created_at DESC, conversation_id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: str,
        updated_at: str,
        revision: int,
        expected_revision: int,
        tags: list[str],
        aliases: list[str],
    ) -> None:
        cursor = self.connection.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?, revision = ?, tags = ?, aliases = ?
            WHERE conversation_id = ? AND revision = ?
            """,
            (
                title,
                updated_at,
                revision,
                json.dumps(tags, ensure_ascii=False),
                json.dumps(aliases, ensure_ascii=False),
                conversation_id,
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            current = self.get_conversation(conversation_id)
            if current is None:
                raise ValueError(f"저장된 대화를 찾을 수 없습니다: {conversation_id}")
            raise ValueError(
                "저장된 대화가 다른 작업에서 변경되었습니다. 다시 조회하세요: "
                f"expected={expected_revision}, current={current['revision']}"
            )

    def delete_conversation(
        self, conversation_id: str, *, expected_revision: int
    ) -> None:
        cursor = self.connection.execute(
            """
            DELETE FROM conversations
            WHERE conversation_id = ? AND revision = ?
            """,
            (conversation_id, expected_revision),
        )
        if cursor.rowcount != 1:
            current = self.get_conversation(conversation_id)
            if current is None:
                raise ValueError(f"저장된 대화를 찾을 수 없습니다: {conversation_id}")
            raise ValueError(
                "저장된 대화가 다른 작업에서 변경되었습니다. 다시 조회하세요: "
                f"expected={expected_revision}, current={current['revision']}"
            )

    def status(self) -> dict[str, Any]:
        document_counts = self.connection.execute(
            """
            SELECT
                COUNT(*) AS tracked,
                SUM(CASE WHEN present = 1 THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN present = 0 THEN 1 ELSE 0 END) AS missing,
                SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) AS failed
            FROM documents
            """
        ).fetchone()
        pending = self.connection.execute(
            """
            SELECT COUNT(*) FROM page_reviews
            WHERE status IN ('pending', 'needs_review')
            """
        ).fetchone()[0]
        conversations = self.connection.execute(
            "SELECT COUNT(*) FROM conversations"
        ).fetchone()[0]
        stats_raw = self.get_metadata("last_stats")
        return {
            "last_sync": self.get_metadata("last_sync"),
            "tracked": int(document_counts["tracked"] or 0),
            "present": int(document_counts["present"] or 0),
            "missing": int(document_counts["missing"] or 0),
            "failed": int(document_counts["failed"] or 0),
            "pending_page_reviews": int(pending),
            "conversations": int(conversations),
            "last_stats": json.loads(stats_raw) if stats_raw else None,
            "latest_run": self.latest_library_run(),
        }
