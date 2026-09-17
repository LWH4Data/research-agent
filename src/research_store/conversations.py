from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .config import Config
from .safety import atomic_text, reject_linked_file
from .state import LibraryState, now


VALID_SCOPES = {"last-exchange", "current-topic", "entire-conversation", "custom"}
VALID_ROLES = {"user", "assistant"}
VALID_CAPTURE_STATUSES = {"complete", "partial"}


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key}는 문자열 배열이어야 합니다")
    return [item.strip() for item in value if item.strip()]


def _legacy_slug(title: str) -> str:
    """Reproduce the filename used before full conversation hashes."""
    value = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-").casefold()
    return value[:64] or "conversation"


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
        if not isinstance(message.get("content"), str) or not message["content"].strip():
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
        "capture_status": capture_status,
        "capture_note": capture_note.strip(),
    }


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
    legacy_output = (
        config.conversations
        / f"{created:%Y}"
        / f"{created:%m}"
        / f"{created:%d}-{_legacy_slug(payload['title'])}-{identity[:6]}.md"
    )

    with LibraryState(config.state, config.root) as state:
        current = state.get_conversation(canonical_id)
        legacy = state.get_conversation(legacy_id)
        if current is not None:
            conversation_id = canonical_id
            output = canonical_output
            expected_relative = str(canonical_output.relative_to(config.root))
            if current["output_path"] != expected_relative:
                raise ValueError("SQLite의 대화 출력 경로가 예상 경로와 일치하지 않습니다")
        elif legacy is not None:
            # Keep a legacy record at its original path. This avoids orphaning
            # searchable Markdown or rewriting unrelated content during an upgrade.
            conversation_id = legacy_id
            output = legacy_output
            expected_relative = str(legacy_output.relative_to(config.root))
            if legacy["output_path"] != expected_relative:
                raise ValueError("SQLite의 기존 대화 경로가 예상 경로와 일치하지 않습니다")
        else:
            conversation_id = canonical_id
            output = canonical_output

        metadata = {
            "schema_version": 1,
            "id": conversation_id,
            "type": "conversation",
            "title": payload["title"],
            "created_at": created_at,
            "language": payload.get("language", ["ko"]),
            "scope": payload["scope"],
            "tags": payload["tags"],
            "aliases": payload["aliases"],
            "status": payload.get("status", ["research-note"]),
            "related_documents": payload.get("related_documents", []),
            "transcript_capture": payload["capture_status"],
            "capture_note": payload["capture_note"],
        }
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
        if payload["capture_status"] == "partial":
            text += (
                "## 원문 보존 범위\n\n"
                "이 기록은 일부 원문만 포함합니다. "
                + payload["capture_note"]
                + "\n\n"
            )
        text += _section("사용자의 생각", payload["user_points"])
        text += _section("결정된 사항", payload["decisions"])
        text += _section("검증되지 않은 생각", payload["unverified"])
        text += _section("미해결 질문", payload["open_questions"])
        text += "## 선택 범위 원문\n\n"
        for message in payload["transcript"]:
            role = "사용자" if message["role"] == "user" else "Codex"
            quoted = "\n".join(
                f"> {line}" if line else ">"
                for line in message["content"].splitlines()
            )
            text += f"### {role}\n\n{quoted}\n\n"

        if output.exists():
            output = reject_linked_file(
                output, config.root, label="기존 대화 Markdown"
            )
            existing = output.read_text(encoding="utf-8")
            header = existing.split("---", 2)
            expected_id = f"id: {json.dumps(conversation_id, ensure_ascii=False)}"
            if len(header) < 3 or header[1].splitlines().count(expected_id) != 1:
                raise ValueError(
                    "기존 대화 Markdown이 현재 대화 ID와 일치하지 않습니다"
                )

        relative = str(output.relative_to(config.root))
        state.register_conversation(
            conversation_id=conversation_id,
            output_path=relative,
            title=payload["title"],
            scope=payload["scope"],
            created_at=created_at,
            tags=payload["tags"],
            aliases=payload["aliases"],
        )
        atomic_text(output, text.rstrip() + "\n", config.root)
    return output
