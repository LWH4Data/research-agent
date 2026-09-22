from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from .config import Config
from .locking import conversation_lock
from .safety import (
    atomic_text,
    is_within,
    reject_linked_file,
    require_owned_path,
    unlink_owned_file,
)
from .state import LibraryState, now


VALID_SCOPES = {"last-exchange", "current-topic", "entire-conversation", "custom"}
VALID_ROLES = {"user", "assistant"}
VALID_CAPTURE_STATUSES = {"complete", "partial"}
CONVERSATION_SCHEMA_VERSION = 3
EDITABLE_FIELDS = (
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
UPDATE_FIELDS = frozenset(EDITABLE_FIELDS)
TRANSCRIPT_HEADING = "## 선택 범위 원문\n\n"
LEGACY_SECTION_HEADINGS = (
    ("사용자의 생각", "user_points"),
    ("결정된 사항", "decisions"),
    ("검증되지 않은 생각", "unverified"),
    ("미해결 질문", "open_questions"),
)


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
    # Split only on the physical newline delimiter. str.splitlines() also
    # treats Unicode separators such as U+2028 as line boundaries, but those
    # characters are valid inside JSON strings written with ensure_ascii=False.
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        raise ValueError("저장된 대화 Markdown에 frontmatter가 없습니다")
    closing = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.rstrip("\r") == "---"
        ),
        None,
    )
    if closing is None:
        raise ValueError("저장된 대화 Markdown의 frontmatter가 닫히지 않았습니다")

    metadata: dict[str, Any] = {}
    for line in lines[1:closing]:
        key, separator, raw_value = line.rstrip("\r").partition(":")
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
    return metadata, "\n".join(lines[closing + 1 :]).lstrip("\r\n")


def _read_text_exact(path: Path) -> str:
    """Read stored Markdown without universal-newline translation."""
    with path.open("r", encoding="utf-8", newline="") as file:
        return file.read()


def _transcript_block(body: str) -> str:
    marker = body.rfind(TRANSCRIPT_HEADING)
    if marker < 0:
        raise ValueError("저장된 대화 Markdown에서 선택 범위 원문을 찾을 수 없습니다")
    transcript = body[marker:]
    if not transcript[len(TRANSCRIPT_HEADING) :].strip():
        raise ValueError("저장된 대화 Markdown의 선택 범위 원문이 비어 있습니다")
    return transcript


def _legacy_transcript_block(body: str) -> str:
    occurrences = body.count(TRANSCRIPT_HEADING)
    if occurrences != 1:
        if occurrences == 0:
            raise ValueError(
                "기존 대화 Markdown에서 선택 범위 원문을 찾을 수 없습니다"
            )
        raise ValueError("기존 대화 Markdown의 선택 범위 원문 구역이 모호합니다")

    transcript = body[body.index(TRANSCRIPT_HEADING) :]
    _validate_legacy_transcript_roles(transcript)
    return transcript


def _validate_legacy_transcript_roles(transcript: str) -> None:
    lines = transcript[len(TRANSCRIPT_HEADING) :].split("\n")
    position = 0
    role_count = 0
    role_headings = {"### 사용자", "### Codex"}

    while position < len(lines):
        if all(not line for line in lines[position:]):
            break
        if lines[position] not in role_headings:
            raise ValueError(
                "기존 대화 Markdown의 원문 역할 블록이 올바르지 않습니다"
            )
        role_count += 1
        position += 1
        if position >= len(lines) or lines[position] != "":
            raise ValueError(
                "기존 대화 Markdown의 원문 역할 블록이 올바르지 않습니다"
            )
        position += 1

        quoted: list[str] = []
        while position < len(lines):
            line = lines[position]
            if line == ">":
                quoted.append("")
            elif line.startswith("> "):
                quoted.append(line[2:])
            else:
                break
            position += 1
        if not quoted or not "\n".join(quoted).strip():
            raise ValueError(
                "기존 대화 Markdown의 원문 역할 블록이 비어 있거나 "
                "인용 형식이 아닙니다"
            )
        if position >= len(lines) or lines[position] != "":
            raise ValueError(
                "기존 대화 Markdown의 원문 역할 블록 경계가 올바르지 않습니다"
            )
        position += 1

    if role_count == 0:
        raise ValueError("기존 대화 Markdown의 원문 역할 블록이 없습니다")


