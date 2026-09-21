from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from .config import Config
from .safety import (
    atomic_text,
    is_within,
    reject_linked_file,
    require_owned_path,
    staged_owned_file_removal,
)
from .state import LibraryState, now


VALID_SCOPES = {"last-exchange", "current-topic", "entire-conversation", "custom"}
VALID_ROLES = {"user", "assistant"}
VALID_CAPTURE_STATUSES = {"complete", "partial"}
CONVERSATION_SCHEMA_VERSION = 2
UPDATE_FIELDS = {
    "title",
    "summary",
    "tags",
    "aliases",
    "user_points",
    "decisions",
    "unverified",
    "open_questions",
    "related_documents",
}
TRANSCRIPT_HEADING = "## 선택 범위 원문\n\n"


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key}는 문자열 배열이어야 합니다")
    return [item.strip() for item in value if item.strip()]


def _section(title: str, items: list[str]) -> str:
    if not items:
        return ""
    return f"## {title}\n\n" + "\n".join(f"- {item}" for item in items) + "\n\n"


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title이 필요합니다")
    scope = payload.get("scope")
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope는 다음 중 하나여야 합니다: {', '.join(sorted(VALID_SCOPES))}")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary가 필요합니다")
    transcript = payload.get("transcript")
    if not isinstance(transcript, list) or not transcript:
        raise ValueError("선택한 범위의 transcript가 필요합니다")
    for message in transcript:
        if not isinstance(message, dict):
            raise ValueError("transcript 항목은 객체여야 합니다")
        if message.get("role") not in VALID_ROLES:
            raise ValueError("transcript role은 user 또는 assistant여야 합니다")
        if (
            not isinstance(message.get("content"), str)
            or not message["content"].strip()
        ):
            raise ValueError("transcript content가 비어 있습니다")
    capture_status = payload.get("capture_status")
    if capture_status not in VALID_CAPTURE_STATUSES:
        raise ValueError("capture_status는 complete 또는 partial이어야 합니다")
    capture_note = payload.get("capture_note", "")
    if not isinstance(capture_note, str):
        raise ValueError("capture_note는 문자열이어야 합니다")
    if capture_status == "partial" and not capture_note.strip():
        raise ValueError("부분 저장에는 누락 범위를 설명하는 capture_note가 필요합니다")
    return {
        **payload,
        "title": title.strip(),
        "summary": summary.strip(),
        "tags": _string_list(payload, "tags"),
        "aliases": _string_list(payload, "aliases"),
        "user_points": _string_list(payload, "user_points"),
        "decisions": _string_list(payload, "decisions"),
        "unverified": _string_list(payload, "unverified"),
        "open_questions": _string_list(payload, "open_questions"),
        "related_documents": _string_list(payload, "related_documents"),
        "language": _string_list(
            {"language": payload.get("language", ["ko"])}, "language"
        ),
        "status": _string_list(
            {"status": payload.get("status", ["research-note"])}, "status"
        ),
        "capture_status": capture_status,
        "capture_note": capture_note.strip(),
    }


def _validate_update_payload(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("대화 수정 payload의 최상위 값은 객체여야 합니다")
    keys = set(raw)
    missing = sorted(UPDATE_FIELDS - keys)
    extra = sorted(keys - UPDATE_FIELDS)
    if missing:
        raise ValueError("대화 수정 payload에 필요한 값이 없습니다: " + ", ".join(missing))
    if extra:
        raise ValueError("대화 수정 payload에 허용되지 않은 값이 있습니다: " + ", ".join(extra))

    title = raw["title"]
    summary = raw["summary"]
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title이 필요합니다")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary가 필요합니다")
    return {
        "title": title.strip(),
        "summary": summary.strip(),
        "tags": _string_list(raw, "tags"),
        "aliases": _string_list(raw, "aliases"),
        "user_points": _string_list(raw, "user_points"),
        "decisions": _string_list(raw, "decisions"),
        "unverified": _string_list(raw, "unverified"),
        "open_questions": _string_list(raw, "open_questions"),
        "related_documents": _string_list(raw, "related_documents"),
    }


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("저장된 대화 Markdown에 frontmatter가 없습니다")
    closing = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        ),
        None,
    )
    if closing is None:
        raise ValueError("저장된 대화 Markdown의 frontmatter가 닫히지 않았습니다")

    metadata: dict[str, Any] = {}
    for line in lines[1:closing]:
        key, separator, raw_value = line.rstrip("\r\n").partition(":")
        if not separator or not key:
            raise ValueError("저장된 대화 Markdown의 frontmatter가 올바르지 않습니다")
        if key in metadata:
            raise ValueError(f"저장된 대화 Markdown에 {key}가 중복되어 있습니다")
        try:
            metadata[key] = json.loads(raw_value.strip())
        except json.JSONDecodeError as error:
            raise ValueError(
                f"저장된 대화 Markdown의 {key} 값이 올바르지 않습니다"
            ) from error
    return metadata, "".join(lines[closing + 1 :]).lstrip("\r\n")


