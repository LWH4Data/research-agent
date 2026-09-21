from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from research_store.config import Config, load_config
from research_store.conversations import (
    delete_conversation,
    list_conversations,
    save_conversation,
    update_conversation,
)
from research_store.safety import PROJECT_MARKER_CONTENT
from research_store.search import search_library
from research_store.state import LibraryState, SCHEMA_VERSION
from research_store.sync import sync_library


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


def conversation_payload(
    *, title: str, created_at: str, transcript_text: str
) -> dict[str, object]:
    return {
        "title": title,
        "created_at": created_at,
        "scope": "current-topic",
        "capture_status": "complete",
        "summary": f"{title}의 최초 요약",
        "tags": ["initial-tag"],
        "aliases": ["initial alias"],
        "user_points": ["최초 사용자 생각"],
        "decisions": ["최초 결정"],
        "unverified": ["최초 미검증 내용"],
        "open_questions": ["최초 질문"],
        "related_documents": ["papers:paper.pdf"],
        "transcript": [
            {"role": "user", "content": transcript_text},
            {"role": "assistant", "content": "선택한 범위를 그대로 보존합니다."},
        ],
    }


def update_payload(marker: str = "UPDATED_UNIQUE_MEMORY") -> dict[str, object]:
    return {
        "title": "수정된 대화 제목",
        "summary": f"수정된 검색용 요약 {marker}",
        "tags": ["updated-tag", "광소자"],
        "aliases": ["updated alias", "optical coupling"],
        "user_points": ["수정된 사용자 생각"],
        "decisions": ["수정된 결정"],
        "unverified": ["수정된 미검증 내용"],
        "open_questions": ["수정된 미해결 질문"],
        "related_documents": ["papers:updated-paper.pdf"],
    }


def frontmatter(text: str) -> dict[str, object]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError("frontmatter가 없습니다")
    closing = lines.index("---", 1)
    result: dict[str, object] = {}
    for line in lines[1:closing]:
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"잘못된 frontmatter 줄: {line}")
        result[key] = json.loads(value.strip())
    return result


def transcript_block(text: str) -> str:
    marker = "## 선택 범위 원문\n\n"
    return text[text.index(marker) :]


class ConversationManagementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.source = root / "source"
        self.source.mkdir()
        self.source_pdf = self.source / "paper.pdf"
        self.source_pdf.write_bytes(b"original-pdf-bytes")
        self.project = make_project(root / "agent")
        self.config_path = write_config(self.project, self.source)
        self.config = load_config(self.config_path)

    def run_cli(
        self, *arguments: str, input_payload: object | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "research_store.cli",
                "--config",
                str(self.config_path),
                *arguments,
            ],
            input=(
                None
                if input_payload is None
                else json.dumps(input_payload, ensure_ascii=False)
            ),
            capture_output=True,
            text=True,
        )

    def save_two_conversations(self) -> tuple[Path, Path, str, str]:
        first_path = save_conversation(
            self.config,
            conversation_payload(
                title="첫 번째 연구 대화",
                created_at="2026-09-20T10:00:00+09:00",
                transcript_text="첫 번째 원문은 수정되면 안 됩니다.",
            ),
        )
        second_path = save_conversation(
            self.config,
            conversation_payload(
                title="두 번째 연구 대화",
                created_at="2026-09-21T10:00:00+09:00",
                transcript_text="두 번째 대화는 다른 기록입니다.",
            ),
        )
        records = list_conversations(self.config)
        ids_by_path = {record["path"]: record["conversation_id"] for record in records}
        return (
            first_path,
            second_path,
            str(ids_by_path[str(first_path.relative_to(self.project))]),
            str(ids_by_path[str(second_path.relative_to(self.project))]),
        )

    def test_cli_list_update_delete_lifecycle_preserves_unowned_and_immutable_data(
        self,
    ) -> None:
        sync_library(
            self.config,
            lambda _: "<!-- page: 1 -->\n\nPDF_ONLY_EVIDENCE remains unchanged.\n",
        )
        pdf_markdown = next(self.config.documents.rglob("*.md"))
        pdf_markdown_before = pdf_markdown.read_bytes()
        source_before = self.source_pdf.read_bytes()
        first_path, second_path, first_id, second_id = self.save_two_conversations()
        first_before = first_path.read_text(encoding="utf-8")
        second_before = second_path.read_bytes()
        first_metadata = frontmatter(first_before)
        first_transcript = transcript_block(first_before)

        listed = self.run_cli("conversation-list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        list_payload = json.loads(listed.stdout)
        self.assertEqual(
            [item["conversation_id"] for item in list_payload["conversations"]],
            [second_id, first_id],
        )
        first_listed = next(
            item
            for item in list_payload["conversations"]
            if item["conversation_id"] == first_id
        )
        self.assertEqual(first_listed["revision"], 1)
        self.assertEqual(first_listed["scope"], "current-topic")
        self.assertEqual(first_listed["tags"], ["initial-tag"])
        self.assertEqual(first_listed["aliases"], ["initial alias"])
        self.assertEqual(first_listed["path"], str(first_path.relative_to(self.project)))
        self.assertTrue(first_listed["available"])

        updated = self.run_cli(
            "conversation-update",
            first_id,
            "--expected-revision",
            "1",
            input_payload=update_payload(),
        )
        self.assertEqual(updated.returncode, 0, updated.stderr)
        update_result = json.loads(updated.stdout)
        self.assertEqual(update_result["conversation_id"], first_id)
        self.assertEqual(update_result["revision"], 2)
        self.assertEqual(update_result["path"], str(first_path.relative_to(self.project)))

        first_after = first_path.read_text(encoding="utf-8")
        metadata_after = frontmatter(first_after)
        self.assertEqual(metadata_after["id"], first_metadata["id"])
        self.assertEqual(metadata_after["scope"], first_metadata["scope"])
        self.assertEqual(metadata_after["created_at"], first_metadata["created_at"])
        self.assertEqual(metadata_after["revision"], 2)
        self.assertEqual(metadata_after["title"], "수정된 대화 제목")
        self.assertEqual(metadata_after["tags"], ["updated-tag", "광소자"])
        self.assertEqual(
            metadata_after["related_documents"], ["papers:updated-paper.pdf"]
        )
        self.assertEqual(transcript_block(first_after), first_transcript)
        for expected in (
            "UPDATED_UNIQUE_MEMORY",
            "수정된 사용자 생각",
            "수정된 결정",
            "수정된 미검증 내용",
            "수정된 미해결 질문",
        ):
            self.assertIn(expected, first_after)
        matches = search_library(self.config, ["UPDATED_UNIQUE_MEMORY"])["matches"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path"], str(first_path.relative_to(self.project)))

        after_update_snapshot = first_path.read_bytes()
        stale_update = self.run_cli(
            "conversation-update",
            first_id,
            "--expected-revision",
            "1",
            input_payload=update_payload("SHOULD_NOT_APPEAR"),
        )
        self.assertEqual(stale_update.returncode, 1)
        self.assertIn("다른 작업에서 변경", stale_update.stderr)
        self.assertEqual(first_path.read_bytes(), after_update_snapshot)

        stale_delete = self.run_cli(
            "conversation-delete", first_id, "--expected-revision", "1"
        )
        self.assertEqual(stale_delete.returncode, 1)
        self.assertIn("다른 작업에서 변경", stale_delete.stderr)
        self.assertTrue(first_path.is_file())

        deleted = self.run_cli(
            "conversation-delete", first_id, "--expected-revision", "2"
        )
        self.assertEqual(deleted.returncode, 0, deleted.stderr)
        deletion_result = json.loads(deleted.stdout)
        self.assertEqual(deletion_result["conversation_id"], first_id)
        self.assertEqual(
            deletion_result["deleted_markdown"],
            str(first_path.relative_to(self.project)),
        )
        self.assertFalse(deletion_result["codex_conversation_deleted"])
        self.assertFalse(deletion_result["originals_deleted"])
        self.assertFalse(deletion_result["pdf_markdown_deleted"])
        self.assertFalse(first_path.exists())
        self.assertEqual(
            [row["conversation_id"] for row in list_conversations(self.config)],
            [second_id],
        )
        self.assertEqual(
            search_library(self.config, ["UPDATED_UNIQUE_MEMORY"])["matches"], []
        )
        self.assertEqual(second_path.read_bytes(), second_before)
        self.assertEqual(pdf_markdown.read_bytes(), pdf_markdown_before)
        self.assertEqual(self.source_pdf.read_bytes(), source_before)

    def test_update_requires_exact_complete_mutable_field_set(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        before = output.read_bytes()
        invalid_payloads: list[tuple[str, object, str]] = []

        missing = update_payload()
        del missing["related_documents"]
        invalid_payloads.append(("missing", missing, "필요한 값"))

        extra = update_payload()
        extra["scope"] = "entire-conversation"
        invalid_payloads.append(("extra", extra, "허용되지 않은 값"))

        immutable = update_payload()
        immutable["transcript"] = [{"role": "user", "content": "조작"}]
        invalid_payloads.append(("immutable", immutable, "허용되지 않은 값"))

        invalid_payloads.append(("not-an-object", ["invalid"], "객체"))

        for label, payload, message in invalid_payloads:
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, message):
                    update_conversation(
                        self.config,
                        conversation_id,
                        payload,  # type: ignore[arg-type]
                        expected_revision=1,
                    )
                self.assertEqual(output.read_bytes(), before)
                record = next(
                    item
                    for item in list_conversations(self.config)
                    if item["conversation_id"] == conversation_id
                )
                self.assertEqual(record["revision"], 1)

    def test_update_promotes_v1_markdown_and_preserves_immutable_fields(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        current = output.read_text(encoding="utf-8")
        current_metadata = frontmatter(current)
        current_transcript = transcript_block(current)
        legacy = current.replace("schema_version: 2\n", "schema_version: 1\n", 1)
        legacy = "\n".join(
            line
            for line in legacy.splitlines()
            if not line.startswith("updated_at:") and not line.startswith("revision:")
        ) + "\n"
        output.write_text(legacy, encoding="utf-8")

        result = update_conversation(
            self.config,
            conversation_id,
            update_payload("PROMOTED_V1_MEMORY"),
            expected_revision=1,
        )

        promoted = output.read_text(encoding="utf-8")
        promoted_metadata = frontmatter(promoted)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(promoted_metadata["schema_version"], 2)
        self.assertEqual(promoted_metadata["revision"], 2)
        self.assertEqual(promoted_metadata["id"], current_metadata["id"])
        self.assertEqual(promoted_metadata["scope"], current_metadata["scope"])
        self.assertEqual(
            promoted_metadata["created_at"], current_metadata["created_at"]
        )
        self.assertEqual(transcript_block(promoted), current_transcript)
        self.assertEqual(result["path"], str(output.relative_to(self.project)))
        self.assertIn("PROMOTED_V1_MEMORY", promoted)

    def test_future_markdown_schema_blocks_update_and_delete(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        future = output.read_text(encoding="utf-8").replace(
            "schema_version: 2\n", "schema_version: 999\n", 1
        )
        output.write_text(future, encoding="utf-8")
        before = output.read_bytes()

        for operation in ("update", "delete"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(
                    ValueError, "새로운 대화 Markdown 스키마"
                ):
                    if operation == "update":
                        update_conversation(
                            self.config,
                            conversation_id,
                            update_payload(),
                            expected_revision=1,
                        )
                    else:
                        delete_conversation(
                            self.config,
                            conversation_id,
                            expected_revision=1,
                        )
                self.assertEqual(output.read_bytes(), before)
                record = self._database_record(conversation_id)
                self.assertIsNotNone(record)

    def test_markdown_and_database_revision_mismatch_blocks_update_and_delete(
        self,
    ) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        mismatched = output.read_text(encoding="utf-8").replace(
            "revision: 1\n", "revision: 2\n", 1
        )
        output.write_text(mismatched, encoding="utf-8")
        before = output.read_bytes()

        for operation in ("update", "delete"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "revision.*일치"):
                    if operation == "update":
                        update_conversation(
                            self.config,
                            conversation_id,
                            update_payload(),
                            expected_revision=1,
                        )
                    else:
                        delete_conversation(
                            self.config,
                            conversation_id,
                            expected_revision=1,
                        )
                self.assertEqual(output.read_bytes(), before)
                record = self._database_record(conversation_id)
                self.assertIsNotNone(record)
                assert record is not None
                self.assertEqual(record[6], 1)

    def test_delete_cleans_database_orphan_when_markdown_is_already_missing(
        self,
    ) -> None:
        sync_library(
            self.config,
            lambda _: "<!-- page: 1 -->\n\nPDF_ORPHAN_CONTROL remains unchanged.\n",
        )
        pdf_markdown = next(self.config.documents.rglob("*.md"))
        pdf_before = pdf_markdown.read_bytes()
        source_before = self.source_pdf.read_bytes()
        output, other_output, conversation_id, other_id = self.save_two_conversations()
        other_before = other_output.read_bytes()
        relative = str(output.relative_to(self.project))
        output.unlink()
        orphan_listing = next(
            row
            for row in list_conversations(self.config)
            if row["conversation_id"] == conversation_id
        )
        self.assertFalse(orphan_listing["available"])
        self.assertEqual(orphan_listing["path"], relative)

        result = delete_conversation(
            self.config, conversation_id, expected_revision=1
        )

        self.assertEqual(result["conversation_id"], conversation_id)
        self.assertIsNone(result["deleted_markdown"])
        self.assertTrue(result["missing_markdown"])
        self.assertFalse(output.exists())
        self.assertIsNone(self._database_record(conversation_id))
        self.assertEqual(
            [row["conversation_id"] for row in list_conversations(self.config)],
            [other_id],
        )
        self.assertEqual(other_output.read_bytes(), other_before)
        self.assertEqual(pdf_markdown.read_bytes(), pdf_before)
        self.assertEqual(self.source_pdf.read_bytes(), source_before)

    def test_unknown_id_and_invalid_revision_leave_everything_unchanged(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        before = output.read_bytes()
        with self.assertRaisesRegex(ValueError, "찾을 수 없습니다"):
            update_conversation(
                self.config,
                "conversation-does-not-exist",
                update_payload(),
                expected_revision=1,
            )
        with self.assertRaisesRegex(ValueError, "찾을 수 없습니다"):
            delete_conversation(
                self.config,
                "conversation-does-not-exist",
                expected_revision=1,
            )
        with self.assertRaisesRegex(ValueError, "1 이상"):
            update_conversation(
                self.config,
                conversation_id,
                update_payload(),
                expected_revision=0,
            )
        with self.assertRaisesRegex(ValueError, "1 이상"):
            delete_conversation(self.config, conversation_id, expected_revision=0)
        self.assertEqual(output.read_bytes(), before)

    def test_database_output_path_cannot_target_source_or_pdf_markdown(self) -> None:
        sync_library(self.config, lambda _: "<!-- page: 1 -->\n\nPDF protected\n")
        pdf_markdown = next(self.config.documents.rglob("*.md"))
        pdf_before = pdf_markdown.read_bytes()
        source_note = self.source / "victim.md"
        source_note.write_text("source note\n", encoding="utf-8")
        source_before = source_note.read_bytes()
        output, _, conversation_id, _ = self.save_two_conversations()
        original_relative = str(output.relative_to(self.project))

        malicious_paths = (
            ("outside-project", "../source/victim.md", "올바른 상대 경로"),
            (
                "pdf-markdown",
                str(pdf_markdown.relative_to(self.project)),
                "대화 저장 폴더를 벗어났습니다",
            ),
        )
        for label, malicious, message in malicious_paths:
            for operation in ("update", "delete"):
                with self.subTest(path=label, operation=operation):
                    with sqlite3.connect(self.config.state) as database:
                        database.execute(
                            "UPDATE conversations SET output_path = ? "
                            "WHERE conversation_id = ?",
                            (malicious, conversation_id),
                        )
                    with self.assertRaisesRegex(ValueError, message):
                        if operation == "update":
                            update_conversation(
                                self.config,
                                conversation_id,
                                update_payload(),
                                expected_revision=1,
                            )
                        else:
                            delete_conversation(
                                self.config,
                                conversation_id,
                                expected_revision=1,
                            )
                    with sqlite3.connect(self.config.state) as database:
                        database.execute(
                            "UPDATE conversations SET output_path = ? "
                            "WHERE conversation_id = ?",
                            (original_relative, conversation_id),
                        )
                    self.assertTrue(output.is_file())
                    self.assertEqual(pdf_markdown.read_bytes(), pdf_before)
                    self.assertEqual(source_note.read_bytes(), source_before)

    def test_frontmatter_id_mismatch_blocks_update_and_delete(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        original = output.read_text(encoding="utf-8")
        output.write_text(
            original.replace(
                f'id: {json.dumps(conversation_id)}',
                'id: "conversation-tampered"',
                1,
            ),
            encoding="utf-8",
        )
        tampered = output.read_bytes()

        for operation in ("update", "delete"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "ID.*일치하지 않습니다"):
                    if operation == "update":
                        update_conversation(
                            self.config,
                            conversation_id,
                            update_payload(),
                            expected_revision=1,
                        )
                    else:
                        delete_conversation(
                            self.config,
                            conversation_id,
                            expected_revision=1,
                        )
                self.assertEqual(output.read_bytes(), tampered)
                self.assertIsNotNone(self._database_record(conversation_id))

    def test_symlinked_conversation_cannot_modify_external_file(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are not supported")
        output, _, conversation_id, _ = self.save_two_conversations()
        victim = self.source / "external.md"
        victim.write_text("external content\n", encoding="utf-8")
        output.unlink()
        output.symlink_to(victim)

        for operation in ("update", "delete"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(
                    ValueError, "심볼릭 링크|프로젝트 내부"
                ):
                    if operation == "update":
                        update_conversation(
                            self.config,
                            conversation_id,
                            update_payload(),
                            expected_revision=1,
                        )
                    else:
                        delete_conversation(
                            self.config,
                            conversation_id,
                            expected_revision=1,
                        )
                self.assertEqual(victim.read_text(encoding="utf-8"), "external content\n")
                self.assertIsNotNone(self._database_record(conversation_id))

    def test_hard_linked_conversation_cannot_modify_external_file(self) -> None:
        if not hasattr(os, "link"):
            self.skipTest("hard links are not supported")
        output, _, conversation_id, _ = self.save_two_conversations()
        victim = self.source / "external.md"
        victim.write_text("external content\n", encoding="utf-8")
        output.unlink()
        os.link(victim, output)

        for operation in ("update", "delete"):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "하드 링크"):
                    if operation == "update":
                        update_conversation(
                            self.config,
                            conversation_id,
                            update_payload(),
                            expected_revision=1,
                        )
                    else:
                        delete_conversation(
                            self.config,
                            conversation_id,
                            expected_revision=1,
                        )
                self.assertEqual(victim.read_text(encoding="utf-8"), "external content\n")
                self.assertIsNotNone(self._database_record(conversation_id))

    def _database_record(self, conversation_id: str) -> tuple[object, ...] | None:
        with sqlite3.connect(self.config.state) as database:
            return database.execute(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()


class ConversationSchemaMigrationTests(unittest.TestCase):
    def make_config(self) -> Config:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        source = root / "source"
        source.mkdir()
        project = make_project(root / "agent")
        return load_config(write_config(project, source))

    def test_v1_database_migrates_conversation_revision_fields(self) -> None:
        config = self.make_config()
        config.state.parent.mkdir(parents=True)
        with sqlite3.connect(config.state) as database:
            database.executescript(
                """
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT INTO metadata(key, value) VALUES('schema_version', '1');
                CREATE TABLE conversations (
                    conversation_id TEXT PRIMARY KEY,
                    output_path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    aliases TEXT NOT NULL
                );
                INSERT INTO conversations(
                    conversation_id, output_path, title, scope,
                    created_at, tags, aliases
                ) VALUES(
                    'legacy-id',
                    'knowledge/conversations/legacy.md',
                    'legacy title',
                    'current-topic',
                    '2026-09-20T10:00:00+09:00',
                    '["legacy-tag"]',
                    '["legacy-alias"]'
                );
                """
            )

        with LibraryState(config.state, config.root) as state:
            record = state.get_conversation("legacy-id")
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record["updated_at"], record["created_at"])
            self.assertEqual(record["revision"], 1)
            self.assertEqual(
                state.get_metadata("schema_version"), str(SCHEMA_VERSION)
            )

    def test_future_database_schema_is_rejected_without_downgrade(self) -> None:
        config = self.make_config()
        config.state.parent.mkdir(parents=True)
        future_version = SCHEMA_VERSION + 1
        with sqlite3.connect(config.state) as database:
            database.execute(
                "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            database.execute(
                "INSERT INTO metadata(key, value) VALUES('schema_version', ?)",
                (str(future_version),),
            )

        with self.assertRaisesRegex(RuntimeError, "새로운 SQLite 스키마"):
            LibraryState(config.state, config.root)
        with sqlite3.connect(config.state) as database:
            stored = database.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
        self.assertEqual(stored, (str(future_version),))


if __name__ == "__main__":
    unittest.main()