def _render_transcript(transcript: list[dict[str, str]]) -> str:
    text = TRANSCRIPT_HEADING
    for message in transcript:
        role = "사용자" if message["role"] == "user" else "Codex"
        quoted = "\n".join(
            f"> {line}" if line else ">" for line in message["content"].split("\n")
        )
        text += f"### {role}\n\n{quoted}\n\n"
    return text


def _transcript_sha256(transcript: str) -> str:
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()


def _editable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload[key] for key in EDITABLE_FIELDS}


def _render_editable_body(metadata: dict[str, Any], payload: dict[str, Any]) -> str:
    text = (
        f"# {payload['title']}\n\n"
        "## 검색용 요약\n\n"
        f"{payload['summary']}\n\n"
    )
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
    return text


def _render_record(
    metadata: dict[str, Any], payload: dict[str, Any], transcript: str
) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return (
        "\n".join(lines)
        + "\n\n"
        + _render_editable_body(metadata, payload)
        + transcript
    )


def _legacy_section_items(body: str, heading: str) -> list[str]:
    marker = f"## {heading}\n\n"
    if marker not in body:
        return []
    if body.count(marker) != 1:
        raise ValueError(f"기존 대화 Markdown의 {heading} 구역이 모호합니다")
    start = body.index(marker) + len(marker)
    ends = [
        position
        for candidate, _ in LEGACY_SECTION_HEADINGS
        if (position := body.find(f"## {candidate}\n\n", start)) >= 0
    ]
    transcript_position = body.find(TRANSCRIPT_HEADING, start)
    if transcript_position >= 0:
        ends.append(transcript_position)
    content = body[start : min(ends) if ends else len(body)].strip("\n")
    if not content:
        return []

    items: list[str] = []
    for line in content.splitlines():
        if line.startswith("- "):
            items.append(line[2:])
        elif items:
            items[-1] += "\n" + line
        else:
            raise ValueError(
                f"기존 대화 Markdown의 {heading} 목록 형식이 올바르지 않습니다"
            )
    return [item.rstrip("\n") for item in items]


def _legacy_editable(metadata: dict[str, Any], body: str) -> dict[str, Any]:
    summary_marker = "## 검색용 요약\n\n"
    if body.count(summary_marker) != 1:
        raise ValueError("기존 대화 Markdown의 검색용 요약 구역이 모호합니다")
    summary_start = body.index(summary_marker) + len(summary_marker)
    boundary_markers = [
        "## 원문 보존 범위\n\n",
        *(f"## {heading}\n\n" for heading, _ in LEGACY_SECTION_HEADINGS),
        TRANSCRIPT_HEADING,
    ]
    ends = [
        position
        for marker in boundary_markers
        if (position := body.find(marker, summary_start)) >= 0
    ]
    summary = body[summary_start : min(ends) if ends else len(body)].strip("\n")
    candidate = {
        "title": metadata.get("title"),
        "summary": summary,
        "tags": metadata.get("tags"),
        "aliases": metadata.get("aliases"),
        "user_points": _legacy_section_items(body, "사용자의 생각"),
        "decisions": _legacy_section_items(body, "결정된 사항"),
        "unverified": _legacy_section_items(body, "검증되지 않은 생각"),
        "open_questions": _legacy_section_items(body, "미해결 질문"),
        "related_documents": metadata.get("related_documents"),
    }
    return _validate_update_payload(candidate)


