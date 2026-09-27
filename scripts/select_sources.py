#!/usr/bin/env python3
"""Collect a confirmed folder draft, then register it through the fixed sandbox.

The host-side picker only returns paths. It never imports the storage layer,
writes configuration, reads PDF contents, or changes source permissions.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--codex", required=True, type=_absolute)
    parser.add_argument("--root", required=True, type=_absolute)
    parser.add_argument("--sandbox-home", required=True, type=_absolute)
    args = parser.parse_args(argv)
    try:
        paths = choose_confirmed_sources(Path(args.root))
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
        print(json.dumps({"added": [], "cancelled": True}))
        return 0
    env = os.environ.copy()
    env["CODEX_HOME"] = args.sandbox_home
    command = [args.codex, "sandbox", "-P", "research-store", "-C",
               args.sandbox_home, "--", str(Path(args.root) / "research-store"),
               "source-add", "--", *map(str, paths)]
    try:
        result = subprocess.run(command, env=env, check=False)
    except OSError:
        print("오류: Research Agent 제한 실행기를 시작할 수 없습니다. 폴더는 연결되지 않았습니다.",
              file=sys.stderr)
        return 1
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
