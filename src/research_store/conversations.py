from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from .config import Config
from .state import LibraryState, now


VALID_SCOPES = {"last-exchange", "current-topic", "entire-conversation", "custom"}
VALID_ROLES = {"user", "assistant"}


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key}는 문자열 배열이어야 합니다")
    return [item.strip() for item in value if item.strip()]


def _slug(title: str) -> str:
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
    }


def save_conversation(config: Config, payload_path: Path) -> Path:
    try:
        raw = json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"대화 payload를 읽을 수 없습니다: {error}") from error
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
    ).hexdigest()[:12]
    conversation_id = f"conversation-{created:%Y%m%d}-{identity}"
    output = (
        config.conversations
        / f"{created:%Y}"
        / f"{created:%m}"
        / f"{created:%d}-{_slug(payload['title'])}-{identity[:6]}.md"
    )

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
    text += _section("사용자의 생각", payload["user_points"])
    text += _section("결정된 사항", payload["decisions"])
    text += _section("검증되지 않은 생각", payload["unverified"])
    text += _section("미해결 질문", payload["open_questions"])
    text += "## 선택 범위 원문\n\n"
    for message in payload["transcript"]:
        role = "사용자" if message["role"] == "user" else "Codex"
        quoted = "\n".join(f"> {line}" if line else ">" for line in message["content"].splitlines())
        text += f"### {role}\n\n{quoted}\n\n"

    _atomic_text(output, text.rstrip() + "\n")
    with LibraryState(config.state) as state:
        try:
            relative = str(output.relative_to(config.root))
        except ValueError:
            relative = str(output)
        state.register_conversation(
            conversation_id=conversation_id,
            output_path=relative,
            title=payload["title"],
            scope=payload["scope"],
            created_at=created_at,
            tags=payload["tags"],
            aliases=payload["aliases"],
        )
    return output
