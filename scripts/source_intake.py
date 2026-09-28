"""Host orchestration for one confirmed source selection (stdlib only).

Registration and lifecycle writes use fixed launchers. This helper never reads
PDF contents or writes library state; an installer without Codex may only use
the existing registration primitive and must defer storage explicitly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


def _json_command(command: list[str], *, env: dict[str, str], payload: str | None = None) -> dict:
    result = subprocess.run(command, env=env, input=payload, stdout=subprocess.PIPE,
                            text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"제한 명령을 완료하지 못했습니다 (종료 코드 {result.returncode}).")
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("제한 명령의 응답 형식이 올바르지 않습니다.")
    return value


def _selection(receipt: dict, paths: list[Path]) -> list[dict]:
    selected, added = receipt.get("selected"), receipt.get("added")
    if (receipt.get("cancelled") is not False or not isinstance(selected, list)
            or not selected or not isinstance(added, list)):
        raise ValueError("선택한 폴더의 연결 결과를 확인할 수 없습니다.")
    ids, returned_paths = set(), []
    for row in selected:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", row["id"])
                or row["id"] in ids or row.get("access") != "read-only"
                or not isinstance(row.get("path"), str) or "\0" in row["path"]
                or not Path(row["path"]).is_absolute()):
            raise ValueError("연결 응답의 폴더 식별자가 올바르지 않습니다.")
        ids.add(row["id"])
        returned_paths.append(row["path"])
    expected_paths = list(dict.fromkeys(str(path.resolve()) for path in paths))
    if returned_paths != expected_paths or any(row not in selected for row in added):
        raise ValueError("연결 응답이 확인한 폴더 목록과 다릅니다.")
    return selected


def _request(value: dict, specification: dict, request_id: str | None = None) -> dict:
    rid = value.get("request_id")
    expected = {item["item_id"] for item in specification["items"]}
    if (not isinstance(rid, str) or not re.fullmatch(r"[0-9a-f]{32}", rid)
            or (request_id is not None and request_id != rid)
            or not isinstance(value.get("items"), dict)
            or not isinstance(value.get("links"), dict)
            or ("handoff" in value and not isinstance(value["handoff"], dict))
            or not expected.issubset(value["items"])
            or any(not isinstance(value["items"][item], dict) for item in expected)
            or not isinstance(value.get("state"), str)):
        raise ValueError("저장 접수 응답을 확인할 수 없습니다.")
    return value


def connect_sources(root: Path, paths: list[Path], *, codex: str | None,
                    sandbox_home: str, registration_only: bool = False,
                    installation: bool = False) -> tuple[dict, int]:
    """Return registration and processing outcomes separately, even on failure."""
    if not paths:
        return {"added": [], "selected": [], "cancelled": True,
                "processing": {"state": "not_started", "reason": "cancelled"}}, 0
    if any(not isinstance(path, Path) or not path.is_absolute() or "\0" in str(path)
           for path in paths):
        raise ValueError("확인한 절대 경로 목록이 필요합니다.")
    env = os.environ.copy()
    env["CODEX_HOME"] = sandbox_home
    response = {"added": [], "selected": [], "cancelled": False,
                "registration": "unknown", "processing": {"state": "not_started"}}
    if codex:
        register = [codex, "sandbox", "-P", "research-store", "-C", sandbox_home,
                    "--", str(root / "research-store"), "source-add", "--", *map(str, paths)]
    elif installation:
        register = [str(root / "research-store"), "source-add", "--", *map(str, paths)]
    else:
        response["processing"]["reason"] = "codex_unavailable"
        return response, 1
    try:
        registered = _json_command(register, env=env)
        selected = _selection(registered, paths)
    except (OSError, RuntimeError, ValueError) as error:
        response["error"] = str(error)
        return response, 1
    response.update(added=registered["added"], selected=selected, registration="registered")
    if registration_only:
        response["processing"] = {"state": "not_started", "reason": "registration_only"}
        return response, 0
    if not codex:
        response["processing"] = {"state": "deferred", "reason": "codex_unavailable"}
        return response, 0

    review = str(root / "resources/skills/research-library/scripts/research-review")
    specification = {"items": [{"item_id": f"source-{index}", "source_id": row["id"]}
                                for index, row in enumerate(selected, 1)]}
    processing = response["processing"] = {"state": "deferred", "reason": "intake_startup_failed"}
    try:
        key = _json_command([review, "key"], env=env)
        if (not isinstance(key.get("key"), str) or type(key.get("key_expires_at")) is not int
                or not re.fullmatch(r"vr2\." + str(key["key_expires_at"]) + r"\.[a-zA-Z0-9_-]{16,128}", key["key"])):
            raise ValueError("저장 요청 키를 확인할 수 없습니다.")
        retry = {"key": key["key"], "key_expires_at": key["key_expires_at"],
                 "specification": specification}
        processing["retry"] = retry
        options = ["--key", key["key"], "--key-expires-at", str(key["key_expires_at"]), "--spec-stdin"]
        payload = json.dumps(specification, ensure_ascii=False) + "\n__RESEARCH_STORE_STDIN_END__\n"
        prepared = _request(_json_command([review, "prepare", *options], env=env, payload=payload), specification)
        processing["request"] = prepared
        # Publish recovery identity before PDF storage. The prepared request is
        # already durable, and retries use exactly this key and specification.
        print("RESEARCH_SOURCE_INTAKE_RECEIPT " + json.dumps(
            {**retry, "request_id": prepared["request_id"]}, ensure_ascii=False), file=sys.stderr, flush=True)
        submitted = _request(_json_command([review, "submit", *options], env=env, payload=payload),
                             specification, prepared["request_id"])
        processing["request"] = submitted
        processing.pop("reason", None)
        failed = any(item.get("state") == "failed" for item in submitted["items"].values())
        if failed or submitted["state"] in {"failed", "partial_failure"}:
            processing["state"] = "partial_failure" if submitted["links"] else "failed"
            return response, 1
        processing["state"] = "submitted"
        if submitted.get("handoff", {}).get("worker") == "startup_failed":
            processing["state"] = "deferred"
            processing["reason"] = "review_startup_failed"
            return response, 1
        return response, 0
    except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as error:
        processing["error"] = str(error) or "작업이 중단되었습니다. 저장된 접수 상태를 확인하세요."
        return response, 130 if isinstance(error, KeyboardInterrupt) else 1
