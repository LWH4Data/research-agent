from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from .safety import ensure_owned_directory, reject_linked_file, require_owned_path


SCHEMA_VERSION = 1


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class LibraryState(AbstractContextManager["LibraryState"]):
    """SQLite-backed sync ledger. Source documents are never opened for writing."""

    def __init__(self, path: Path, root: Path):
        self.root = root
        self.path = require_owned_path(path, root, label="SQLite 저장 경로")
        ensure_owned_directory(self.path.parent, root, label="SQLite 저장 폴더")
        self.path = reject_linked_file(self.path, root, label="SQLite 저장 경로")
        for suffix in ("-journal", "-wal", "-shm"):
            reject_linked_file(
                Path(f"{self.path}{suffix}"),
                root,
                label="SQLite 보조 파일 경로",
            )
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        # Keep SQLite's sort/index spill files in memory so every persistent
        # write remains beside the project-owned database.
        self.connection.execute("PRAGMA temp_store = MEMORY")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

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
                tags TEXT NOT NULL,
                aliases TEXT NOT NULL
            );
            """
        )
        self.set_metadata("schema_version", str(SCHEMA_VERSION))
        self.connection.commit()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        self.connection.close()

    def set_metadata(self, key: str, value: str) -> None:
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

    def get_document(self, document_key: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM documents WHERE document_key = ?", (document_key,)
        ).fetchone()
        return None if row is None else dict(row)

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
    ) -> int:
        if status not in {"verified", "needs_review"}:
            raise ValueError(f"지원하지 않는 검토 상태입니다: {status}")
        count = 0
        for page in pages:
            cursor = self.connection.execute(
                """
                UPDATE page_reviews
                SET status = ?, reviewed_at = ?, reviewer_model = ?, notes = ?
                WHERE document_key = ? AND page_number = ?
                """,
                (status, now(), reviewer_model, notes, document_key, page),
            )
            count += cursor.rowcount
        return count

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
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO conversations(
                conversation_id, output_path, title, scope,
                created_at, tags, aliases
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                output_path = excluded.output_path,
                title = excluded.title,
                scope = excluded.scope,
                created_at = excluded.created_at,
                tags = excluded.tags,
                aliases = excluded.aliases
            """,
            (
                conversation_id,
                output_path,
                title,
                scope,
                created_at,
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
        }