def _transcript_block(body: str) -> str:
    marker = body.rfind(TRANSCRIPT_HEADING)
    if marker < 0:
        raise ValueError("저장된 대화 Markdown에서 선택 범위 원문을 찾을 수 없습니다")
    transcript = body[marker:]
    if not transcript[len(TRANSCRIPT_HEADING) :].strip():
        raise ValueError("저장된 대화 Markdown의 선택 범위 원문이 비어 있습니다")
    return transcript


def _render_transcript(transcript: list[dict[str, str]]) -> str:
    text = TRANSCRIPT_HEADING
    for message in transcript:
        role = "사용자" if message["role"] == "user" else "Codex"
        quoted = "\n".join(
            f"> {line}" if line else ">" for line in message["content"].splitlines()
        )
        text += f"### {role}\n\n{quoted}\n\n"
    return text


def _render_record(
    metadata: dict[str, Any], payload: dict[str, Any], transcript: str
) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(
        [
            "---",
            "",
            f"# {payload['title']}",
            "",
            "## 검색용 요약",
            "",
            payload["summary"],
            "",
        ]
    )
    text = "\n".join(lines)
    if metadata["transcript_capture"] == "partial":
        text += (
            "## 원문 보존 범위\n\n"
            "이 기록은 일부 원문만 포함합니다. "
            + str(metadata["capture_note"])
            + "\n\n"
        )
    text += _section("사용자의 생각", payload["user_points"])
    text += _section("결정된 사항", payload["decisions"])
    text += _section("검증되지 않은 생각", payload["unverified"])
    text += _section("미해결 질문", payload["open_questions"])
    text += transcript
    return text.rstrip() + "\n"


def _conversation_output(
    config: Config, record: dict[str, Any], *, require_file: bool
) -> Path:
    raw_path = str(record.get("output_path") or "")
    relative = Path(raw_path)
    if not raw_path or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("SQLite의 대화 출력 경로가 올바른 상대 경로가 아닙니다")
    output = require_owned_path(
        config.root / relative,
        config.root,
        label="저장된 대화 Markdown 경로",
    )
    conversations_root = require_owned_path(
        config.conversations,
        config.root,
        label="대화 저장 폴더",
    )
    if not is_within(output, conversations_root):
        raise ValueError("SQLite의 대화 출력 경로가 대화 저장 폴더를 벗어났습니다")
    if output.exists():
        return reject_linked_file(output, config.root, label="저장된 대화 Markdown")
    if require_file:
        raise ValueError(f"저장된 대화 Markdown을 찾을 수 없습니다: {output}")
    return output


