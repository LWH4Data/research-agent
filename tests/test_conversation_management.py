from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import research_store.conversations as conversation_module
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


def exact_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as file:
        return file.read()


def legacy_conversation_markdown(
    *,
    schema_version: int,
    conversation_id: str,
    created_at: str,
    updated_at: str,
) -> str:
    metadata: list[tuple[str, object]] = [
        ("schema_version", schema_version),
        ("id", conversation_id),
        ("type", "conversation"),
        ("title", "첫 번째 연구 대화"),
        ("created_at", created_at),
    ]
    if schema_version >= 2:
        metadata.extend((("updated_at", updated_at), ("revision", 1)))
    metadata.extend(
        (
            ("language", ["ko"]),
            ("scope", "current-topic"),
            ("tags", ["initial-tag"]),
            ("aliases", ["initial alias"]),
            ("status", ["research-note"]),
            ("related_documents", ["papers:paper.pdf"]),
            ("transcript_capture", "complete"),
            ("capture_note", ""),
        )
    )
    frontmatter_lines = ["---"] + [
        f"{key}: {json.dumps(value, ensure_ascii=False)}"
        for key, value in metadata
    ]
    frontmatter_lines.extend(("---", ""))
    body = """# 첫 번째 연구 대화

## 검색용 요약

첫 번째 연구 대화의 최초 요약

## 사용자의 생각

- 최초 사용자 생각

## 결정된 사항

- 최초 결정

## 검증되지 않은 생각

- 최초 미검증 내용

## 미해결 질문

- 최초 질문

## 선택 범위 원문

### 사용자

> 첫 번째 원문은 수정되면 안 됩니다.

### Codex

> 선택한 범위를 그대로 보존합니다.
"""
    return "\n".join(frontmatter_lines) + body


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

    def test_conversation_get_round_trips_v3_without_returning_transcript(
        self,
    ) -> None:
        payload = conversation_payload(
            title="구조화된 대화 # 기록",
            created_at="2026-09-21T11:00:00+09:00",
            transcript_text="TRANSCRIPT_SECRET_MUST_NOT_BE_RETURNED",
        )
        payload.update(
            {
                "capture_status": "partial",
                "capture_note": "마지막 응답 뒤 내용은 제외됨\n## 참고용 제목",
                "summary": (
                    "첫 줄\n\n## 결정된 사항\n\n- 요약 안의 제목 같은 문자열"
                    "\u2028Unicode 줄 구분 문자도 그대로 보존"
                ),
                "tags": ["광소자", "RAG"],
                "aliases": ["별칭 첫 줄\n## 별칭 내부 제목", "optical retrieval"],
                "user_points": ["생각 첫 줄\n\n## 선택 범위 원문\n\n본문처럼 보이는 값"],
                "decisions": ["결정 첫 줄\n- 목록처럼 보이는 둘째 줄"],
                "unverified": ["미검증 첫 줄\n### 사용자\n> 인용처럼 보이는 값"],
                "open_questions": ["질문 첫 줄\n\n## 검색용 요약\n\n제목처럼 보이는 값"],
                "related_documents": [
                    "papers:optics/laser.pdf",
                    "notes:첫 줄\n## 문서 제목처럼 보이는 값",
                ],
            }
        )
        output = save_conversation(self.config, payload)
        record = next(
            item
            for item in list_conversations(self.config)
            if item["path"] == str(output.relative_to(self.project))
        )
        conversation_id = str(record["conversation_id"])
        expected_editable = {
            key: payload[key]
            for key in (
                "title",
                "summary",
                "tags",
                "aliases",
                "user_points",
                "decisions",
                "unverified",
                "open_questions",
                "related_documents",
            )
        }
        markdown_before = output.read_bytes()
        markdown_mtime_before = output.stat().st_mtime_ns
        database_before = self.config.state.read_bytes()
        database_mtime_before = self.config.state.stat().st_mtime_ns

        result = conversation_module.get_conversation(self.config, conversation_id)

        self.assertEqual(
            set(result),
            {
                "conversation_id",
                "path",
                "revision",
                "updated_at",
                "editable",
                "immutable",
            },
        )
        self.assertEqual(result["conversation_id"], conversation_id)
        self.assertEqual(result["path"], str(output.relative_to(self.project)))
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["updated_at"], payload["created_at"])
        self.assertEqual(set(result["editable"]), set(expected_editable))
        self.assertEqual(result["editable"], expected_editable)
        self.assertEqual(
            result["immutable"],
            {
                "scope": "current-topic",
                "created_at": payload["created_at"],
                "transcript_capture": "partial",
                "capture_note": payload["capture_note"],
            },
        )
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("transcript", result)
        self.assertNotIn("TRANSCRIPT_SECRET_MUST_NOT_BE_RETURNED", serialized)
        self.assertEqual(output.read_bytes(), markdown_before)
        self.assertEqual(output.stat().st_mtime_ns, markdown_mtime_before)
        self.assertEqual(self.config.state.read_bytes(), database_before)
        self.assertEqual(self.config.state.stat().st_mtime_ns, database_mtime_before)
        title_matches = [
            match
            for match in search_library(self.config, [str(payload["title"])])["matches"]
            if match["type"] == "conversation" and match["path"] == result["path"]
        ]
        self.assertEqual(len(title_matches), 1)

    def test_transcript_trailing_whitespace_survives_update(self) -> None:
        payload = conversation_payload(
            title="원문 공백 보존",
            created_at="2026-09-21T11:30:00+09:00",
            transcript_text="끝 공백  \n\n",
        )
        output = save_conversation(self.config, payload)
        record = next(
            item
            for item in list_conversations(self.config)
            if item["path"] == str(output.relative_to(self.project))
        )
        conversation_id = str(record["conversation_id"])
        transcript_before = transcript_block(output.read_text(encoding="utf-8"))
        self.assertIn("> 끝 공백  \n>\n>\n\n### Codex", transcript_before)

        update_conversation(
            self.config,
            conversation_id,
            update_payload("TRANSCRIPT_WHITESPACE_UPDATE"),
            expected_revision=1,
        )

        self.assertEqual(
            transcript_block(output.read_text(encoding="utf-8")),
            transcript_before,
        )

    def test_crlf_and_lone_cr_round_trip_in_all_editable_fields_and_transcript(
        self,
    ) -> None:
        payload = conversation_payload(
            title="원본 제목\r\n둘째 줄\r셋째 줄",
            created_at="2026-09-21T11:45:00+09:00",
            transcript_text="원문 CRLF\r\n다음 줄\r마지막 줄",
        )
        payload.update(
            {
                "summary": "요약 CRLF\r\n다음 줄\r마지막 줄",
                "tags": ["태그\r\n둘째", "태그\r셋째"],
                "aliases": ["별칭\r\n둘째", "별칭\r셋째"],
                "user_points": ["생각\r\n둘째\r셋째"],
                "decisions": ["결정\r\n둘째\r셋째"],
                "unverified": ["미검증\r\n둘째\r셋째"],
                "open_questions": ["질문\r\n둘째\r셋째"],
                "related_documents": ["papers:첫째\r\n둘째\r셋째.pdf"],
            }
        )
        output = save_conversation(self.config, payload)
        record = next(
            item
            for item in list_conversations(self.config)
            if item["path"] == str(output.relative_to(self.project))
        )
        conversation_id = str(record["conversation_id"])
        editable_before = {
            key: payload[key] for key in conversation_module.EDITABLE_FIELDS
        }
        markdown_before = exact_text(output)
        transcript_before = conversation_module._transcript_block(markdown_before)

        self.assertIn("> 원문 CRLF\r\n> 다음 줄\r마지막 줄", transcript_before)
        self.assertEqual(
            conversation_module.get_conversation(self.config, conversation_id)[
                "editable"
            ],
            editable_before,
        )

        revised = {
            "title": "수정 제목\r\n둘째\r셋째",
            "summary": "수정 요약\r\n둘째\r셋째",
            "tags": ["수정 태그\r\n둘째\r셋째"],
            "aliases": ["수정 별칭\r\n둘째\r셋째"],
            "user_points": ["수정 생각\r\n둘째\r셋째"],
            "decisions": ["수정 결정\r\n둘째\r셋째"],
            "unverified": ["수정 미검증\r\n둘째\r셋째"],
            "open_questions": ["수정 질문\r\n둘째\r셋째"],
            "related_documents": ["papers:수정\r\n둘째\r셋째.pdf"],
        }
        update_conversation(
            self.config,
            conversation_id,
            revised,
            expected_revision=1,
        )

        markdown_after = exact_text(output)
        self.assertEqual(
            conversation_module._transcript_block(markdown_after),
            transcript_before,
        )
        self.assertEqual(
            conversation_module.get_conversation(self.config, conversation_id)[
                "editable"
            ],
            revised,
        )

    def test_idempotent_save_fully_validates_v3_and_immutable_identity(self) -> None:
        payload = conversation_payload(
            title="동일 저장 검증",
            created_at="2026-09-21T12:00:00+09:00",
            transcript_text="동일 저장 원문",
        )
        output = save_conversation(self.config, payload)
        markdown_before = output.read_bytes()
        database_before = self.config.state.read_bytes()

        self.assertEqual(save_conversation(self.config, payload), output)
        self.assertEqual(output.read_bytes(), markdown_before)
        self.assertEqual(self.config.state.read_bytes(), database_before)

        mismatched_scope = dict(payload)
        mismatched_scope["scope"] = "entire-conversation"
        with self.assertRaisesRegex(ValueError, "scope.*동일 저장 요청"):
            save_conversation(self.config, mismatched_scope)
        self.assertEqual(output.read_bytes(), markdown_before)

        tampered = exact_text(output).replace(
            "동일 저장 검증의 최초 요약",
            "Markdown 본문만 변조됨",
            1,
        )
        output.write_text(tampered, encoding="utf-8", newline="")
        with self.assertRaisesRegex(ValueError, "본문.*editable.*일치"):
            save_conversation(self.config, payload)
        self.assertEqual(exact_text(output), tampered)

    def test_idempotent_save_retains_valid_legacy_record_without_rewriting(
        self,
    ) -> None:
        payload = conversation_payload(
            title="첫 번째 연구 대화",
            created_at="2026-09-21T12:15:00+09:00",
            transcript_text="첫 번째 원문은 수정되면 안 됩니다.",
        )
        output = save_conversation(self.config, payload)
        record = next(
            item
            for item in list_conversations(self.config)
            if item["path"] == str(output.relative_to(self.project))
        )
        conversation_id = str(record["conversation_id"])
        legacy = legacy_conversation_markdown(
            schema_version=2,
            conversation_id=conversation_id,
            created_at=str(record["created_at"]),
            updated_at=str(record["updated_at"]),
        )
        output.write_text(legacy, encoding="utf-8", newline="")
        before = output.read_bytes()

        self.assertEqual(save_conversation(self.config, payload), output)
        self.assertEqual(output.read_bytes(), before)

    def test_legacy_promotion_rejects_ambiguous_or_malformed_transcript(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        record = next(
            item
            for item in list_conversations(self.config)
            if item["conversation_id"] == conversation_id
        )
        legacy = legacy_conversation_markdown(
            schema_version=2,
            conversation_id=conversation_id,
            created_at=str(record["created_at"]),
            updated_at=str(record["updated_at"]),
        )
        malformed_cases = {
            "ambiguous-heading": (
                legacy.replace(
                    "첫 번째 연구 대화의 최초 요약",
                    "첫 번째 연구 대화의 최초 요약\n\n## 선택 범위 원문\n\n가짜",
                    1,
                ),
                "원문 구역이 모호",
            ),
            "unknown-role": (
                legacy.replace("### 사용자", "### 시스템", 1),
                "원문 역할 블록",
            ),
            "unquoted-content": (
                legacy.replace(
                    "> 첫 번째 원문은 수정되면 안 됩니다.",
                    "첫 번째 원문은 수정되면 안 됩니다.",
                    1,
                ),
                "원문 역할 블록",
            ),
        }

        for label, (malformed, message) in malformed_cases.items():
            with self.subTest(case=label):
                output.write_text(malformed, encoding="utf-8", newline="")
                before = output.read_bytes()
                with self.assertRaisesRegex(ValueError, message):
                    update_conversation(
                        self.config,
                        conversation_id,
                        update_payload(f"REJECT_{label}"),
                        expected_revision=1,
                        confirm_legacy_promotion=True,
                    )
                self.assertEqual(output.read_bytes(), before)
                database_record = self._database_record(conversation_id)
                self.assertIsNotNone(database_record)
                assert database_record is not None
                self.assertEqual(database_record[6], 1)

    def test_cli_conversation_get_requires_exact_positional_id(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        before = output.read_bytes()

        received = self.run_cli("conversation-get", conversation_id)

        self.assertEqual(received.returncode, 0, received.stderr)
        result = json.loads(received.stdout)
        self.assertEqual(result["conversation_id"], conversation_id)
        self.assertEqual(result["path"], str(output.relative_to(self.project)))
        self.assertEqual(result["revision"], 1)
        self.assertEqual(
            set(result["editable"]),
            {
                "title",
                "summary",
                "tags",
                "aliases",
                "user_points",
                "decisions",
                "unverified",
                "open_questions",
                "related_documents",
            },
        )
        self.assertNotIn("첫 번째 원문은 수정되면 안 됩니다.", received.stdout)

        partial_id = self.run_cli("conversation-get", conversation_id[:-1])
        self.assertEqual(partial_id.returncode, 1)
        self.assertIn("찾을 수 없습니다", partial_id.stderr)
        missing_id = self.run_cli("conversation-get")
        self.assertEqual(missing_id.returncode, 2)
        self.assertEqual(output.read_bytes(), before)

    def test_conversation_get_rejects_path_link_id_schema_and_revision_mismatch(
        self,
    ) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        original = output.read_text(encoding="utf-8")
        metadata = frontmatter(original)
        relative = str(output.relative_to(self.project))

        with self.subTest(mismatch="path"):
            with sqlite3.connect(self.config.state) as database:
                database.execute(
                    "UPDATE conversations SET output_path = ? WHERE conversation_id = ?",
                    ("../source/paper.pdf", conversation_id),
                )
            try:
                with self.assertRaisesRegex(ValueError, "올바른 상대 경로"):
                    conversation_module.get_conversation(self.config, conversation_id)
            finally:
                with sqlite3.connect(self.config.state) as database:
                    database.execute(
                        "UPDATE conversations SET output_path = ? "
                        "WHERE conversation_id = ?",
                        (relative, conversation_id),
                    )

        if hasattr(os, "symlink"):
            with self.subTest(mismatch="link"):
                victim = self.source / "external-conversation.md"
                victim.write_text("external content\n", encoding="utf-8")
                output.unlink()
                output.symlink_to(victim)
                try:
                    with self.assertRaisesRegex(
                        ValueError, "심볼릭 링크|프로젝트 내부"
                    ):
                        conversation_module.get_conversation(
                            self.config, conversation_id
                        )
                    self.assertEqual(
                        victim.read_text(encoding="utf-8"), "external content\n"
                    )
                finally:
                    output.unlink(missing_ok=True)
                    output.write_text(original, encoding="utf-8")

        with self.subTest(mismatch="id"):
            output.write_text(
                original.replace(
                    f'id: {json.dumps(conversation_id)}',
                    'id: "conversation-tampered"',
                    1,
                ),
                encoding="utf-8",
            )
            try:
                with self.assertRaisesRegex(ValueError, "ID.*일치하지 않습니다"):
                    conversation_module.get_conversation(self.config, conversation_id)
            finally:
                output.write_text(original, encoding="utf-8")

        with self.subTest(mismatch="schema"):
            output.write_text(
                original.replace(
                    f"schema_version: {metadata['schema_version']}\n",
                    "schema_version: 999\n",
                    1,
                ),
                encoding="utf-8",
            )
            try:
                with self.assertRaisesRegex(
                    ValueError, "새로운 대화 Markdown 스키마"
                ):
                    conversation_module.get_conversation(self.config, conversation_id)
            finally:
                output.write_text(original, encoding="utf-8")

        with self.subTest(mismatch="revision"):
            output.write_text(
                original.replace("revision: 1\n", "revision: 2\n", 1),
                encoding="utf-8",
            )
            try:
                with self.assertRaisesRegex(ValueError, "revision.*일치"):
                    conversation_module.get_conversation(self.config, conversation_id)
            finally:
                output.write_text(original, encoding="utf-8")

        with self.subTest(mismatch="editable-body"):
            output.write_text(
                original.replace(
                    "\n# 첫 번째 연구 대화\n",
                    "\n# 본문만 변조된 대화\n",
                    1,
                ),
                encoding="utf-8",
            )
            try:
                with self.assertRaisesRegex(ValueError, "본문.*editable.*일치"):
                    conversation_module.get_conversation(self.config, conversation_id)
            finally:
                output.write_text(original, encoding="utf-8")

        with self.subTest(mismatch="transcript-hash"):
            output.write_text(
                original.replace(
                    "첫 번째 원문은 수정되면 안 됩니다.",
                    "변조된 원문입니다.",
                    1,
                ),
                encoding="utf-8",
            )
            try:
                with self.assertRaisesRegex(ValueError, "원문 해시.*일치"):
                    conversation_module.get_conversation(self.config, conversation_id)
            finally:
                output.write_text(original, encoding="utf-8")

    def test_conversation_get_reads_v1_v2_and_update_promotes_each_to_v3(
        self,
    ) -> None:
        expected_legacy_editable = {
            "title": "첫 번째 연구 대화",
            "summary": "첫 번째 연구 대화의 최초 요약",
            "tags": ["initial-tag"],
            "aliases": ["initial alias"],
            "user_points": ["최초 사용자 생각"],
            "decisions": ["최초 결정"],
            "unverified": ["최초 미검증 내용"],
            "open_questions": ["최초 질문"],
            "related_documents": ["papers:paper.pdf"],
        }
        for schema_version in (1, 2):
            with self.subTest(schema_version=schema_version):
                created_at = f"2026-09-{21 + schema_version:02d}T10:00:00+09:00"
                output = save_conversation(
                    self.config,
                    conversation_payload(
                        title="첫 번째 연구 대화",
                        created_at=created_at,
                        transcript_text="첫 번째 원문은 수정되면 안 됩니다.",
                    ),
                )
                record = next(
                    item
                    for item in list_conversations(self.config)
                    if item["path"] == str(output.relative_to(self.project))
                )
                conversation_id = str(record["conversation_id"])
                output.write_text(
                    legacy_conversation_markdown(
                        schema_version=schema_version,
                        conversation_id=conversation_id,
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                    encoding="utf-8",
                )

                legacy_result = conversation_module.get_conversation(
                    self.config, conversation_id
                )

                self.assertEqual(legacy_result["revision"], 1)
                self.assertEqual(legacy_result["updated_at"], created_at)
                self.assertEqual(legacy_result["schema_version"], schema_version)
                self.assertIs(legacy_result["migration_required"], True)
                self.assertNotIn("editable", legacy_result)
                self.assertEqual(
                    legacy_result["editable_candidate"],
                    expected_legacy_editable,
                )
                self.assertEqual(
                    legacy_result["immutable"],
                    {
                        "scope": "current-topic",
                        "created_at": created_at,
                        "transcript_capture": "complete",
                        "capture_note": "",
                    },
                )
                markdown_before_rejected_update = output.read_bytes()
                database_before_rejected_update = self.config.state.read_bytes()
                database_mtime_before_rejected_update = (
                    self.config.state.stat().st_mtime_ns
                )
                with self.assertRaisesRegex(ValueError, "confirm_legacy_promotion"):
                    update_conversation(
                        self.config,
                        conversation_id,
                        update_payload(f"REJECTED_V{schema_version}_MEMORY"),
                        expected_revision=1,
                    )
                self.assertEqual(output.read_bytes(), markdown_before_rejected_update)
                self.assertEqual(
                    self.config.state.read_bytes(),
                    database_before_rejected_update,
                )
                self.assertEqual(
                    self.config.state.stat().st_mtime_ns,
                    database_mtime_before_rejected_update,
                )
                update_conversation(
                    self.config,
                    conversation_id,
                    update_payload(f"PROMOTED_V{schema_version}_MEMORY"),
                    expected_revision=1,
                    confirm_legacy_promotion=True,
                )
                promoted_metadata = frontmatter(
                    output.read_text(encoding="utf-8")
                )
                self.assertEqual(promoted_metadata["schema_version"], 3)
                promoted_result = conversation_module.get_conversation(
                    self.config, conversation_id
                )
                self.assertEqual(promoted_result["revision"], 2)
                self.assertEqual(
                    promoted_result["editable"],
                    update_payload(f"PROMOTED_V{schema_version}_MEMORY"),
                )

    def test_legacy_delete_does_not_parse_ambiguous_editable_body(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        record = next(
            item
            for item in list_conversations(self.config)
            if item["conversation_id"] == conversation_id
        )
        ambiguous = legacy_conversation_markdown(
            schema_version=2,
            conversation_id=conversation_id,
            created_at=str(record["created_at"]),
            updated_at=str(record["updated_at"]),
        ).replace(
            "첫 번째 연구 대화의 최초 요약\n\n## 사용자의 생각",
            (
                "첫 번째 연구 대화의 최초 요약\n\n"
                "## 결정된 사항\n\n- 요약 속 제목 같은 목록\n\n"
                "## 사용자의 생각"
            ),
            1,
        )
        output.write_text(ambiguous, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "결정된 사항 구역이 모호"):
            conversation_module.get_conversation(self.config, conversation_id)

        result = delete_conversation(
            self.config,
            conversation_id,
            expected_revision=1,
        )

        self.assertEqual(result["deleted_markdown"], record["path"])
        self.assertFalse(output.exists())
        self.assertIsNone(self._database_record(conversation_id))

    def test_cli_legacy_promotion_requires_explicit_review_flag(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        record = next(
            item
            for item in list_conversations(self.config)
            if item["conversation_id"] == conversation_id
        )
        output.write_text(
            legacy_conversation_markdown(
                schema_version=2,
                conversation_id=conversation_id,
                created_at=str(record["created_at"]),
                updated_at=str(record["updated_at"]),
            ),
            encoding="utf-8",
        )
        before = output.read_bytes()

        rejected = self.run_cli(
            "conversation-update",
            conversation_id,
            "--expected-revision",
            "1",
            input_payload=update_payload("CLI_LEGACY_REJECTED"),
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("confirm_legacy_promotion", rejected.stderr)
        self.assertEqual(output.read_bytes(), before)

        promoted = self.run_cli(
            "conversation-update",
            conversation_id,
            "--expected-revision",
            "1",
            "--confirm-legacy-promotion",
            input_payload=update_payload("CLI_LEGACY_PROMOTED"),
        )
        self.assertEqual(promoted.returncode, 0, promoted.stderr)
        self.assertEqual(
            frontmatter(output.read_text(encoding="utf-8"))["schema_version"],
            3,
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

    def test_update_promotes_v1_markdown_to_v3_and_preserves_immutable_fields(
        self,
    ) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        current = output.read_text(encoding="utf-8")
        current_metadata = frontmatter(current)
        output.write_text(
            legacy_conversation_markdown(
                schema_version=1,
                conversation_id=conversation_id,
                created_at=str(current_metadata["created_at"]),
                updated_at=str(current_metadata["updated_at"]),
            ),
            encoding="utf-8",
        )
        legacy_transcript = transcript_block(output.read_text(encoding="utf-8"))

        result = update_conversation(
            self.config,
            conversation_id,
            update_payload("PROMOTED_V1_MEMORY"),
            expected_revision=1,
            confirm_legacy_promotion=True,
        )

        promoted = output.read_text(encoding="utf-8")
        promoted_metadata = frontmatter(promoted)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(promoted_metadata["schema_version"], 3)
        self.assertEqual(promoted_metadata["revision"], 2)
        self.assertEqual(promoted_metadata["id"], current_metadata["id"])
        self.assertEqual(promoted_metadata["scope"], current_metadata["scope"])
        self.assertEqual(
            promoted_metadata["created_at"], current_metadata["created_at"]
        )
        self.assertEqual(transcript_block(promoted), legacy_transcript)
        self.assertEqual(result["path"], str(output.relative_to(self.project)))
        self.assertIn("PROMOTED_V1_MEMORY", promoted)

    def test_future_markdown_schema_blocks_update_and_delete(self) -> None:
        output, _, conversation_id, _ = self.save_two_conversations()
        current = output.read_text(encoding="utf-8")
        schema_version = frontmatter(current)["schema_version"]
        future = current.replace(
            f"schema_version: {schema_version}\n", "schema_version: 999\n", 1
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
