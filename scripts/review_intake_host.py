#!/usr/bin/env python3
"""Bridge authorized attachment bytes into the existing constrained intake.

The public launcher validates the installation, Codex binary, and profiles.
This stdlib-only host helper persists intent through the worker profile before
invoking the existing read-only attachment transport. It never imports the
model runner, writes library files, or accepts a configurable child command.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import BinaryIO


MAX_SPEC_BYTES = 1024 * 1024
SENTINEL = b"__RESEARCH_STORE_STDIN_END__"


def _absolute(value: str) -> str:
    if not value or "\0" in value or not os.path.isabs(value):
        raise argparse.ArgumentTypeError("절대 경로를 지정해야 합니다")
    return value


def read_specification(stream: BinaryIO) -> tuple[bytes, dict]:
    chunks = []
    total = 0
    while True:
        line = stream.readline(MAX_SPEC_BYTES - total + len(SENTINEL) + 2)
        if not line or line in (SENTINEL, SENTINEL + b"\n", SENTINEL + b"\r\n"):
            break
        total += len(line)
        if total > MAX_SPEC_BYTES:
            raise ValueError("검토 접수 명세는 1 MiB 이하여야 합니다")
        chunks.append(line)
    payload = b"".join(chunks)
    try:
        specification = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ValueError("검토 접수 명세는 올바른 UTF-8 JSON이어야 합니다") from error
    if (not isinstance(specification, dict)
            or not isinstance(specification.get("items"), list)
            or not specification["items"]
            or any(not isinstance(item, dict) for item in specification["items"])):
        raise ValueError("검토 접수에는 정확한 항목 목록이 필요합니다")
    return payload, specification


def _exit_code(code: int) -> int:
    return code if code >= 0 else 128 - code


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", required=True, type=_absolute)
    parser.add_argument("--codex", required=True, type=_absolute)
    parser.add_argument("--sandbox-home", required=True, type=_absolute)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("submit", "start"):
        command = commands.add_parser(name, allow_abbrev=False)
        command.add_argument("--key", required=True)
        command.add_argument("--key-expires-at", required=True, type=float)
        command.add_argument("--spec-stdin", required=True, action="store_true")
        command.add_argument("--warn-seconds", type=float)
        command.add_argument("--warn-pages", type=int)
        command.add_argument("--warning-ratio", type=float, default=0.8)
        command.add_argument("--retention-seconds", type=float, default=30 * 86400)
        command.add_argument("--wait", action="store_true")
    args = parser.parse_args(raw)
    try:
        payload, specification = read_specification(sys.stdin.buffer)
        # Preserve the exact public options and specification for both calls.
        # Parsing above rejects private controls and arbitrary subprocess hooks.
        offset = raw.index(args.command)
        options = raw[offset + 1:]
        worker = [args.codex, "sandbox", "-P", "research-review-worker", "-C",
                  args.sandbox_home, "--", str(Path(args.root) / ".venv/bin/python"),
                  "-I", "-S", "-B", str(Path(args.root) / "scripts/background_lifecycle.py"),
                  "--root", args.root]
        env = os.environ.copy()
        env["CODEX_HOME"] = args.sandbox_home
        prepared = subprocess.run(
            [*worker, "prepare", *(option for option in options if option != "--wait")],
            input=payload, stdout=subprocess.PIPE, env=env, check=False,
        )
        if prepared.returncode:
            return _exit_code(prepared.returncode)
        try:
            receipt = json.loads(prepared.stdout)
        except (ValueError, UnicodeError) as error:
            raise ValueError("검토 접수 준비 응답을 확인할 수 없습니다") from error
        if (not isinstance(receipt, dict)
                or not isinstance(receipt.get("request_id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", receipt["request_id"])
                or not isinstance(receipt.get("items"), dict)):
            raise ValueError("검토 접수 준비 응답의 식별자가 올바르지 않습니다")
        request_id = receipt["request_id"]
        for item in specification["items"]:
            item_id = item.get("item_id")
            if (not isinstance(item_id, str) or not item_id
                    or not isinstance(receipt["items"].get(item_id), dict)):
                raise ValueError("검토 접수 준비 응답과 항목 목록이 다릅니다")
            if "attachment" not in item or receipt["items"][item_id].get("state") in {"linked", "complete", "deleted"}:
                continue
            # Transport failure is per item. The final constrained submit can
            # still recover an earlier stored receipt after the original is gone.
            command = [str(Path(args.root) / ".venv/bin/python"), "-I", "-S", "-B",
                       str(Path(args.root) / "scripts/import_attachment.py"),
                       "--root", args.root, "--codex", args.codex,
                       "--sandbox-home", args.sandbox_home,
                       "--path=" + str(item["attachment"]),
                       "--request-id=" + request_id, "--item-id=" + item_id]
            try:
                subprocess.run(command, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, env=env, check=False)
            except OSError:
                print("안내: 첨부 전송을 시작하지 못했습니다. 저장된 항목으로 접수를 복구합니다.",
                      file=sys.stderr)
        completed = subprocess.run([*worker, "submit", *options], input=payload,
                                   env=env, check=False)
        return _exit_code(completed.returncode)
    except (ValueError, UnicodeError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("오류: Research Agent 제한 실행기를 시작할 수 없습니다.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