def _validated_record(
    config: Config,
    record: dict[str, Any],
    conversation_id: str,
) -> tuple[Path, str, dict[str, Any], str]:
    output = _conversation_output(config, record, require_file=True)
    text = output.read_text(encoding="utf-8")
    metadata, body = _frontmatter(text)
    schema_version = metadata.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version < 1
    ):
        raise ValueError("저장된 대화 Markdown의 schema_version이 올바르지 않습니다")
    if schema_version > CONVERSATION_SCHEMA_VERSION:
        raise ValueError(
            "현재 프로그램보다 새로운 대화 Markdown 스키마입니다: "
            f"{schema_version} > {CONVERSATION_SCHEMA_VERSION}"
        )
    if metadata.get("id") != conversation_id:
        raise ValueError("저장된 대화 Markdown의 ID가 SQLite 기록과 일치하지 않습니다")
    if metadata.get("type") != "conversation":
        raise ValueError("저장된 대화 Markdown의 종류가 conversation이 아닙니다")
    if metadata.get("scope") != record["scope"]:
        raise ValueError("저장된 대화 Markdown의 범위가 SQLite 기록과 일치하지 않습니다")
    if metadata.get("created_at") != record["created_at"]:
        raise ValueError("저장된 대화 Markdown의 생성 시각이 SQLite 기록과 일치하지 않습니다")
    capture_status = metadata.get("transcript_capture")
    capture_note = metadata.get("capture_note")
    if capture_status not in VALID_CAPTURE_STATUSES:
        raise ValueError("저장된 대화 Markdown의 원문 보존 상태가 올바르지 않습니다")
    if not isinstance(capture_note, str):
        raise ValueError("저장된 대화 Markdown의 원문 보존 설명이 올바르지 않습니다")
    if capture_status == "partial" and not capture_note.strip():
        raise ValueError("부분 저장된 대화 Markdown에 누락 범위 설명이 없습니다")

    database_revision = int(record["revision"])
    if schema_version == 1:
        if database_revision != 1:
            raise ValueError(
                "대화 Markdown과 SQLite의 revision이 일치하지 않습니다"
            )
    else:
        markdown_revision = metadata.get("revision")
        if (
            isinstance(markdown_revision, bool)
            or not isinstance(markdown_revision, int)
            or markdown_revision < 1
        ):
            raise ValueError("저장된 대화 Markdown의 revision이 올바르지 않습니다")
        if markdown_revision != database_revision:
            raise ValueError(
                "대화 Markdown과 SQLite의 revision이 일치하지 않습니다: "
                f"markdown={markdown_revision}, sqlite={database_revision}"
            )
        updated_at = metadata.get("updated_at")
        if not isinstance(updated_at, str) or not updated_at:
            raise ValueError("저장된 대화 Markdown의 updated_at이 올바르지 않습니다")
        if updated_at != record["updated_at"]:
            raise ValueError(
                "대화 Markdown과 SQLite의 updated_at이 일치하지 않습니다"
            )
    return output, text, metadata, _transcript_block(body)


def _existing_record_output(
    config: Config, record: dict[str, Any], conversation_id: str
) -> Path:
    """Validate an idempotent save without rewriting a legacy record."""
    output = _conversation_output(config, record, require_file=True)
    metadata, _ = _frontmatter(output.read_text(encoding="utf-8"))
    if metadata.get("id") != conversation_id:
        raise ValueError("저장된 대화 Markdown의 ID가 SQLite 기록과 일치하지 않습니다")
    return output


def _decoded_string_list(record: dict[str, Any], key: str) -> list[str]:
    try:
        value = json.loads(str(record[key]))
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"SQLite의 대화 {key} 값이 올바르지 않습니다") from error
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"SQLite의 대화 {key} 값이 문자열 배열이 아닙니다")
    return value