def _validated_editable(
    metadata: dict[str, Any], body: str, record: dict[str, Any]
) -> dict[str, Any]:
    schema_version = int(metadata["schema_version"])
    if schema_version < 3:
        editable = _legacy_editable(metadata, body)
    else:
        raw_editable = metadata.get("editable")
        editable = _validate_update_payload(raw_editable)
        if raw_editable != editable:
            raise ValueError("저장된 대화 Markdown의 editable 값이 정규 형식이 아닙니다")
        for key in ("title", "tags", "aliases", "related_documents"):
            if metadata.get(key) != editable[key]:
                raise ValueError(
                    f"저장된 대화 Markdown의 {key} 값이 editable과 일치하지 않습니다"
                )

    if editable["title"] != record["title"]:
        raise ValueError("대화 Markdown과 SQLite의 title이 일치하지 않습니다")
    for key in ("tags", "aliases"):
        if editable[key] != _decoded_string_list(record, key):
            raise ValueError(f"대화 Markdown과 SQLite의 {key} 값이 일치하지 않습니다")
    return editable


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
    *,
    include_content: bool = True,
) -> tuple[Path, str, dict[str, Any], dict[str, Any] | None, str | None]:
    output = _conversation_output(config, record, require_file=True)
    text = _read_text_exact(output)
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
    if not include_content:
        return output, text, metadata, None, None
    transcript = (
        _legacy_transcript_block(body)
        if schema_version < 3
        else _transcript_block(body)
    )
    if schema_version >= 3:
        transcript_hash = metadata.get("transcript_sha256")
        if transcript_hash != _transcript_sha256(transcript):
            raise ValueError(
                "저장된 대화 Markdown의 원문 해시가 실제 원문과 일치하지 않습니다"
            )
    editable = _validated_editable(metadata, body, record)
    if schema_version >= 3:
        editable_body = body[: len(body) - len(transcript)]
        if editable_body != _render_editable_body(metadata, editable):
            raise ValueError(
                "저장된 대화 Markdown 본문이 editable 값과 일치하지 않습니다"
            )
    return output, text, metadata, editable, transcript


def _existing_record_output(
    config: Config,
    record: dict[str, Any],
    conversation_id: str,
    payload: dict[str, Any],
) -> Path:
    """Validate an idempotent save without rewriting the existing record."""
    output = _conversation_output(config, record, require_file=True)
    metadata, _ = _frontmatter(_read_text_exact(output))
    schema_version = metadata.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version < 1
    ):
        raise ValueError("저장된 대화 Markdown의 schema_version이 올바르지 않습니다")

    if schema_version >= 3:
        output, _, metadata, _, transcript = _validated_record(
            config, record, conversation_id
        )
        assert transcript is not None
        if transcript != _render_transcript(payload["transcript"]):
            raise ValueError(
                "기존 대화 Markdown의 원문이 동일 저장 요청과 일치하지 않습니다"
            )
    else:
        # Older records did not contain enough structured data for a safe full
        # content validation. Preserve compatibility while still validating
        # their path, identifier, schema, revision, and immutable metadata.
        output, _, metadata, _, _ = _validated_record(
            config,
            record,
            conversation_id,
            include_content=False,
        )

    immutable_expectations = {
        "created_at": payload["created_at"],
        "scope": payload["scope"],
        "language": payload["language"],
        "status": payload["status"],
        "transcript_capture": payload["capture_status"],
        "capture_note": payload["capture_note"],
    }
    for key, expected in immutable_expectations.items():
        if metadata.get(key) != expected:
            raise ValueError(
                f"기존 대화 Markdown의 {key} 값이 동일 저장 요청과 일치하지 않습니다"
            )
    return output


def _decoded_string_list(record: dict[str, Any], key: str) -> list[str]:
    try:
        value = json.loads(str(record[key]))
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"SQLite의 대화 {key} 값이 올바르지 않습니다") from error
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"SQLite의 대화 {key} 값이 문자열 배열이 아닙니다")
    return value


