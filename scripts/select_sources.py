#!/usr/bin/env python3
"""Confirm sources, register them, and start their managed storage request.

The host-side picker only returns paths. It never imports the storage layer,
writes configuration, reads PDF contents, or changes source permissions.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def _absolute(value: str) -> str:
    if not value or "\0" in value or not os.path.isabs(value):
        raise argparse.ArgumentTypeError("절대 경로를 지정해야 합니다")
    return value


def choose_confirmed_sources(root: Path) -> list[Path]:
    # -I -S intentionally excludes site packages and the caller's working path.
    # Load only the stdlib-only picker from the validated installation.
    spec = importlib.util.spec_from_file_location(
        "research_agent_folder_picker", root / "src/research_store/picker.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("폴더 연결 화면을 불러올 수 없습니다.")
    picker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(picker)
    return picker.choose_sources()


def connect_sources(root: Path, paths: list[Path], **options) -> tuple[dict, int]:
    spec = importlib.util.spec_from_file_location(
        "research_agent_source_intake", root / "scripts/source_intake.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("폴더 저장 접수 기능을 불러올 수 없습니다.")
    intake = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(intake)
    return intake.connect_sources(root, paths, **options)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--codex", type=_absolute)
    parser.add_argument("--root", required=True, type=_absolute)
    parser.add_argument("--sandbox-home", required=True, type=_absolute)
    parser.add_argument("--installation", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--registration-only", action="store_true",
                        help="지정한 경로를 연결만 하고 PDF 저장은 시작하지 않습니다")
    parser.add_argument("paths", nargs="*", type=_absolute)
    args = parser.parse_args(argv)
    if not args.codex and not args.installation:
        parser.error("Codex 제한 실행기가 필요합니다")
    if args.registration_only and not args.paths:
        parser.error("연결만 할 때는 정확한 원본 경로를 지정하세요")
    try:
        paths = list(map(Path, args.paths)) if args.paths else choose_confirmed_sources(Path(args.root))
        if not isinstance(paths, list) or any(
            not isinstance(path, Path) or not path.is_absolute() or "\0" in str(path)
            for path in paths
        ):
            raise ValueError("폴더 연결 화면의 선택 결과가 올바르지 않습니다.")
    except (OSError, ValueError, RuntimeError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        paths = []

    if not paths:
        print(json.dumps({"added": [], "selected": [], "cancelled": True,
                          "processing": {"state": "not_started", "reason": "cancelled"}}))
        return 0
    try:
        response, code = connect_sources(Path(args.root), paths, codex=args.codex,
                                         sandbox_home=args.sandbox_home,
                                         registration_only=args.registration_only,
                                         installation=args.installation)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    print(json.dumps(response, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