def save_conversation(config: Config, raw: dict[str, Any]) -> Path:
    if not isinstance(raw, dict):
        raise ValueError("대화 payload의 최상위 값은 객체여야 합니다")
    payload = _validate_payload(raw)

    created_at = payload.get("created_at") or now()
    if not isinstance(created_at, str):
        raise ValueError("created_at은 ISO 8601 문자열이어야 합니다")
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError as error:
        raise ValueError("created_at은 ISO 8601 형식이어야 합니다") from error

    identity = hashlib.sha256(
        json.dumps(
            {
                "title": payload["title"],
                "created_at": created_at,
                "transcript": payload["transcript"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    canonical_id = f"conversation-{created:%Y%m%d}-{identity}"
    legacy_id = f"conversation-{created:%Y%m%d}-{identity[:12]}"
    canonical_output = (
        config.conversations
        / f"{created:%Y}"
        / f"{created:%m}"
        / f"{created:%d}-{identity}.md"
    )

    with LibraryState(config.state, config.root) as state:
        current = state.get_conversation(canonical_id)
        legacy = state.get_conversation(legacy_id)
        if current is not None:
            return _existing_record_output(config, current, canonical_id)
        if legacy is not None:
            return _existing_record_output(config, legacy, legacy_id)

        conversation_id = canonical_id
        output = canonical_output
        if output.exists():
            output = reject_linked_file(
                output, config.root, label="기존 대화 Markdown"
            )
            existing_metadata, _ = _frontmatter(output.read_text(encoding="utf-8"))
            if existing_metadata.get("id") != conversation_id:
                raise ValueError(
                    "기존 대화 Markdown이 현재 대화 ID와 일치하지 않습니다"
                )

        updated_at = created_at
        revision = 1
        metadata = {
            "schema_version": CONVERSATION_SCHEMA_VERSION,
            "id": conversation_id,
            "type": "conversation",
            "title": payload["title"],
            "created_at": created_at,
            "updated_at": updated_at,
            "revision": revision,
            "language": payload["language"],
            "scope": payload["scope"],
            "tags": payload["tags"],
            "aliases": payload["aliases"],
            "status": payload["status"],
            "related_documents": payload["related_documents"],
            "transcript_capture": payload["capture_status"],
            "capture_note": payload["capture_note"],
        }
        text = _render_record(
            metadata, payload, _render_transcript(payload["transcript"])
        )
        relative = str(output.relative_to(config.root))
        state.register_conversation(
            conversation_id=conversation_id,
            output_path=relative,
            title=payload["title"],
            scope=payload["scope"],
            created_at=created_at,
            updated_at=updated_at,
            revision=revision,
            tags=payload["tags"],
            aliases=payload["aliases"],
        )
        atomic_text(output, text, config.root)
    return output


def list_conversations(config: Config) -> list[dict[str, Any]]:
    with LibraryState(config.state, config.root) as state:
        records = state.conversations()
    result: list[dict[str, Any]] = []
    for record in records:
        output = _conversation_output(config, record, require_file=False)
        result.append(
            {
                "conversation_id": record["conversation_id"],
                "title": record["title"],
                "scope": record["scope"],
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
                "revision": int(record["revision"]),
                "tags": _decoded_string_list(record, "tags"),
                "aliases": _decoded_string_list(record, "aliases"),
                "path": str(output.relative_to(config.root)),
                "available": output.is_file(),
            }
        )
    return result


def update_conversation(
    config: Config,
    conversation_id: str,
    raw: dict[str, Any],
    *,
    expected_revision: int,
) -> dict[str, Any]:
    if expected_revision < 1:
        raise ValueError("expected_revision은 1 이상이어야 합니다")
    payload = _validate_update_payload(raw)
    with LibraryState(config.state, config.root) as state:
        state.begin_immediate()
        record = state.get_conversation(conversation_id)
        if record is None:
            raise ValueError(f"저장된 대화를 찾을 수 없습니다: {conversation_id}")
        current_revision = int(record["revision"])
        if current_revision != expected_revision:
            raise ValueError(
                "저장된 대화가 다른 작업에서 변경되었습니다. 목록을 다시 확인하세요: "
                f"expected={expected_revision}, current={current_revision}"
            )
        output, existing_text, metadata, transcript = _validated_record(
            config, record, conversation_id
        )
        revision = current_revision + 1
        updated_at = now()
        updated_metadata = {
            **metadata,
            "schema_version": CONVERSATION_SCHEMA_VERSION,
            "title": payload["title"],
            "updated_at": updated_at,
            "revision": revision,
            "tags": payload["tags"],
            "aliases": payload["aliases"],
            "related_documents": payload["related_documents"],
        }
        updated_text = _render_record(updated_metadata, payload, transcript)
        wrote_markdown = False
        try:
            state.update_conversation(
                conversation_id,
                title=payload["title"],
                updated_at=updated_at,
                revision=revision,
                expected_revision=expected_revision,
                tags=payload["tags"],
                aliases=payload["aliases"],
            )
            atomic_text(output, updated_text, config.root)
            wrote_markdown = True
            state.commit()
        except BaseException:
            if wrote_markdown:
                atomic_text(output, existing_text, config.root)
            raise
    return {
        "conversation_id": conversation_id,
        "path": str(output.relative_to(config.root)),
        "revision": revision,
        "updated_at": updated_at,
    }


def delete_conversation(
    config: Config, conversation_id: str, *, expected_revision: int
) -> dict[str, Any]:
    if expected_revision < 1:
        raise ValueError("expected_revision은 1 이상이어야 합니다")
    with LibraryState(config.state, config.root) as state:
        state.begin_immediate()
        record = state.get_conversation(conversation_id)
        if record is None:
            raise ValueError(f"저장된 대화를 찾을 수 없습니다: {conversation_id}")
        current_revision = int(record["revision"])
        if current_revision != expected_revision:
            raise ValueError(
                "저장된 대화가 다른 작업에서 변경되었습니다. 목록을 다시 확인하세요: "
                f"expected={expected_revision}, current={current_revision}"
            )
        output = _conversation_output(config, record, require_file=False)
        relative = str(output.relative_to(config.root))
        markdown_was_present = output.is_file()
        if markdown_was_present:
            _validated_record(config, record, conversation_id)
            removal = staged_owned_file_removal(
                output, config.root, label="삭제할 대화 Markdown"
            )
        else:
            removal = nullcontext(output)
        with removal:
            state.delete_conversation(
                conversation_id, expected_revision=expected_revision
            )
            state.commit()
    return {
        "conversation_id": conversation_id,
        "deleted_markdown": relative if markdown_was_present else None,
        "missing_markdown": not markdown_was_present,
        "codex_conversation_deleted": False,
        "originals_deleted": False,
        "pdf_markdown_deleted": False,
    }