def _markdown_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_snapshot(
    *,
    conversation_id: str,
    output_path: str,
    title: str,
    scope: str,
    created_at: str,
    updated_at: str,
    revision: int,
    tags: list[str],
    aliases: list[str],
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "output_path": output_path,
        "title": title,
        "scope": scope,
        "created_at": created_at,
        "updated_at": updated_at,
        "revision": revision,
        "tags": json.dumps(tags, ensure_ascii=False),
        "aliases": json.dumps(aliases, ensure_ascii=False),
    }


def _same_record(
    current: dict[str, Any] | None, expected: dict[str, Any] | None
) -> bool:
    if current is None or expected is None:
        return current is expected
    return current == expected


def _output_path_owner(state: LibraryState, output_path: str) -> str | None:
    row = state.connection.execute(
        "SELECT conversation_id FROM conversations WHERE output_path = ?",
        (output_path,),
    ).fetchone()
    return None if row is None else str(row["conversation_id"])


def _require_output_path_available(
    state: LibraryState, output_path: str, conversation_id: str
) -> None:
    owner = _output_path_owner(state, output_path)
    if owner is not None and owner != conversation_id:
        # Match the public error class SQLite previously raised at insert time,
        # while moving the check before the durable journal/file boundary.
        raise sqlite3.IntegrityError(
            "UNIQUE constraint failed: conversations.output_path"
        )


