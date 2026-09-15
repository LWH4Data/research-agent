from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .config import load_config
from .sync import library_status, sync_library


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-store",
        description="읽기 전용 PDF 디렉터리를 검색용 Markdown으로 동기화합니다.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="설정 파일 경로 (기본값: config.toml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync", help="신규·변경 PDF를 Markdown으로 변환")
    subparsers.add_parser("status", help="마지막 동기화 상태 출력")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        config = load_config(args.config)
        if args.command == "sync":
            result = asdict(sync_library(config))
        else:
            result = library_status(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()