def _validate_journal_record(
    record: dict[str, Any],
    *,
    conversation_id: str,
    output_path: str,
    label: str,
) -> None:
    required = {
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
    if set(record) != required:
        raise RuntimeError(f"{label}의 필드 구성이 올바르지 않습니다")
    if record["conversation_id"] != conversation_id:
        raise RuntimeError(f"{label}의 대화 ID가 작업 기록과 일치하지 않습니다")
    if record["output_path"] != output_path:
        raise RuntimeError(f"{label}의 출력 경로가 작업 기록과 일치하지 않습니다")
    revision = record["revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise RuntimeError(f"{label}의 revision이 올바르지 않습니다")
    for key in ("title", "scope", "created_at", "updated_at", "tags", "aliases"):
        if not isinstance(record[key], str) or not record[key]:
            raise RuntimeError(f"{label}의 {key} 값이 올바르지 않습니다")
    _decoded_string_list(record, "tags")
    _decoded_string_list(record, "aliases")


def _validate_target_markdown(
    target: bytes,
    target_record: dict[str, Any],
    conversation_id: str,
) -> str:
    try:
        text = target.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuntimeError("대화 작업 기록의 Markdown이 UTF-8이 아닙니다") from error
    metadata, body = _frontmatter(text)
    expectations = {
        "schema_version": CONVERSATION_SCHEMA_VERSION,
        "id": conversation_id,
        "type": "conversation",
        "title": target_record["title"],
        "created_at": target_record["created_at"],
        "updated_at": target_record["updated_at"],
        "revision": target_record["revision"],
        "scope": target_record["scope"],
        "tags": _decoded_string_list(target_record, "tags"),
        "aliases": _decoded_string_list(target_record, "aliases"),
    }
    for key, expected in expectations.items():
        if metadata.get(key) != expected:
            raise RuntimeError(
                f"대화 작업 기록의 Markdown {key} 값이 목표 레코드와 일치하지 않습니다"
            )
    transcript = _transcript_block(body)
    if metadata.get("transcript_sha256") != _transcript_sha256(transcript):
        raise RuntimeError("대화 작업 기록의 원문 해시가 일치하지 않습니다")
    editable = _validated_editable(metadata, body, target_record)
    editable_body = body[: len(body) - len(transcript)]
    if editable_body != _render_editable_body(metadata, editable):
        raise RuntimeError("대화 작업 기록의 Markdown 본문이 올바르지 않습니다")
    return text


def _journal_output(config: Config, operation: dict[str, Any]) -> Path:
    record = operation.get("target_record") or operation.get("base_record") or {
        "output_path": operation.get("output_path")
    }
    output = _conversation_output(config, record, require_file=False)
    conversations_root = require_owned_path(
        config.conversations,
        config.root,
        label="대화 저장 폴더",
    )
    if output == conversations_root:
        raise RuntimeError("대화 작업의 출력 경로는 파일이어야 합니다")
    return output


def _validate_pending_operation(
    config: Config,
    state: LibraryState,
    operation: dict[str, Any],
) -> tuple[Path, str | None]:
    operation_type = operation.get("operation")
    conversation_id = operation.get("conversation_id")
    output_path = operation.get("output_path")
    if operation_type not in {"save", "update", "delete"}:
        raise RuntimeError("완료되지 않은 대화 작업의 종류가 올바르지 않습니다")
    if not isinstance(conversation_id, str) or not conversation_id:
        raise RuntimeError("완료되지 않은 대화 작업의 ID가 올바르지 않습니다")
    if not isinstance(output_path, str) or not output_path:
        raise RuntimeError("완료되지 않은 대화 작업의 경로가 올바르지 않습니다")

    base = operation.get("base_record")
    target = operation.get("target_record")
    if base is not None:
        if not isinstance(base, dict):
            raise RuntimeError("대화 작업의 기존 레코드가 올바르지 않습니다")
        _validate_journal_record(
            base,
            conversation_id=conversation_id,
            output_path=output_path,
            label="기존 대화 레코드",
        )
    if target is not None:
        if not isinstance(target, dict):
            raise RuntimeError("대화 작업의 목표 레코드가 올바르지 않습니다")
        _validate_journal_record(
            target,
            conversation_id=conversation_id,
            output_path=output_path,
            label="목표 대화 레코드",
        )

    expected_revision = operation.get("expected_revision")
    if operation_type == "save":
        if base is not None or target is None or expected_revision is not None:
            raise RuntimeError("저장 작업 기록의 상태 전이가 올바르지 않습니다")
        if int(target["revision"]) != 1:
            raise RuntimeError("저장 작업의 목표 revision은 1이어야 합니다")
    elif operation_type == "update":
        if base is None or target is None:
            raise RuntimeError("수정 작업 기록의 상태 전이가 올바르지 않습니다")
        if expected_revision != int(base["revision"]):
            raise RuntimeError("수정 작업의 기준 revision이 일치하지 않습니다")
        if int(target["revision"]) != int(base["revision"]) + 1:
            raise RuntimeError("수정 작업의 목표 revision이 올바르지 않습니다")
    else:
        if base is None or target is not None:
            raise RuntimeError("삭제 작업 기록의 상태 전이가 올바르지 않습니다")
        if expected_revision != int(base["revision"]):
            raise RuntimeError("삭제 작업의 기준 revision이 일치하지 않습니다")

    target_bytes = operation.get("target_markdown")
    target_hash = operation.get("target_markdown_sha256")
    target_text: str | None
    if operation_type == "delete":
        if target_bytes is not None or target_hash is not None:
            raise RuntimeError("삭제 작업에는 목표 Markdown이 없어야 합니다")
        target_text = None
    else:
        if not isinstance(target_bytes, bytes) or not isinstance(target_hash, str):
            raise RuntimeError("저장 또는 수정 작업의 목표 Markdown이 없습니다")
        if hashlib.sha256(target_bytes).hexdigest() != target_hash:
            raise RuntimeError("대화 작업 기록의 목표 Markdown 해시가 일치하지 않습니다")
        assert target is not None
        target_text = _validate_target_markdown(
            target_bytes, target, conversation_id
        )

    output = _journal_output(config, operation)
    if output.exists():
        output = reject_linked_file(
            output, config.root, label="복구할 대화 Markdown"
        )
    current_hash = _file_sha256(output)
    allowed_hashes = {
        operation.get("base_markdown_sha256"),
        target_hash,
    }
    if current_hash not in allowed_hashes:
        raise RuntimeError(
            "대화 작업을 복구할 수 없습니다. Markdown이 작업 준비 후 예상하지 "
            "못한 내용으로 변경되었습니다"
        )

    current_record = state.get_conversation(conversation_id)
    if not (
        _same_record(current_record, base) or _same_record(current_record, target)
    ):
        raise RuntimeError(
            "대화 작업을 복구할 수 없습니다. SQLite 레코드가 작업 준비 후 "
            "예상하지 못한 내용으로 변경되었습니다"
        )
    owner = _output_path_owner(state, output_path)
    if owner is not None and owner != conversation_id:
        raise RuntimeError(
            "대화 작업을 복구할 수 없습니다. Markdown 출력 경로가 다른 "
            "대화 레코드에 등록되어 있습니다"
        )
    return output, target_text


def _register_target_record(state: LibraryState, record: dict[str, Any]) -> None:
    state.register_conversation(
        conversation_id=str(record["conversation_id"]),
        output_path=str(record["output_path"]),
        title=str(record["title"]),
        scope=str(record["scope"]),
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
        revision=int(record["revision"]),
        tags=_decoded_string_list(record, "tags"),
        aliases=_decoded_string_list(record, "aliases"),
    )


def _roll_forward_pending(
    config: Config,
    state: LibraryState,
    operation: dict[str, Any],
) -> None:
    output, target_text = _validate_pending_operation(config, state, operation)
    if operation["operation"] == "delete":
        unlink_owned_file(
            output,
            config.root,
            label="삭제할 대화 Markdown",
            missing_ok=True,
        )
        if output.exists():  # pragma: no cover - defensive invariant
            raise RuntimeError("대화 Markdown 삭제를 완료하지 못했습니다")
    else:
        assert target_text is not None
        atomic_text(output, target_text, config.root)
        if _file_sha256(output) != operation["target_markdown_sha256"]:
            raise RuntimeError("대화 Markdown 쓰기 결과를 검증하지 못했습니다")

    state.begin_immediate()
    try:
        current_operation = state.get_pending_conversation_operation()
        if (
            current_operation is None
            or current_operation.get("operation_id") != operation.get("operation_id")
        ):
            raise RuntimeError("완료하려는 대화 작업 기록이 변경되었습니다")
        # Validate the database side again while holding SQLite's writer lock.
        _validate_pending_operation(config, state, current_operation)
        current_record = state.get_conversation(str(operation["conversation_id"]))
        target_record = operation.get("target_record")
        if target_record is None:
            if current_record is not None:
                state.delete_conversation(
                    str(operation["conversation_id"]),
                    expected_revision=int(current_record["revision"]),
                )
        else:
            _register_target_record(state, target_record)
        state.finish_conversation_operation(str(operation["operation_id"]))
        state.commit()
    except BaseException:
        if state.connection.in_transaction:
            state.connection.rollback()
        raise


def _recover_pending_with_state(config: Config, state: LibraryState) -> bool:
    operation = state.get_pending_conversation_operation()
    if operation is None:
        return False
    _roll_forward_pending(config, state, operation)
    return True


def _recover_pending_locked(config: Config) -> bool:
    # The common read path opens SQLite read-only so a healthy lookup cannot
    # change database bytes or timestamps. Only a discovered journal entry
    # switches to a writer connection to finish the approved operation.
    with LibraryState(config.state, config.root, read_only=True) as read_state:
        if read_state.get_pending_conversation_operation() is None:
            return False
    with LibraryState(config.state, config.root) as state:
        return _recover_pending_with_state(config, state)


def recover_conversations(config: Config, *, lock_held: bool = False) -> bool:
    """Finish one approved conversation operation left by an interruption."""

    if lock_held:
        return _recover_pending_locked(config)
    with conversation_lock(config.root):
        return _recover_pending_locked(config)


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
    payload["created_at"] = created_at

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

    with conversation_lock(config.root):
        with LibraryState(config.state, config.root) as state:
            _recover_pending_with_state(config, state)
            state.begin_immediate()
            current = state.get_conversation(canonical_id)
            legacy = state.get_conversation(legacy_id)
            if current is not None:
                output = _existing_record_output(
                    config, current, canonical_id, payload
                )
                state.connection.rollback()
                return output
            if legacy is not None:
                output = _existing_record_output(config, legacy, legacy_id, payload)
                state.connection.rollback()
                return output

            conversation_id = canonical_id
            output = canonical_output
            base_hash: str | None = None
            if output.exists():
                output = reject_linked_file(
                    output, config.root, label="기존 대화 Markdown"
                )
                existing_text = _read_text_exact(output)
                existing_metadata, _ = _frontmatter(existing_text)
                if existing_metadata.get("id") != conversation_id:
                    raise ValueError(
                        "기존 대화 Markdown이 현재 대화 ID와 일치하지 않습니다"
                    )
                base_hash = _markdown_sha256(existing_text)

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
            transcript = _render_transcript(payload["transcript"])
            metadata["editable"] = _editable_payload(payload)
            metadata["transcript_sha256"] = _transcript_sha256(transcript)
            text = _render_record(metadata, payload, transcript)
            relative = str(output.relative_to(config.root))
            _require_output_path_available(state, relative, conversation_id)
            target_record = _record_snapshot(
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
            operation = state.prepare_conversation_operation(
                operation_id=uuid.uuid4().hex,
                operation="save",
                conversation_id=conversation_id,
                output_path=relative,
                expected_revision=None,
                base_record=None,
                target_record=target_record,
                base_markdown_sha256=base_hash,
                target_markdown=text,
            )
            _roll_forward_pending(config, state, operation)
        return output


def list_conversations(config: Config) -> list[dict[str, Any]]:
    with conversation_lock(config.root):
        recover_conversations(config, lock_held=True)
        with LibraryState(config.state, config.root, read_only=True) as state:
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


def get_conversation(config: Config, conversation_id: str) -> dict[str, Any]:
    with conversation_lock(config.root):
        recover_conversations(config, lock_held=True)
        with LibraryState(config.state, config.root, read_only=True) as state:
            record = state.get_conversation(conversation_id)
            if record is None:
                raise ValueError(f"저장된 대화를 찾을 수 없습니다: {conversation_id}")
            output, _, metadata, editable, _ = _validated_record(
                config, record, conversation_id
            )
        assert editable is not None
        result = {
            "conversation_id": conversation_id,
            "path": str(output.relative_to(config.root)),
            "revision": int(record["revision"]),
            "updated_at": str(record["updated_at"]),
            "editable": editable,
            "immutable": {
                "scope": str(record["scope"]),
                "created_at": str(record["created_at"]),
                "transcript_capture": metadata["transcript_capture"],
                "capture_note": metadata["capture_note"],
            },
        }
        schema_version = int(metadata["schema_version"])
        if schema_version < 3:
            result["schema_version"] = schema_version
            result["migration_required"] = True
            result["editable_candidate"] = result.pop("editable")
        return result


def update_conversation(
    config: Config,
    conversation_id: str,
    raw: dict[str, Any],
    *,
    expected_revision: int,
    confirm_legacy_promotion: bool = False,
) -> dict[str, Any]:
    if expected_revision < 1:
        raise ValueError("expected_revision은 1 이상이어야 합니다")
    payload = _validate_update_payload(raw)
    with conversation_lock(config.root):
        recover_conversations(config, lock_held=True)
        if not confirm_legacy_promotion:
            with LibraryState(config.state, config.root, read_only=True) as read_state:
                preflight_record = read_state.get_conversation(conversation_id)
                if preflight_record is None:
                    raise ValueError(
                        f"저장된 대화를 찾을 수 없습니다: {conversation_id}"
                    )
                _, _, preflight_metadata, _, _ = _validated_record(
                    config,
                    preflight_record,
                    conversation_id,
                )
                if int(preflight_metadata["schema_version"]) < 3:
                    raise ValueError(
                        "이전 형식 대화는 복원된 아홉 필드를 확인한 뒤 "
                        "confirm_legacy_promotion으로 승격해야 합니다"
                    )

        with LibraryState(config.state, config.root) as state:
            state.begin_immediate()
            record = state.get_conversation(conversation_id)
            if record is None:
                raise ValueError(f"저장된 대화를 찾을 수 없습니다: {conversation_id}")
            current_revision = int(record["revision"])
            if current_revision != expected_revision:
                raise ValueError(
                    "저장된 대화가 다른 작업에서 변경되었습니다. 다시 조회하세요: "
                    f"expected={expected_revision}, current={current_revision}"
                )
            output, existing_text, metadata, _, transcript = _validated_record(
                config, record, conversation_id
            )
            if (
                int(metadata["schema_version"]) < 3
                and not confirm_legacy_promotion
            ):
                raise ValueError(
                    "이전 형식 대화는 복원된 아홉 필드를 확인한 뒤 "
                    "confirm_legacy_promotion으로 승격해야 합니다"
                )
            assert transcript is not None
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
                "editable": _editable_payload(payload),
                "transcript_sha256": _transcript_sha256(transcript),
            }
            updated_text = _render_record(updated_metadata, payload, transcript)
            relative = str(output.relative_to(config.root))
            target_record = {
                **record,
                "title": payload["title"],
                "updated_at": updated_at,
                "revision": revision,
                "tags": json.dumps(payload["tags"], ensure_ascii=False),
                "aliases": json.dumps(payload["aliases"], ensure_ascii=False),
            }
            operation = state.prepare_conversation_operation(
                operation_id=uuid.uuid4().hex,
                operation="update",
                conversation_id=conversation_id,
                output_path=relative,
                expected_revision=expected_revision,
                base_record=record,
                target_record=target_record,
                base_markdown_sha256=_markdown_sha256(existing_text),
                target_markdown=updated_text,
            )
            _roll_forward_pending(config, state, operation)
        return {
            "conversation_id": conversation_id,
            "path": relative,
            "revision": revision,
            "updated_at": updated_at,
        }


def delete_conversation(
    config: Config, conversation_id: str, *, expected_revision: int
) -> dict[str, Any]:
    if expected_revision < 1:
        raise ValueError("expected_revision은 1 이상이어야 합니다")
    with conversation_lock(config.root):
        with LibraryState(config.state, config.root) as state:
            _recover_pending_with_state(config, state)
            state.begin_immediate()
            record = state.get_conversation(conversation_id)
            if record is None:
                raise ValueError(f"저장된 대화를 찾을 수 없습니다: {conversation_id}")
            current_revision = int(record["revision"])
            if current_revision != expected_revision:
                raise ValueError(
                    "저장된 대화가 다른 작업에서 변경되었습니다. 다시 조회하세요: "
                    f"expected={expected_revision}, current={current_revision}"
                )
            output = _conversation_output(config, record, require_file=False)
            relative = str(output.relative_to(config.root))
            markdown_was_present = output.is_file()
            base_hash: str | None = None
            if markdown_was_present:
                _, existing_text, _, _, _ = _validated_record(
                    config,
                    record,
                    conversation_id,
                    include_content=False,
                )
                base_hash = _markdown_sha256(existing_text)
            operation = state.prepare_conversation_operation(
                operation_id=uuid.uuid4().hex,
                operation="delete",
                conversation_id=conversation_id,
                output_path=relative,
                expected_revision=expected_revision,
                base_record=record,
                target_record=None,
                base_markdown_sha256=base_hash,
                target_markdown=None,
            )
            _roll_forward_pending(config, state, operation)
        return {
            "conversation_id": conversation_id,
            "deleted_markdown": relative if markdown_was_present else None,
            "missing_markdown": not markdown_was_present,
            "codex_conversation_deleted": False,
            "originals_deleted": False,
            "pdf_markdown_deleted": False,
        }
