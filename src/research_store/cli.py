from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .conversations import save_conversation
from .config import load_config
from .sync import (
    complete_reviews,
    library_status,
    pending_reviews,
    render_review_pages,
    sync_library,
)


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
    subparsers.add_parser("review-list", help="이미지 판독이 필요한 페이지 목록")

    render = subparsers.add_parser("render-review", help="검토할 PDF 페이지를 PNG로 렌더링")
    render.add_argument("document", help="review-list에 표시된 document_key")
    render.add_argument("--page", type=int, action="append", dest="pages")
    render.add_argument("--dpi", type=int, default=220)

    reviewed = subparsers.add_parser("review-complete", help="페이지 이미지 판독 상태 기록")
    reviewed.add_argument("document", help="review-list에 표시된 document_key")
    reviewed.add_argument("--page", type=int, action="append", required=True, dest="pages")
    reviewed.add_argument(
        "--status", choices=("verified", "needs_review"), default="verified"
    )
    reviewed.add_argument("--model", default="gpt-5.6-sol")
    reviewed.add_argument("--notes")

    conversation = subparsers.add_parser(
        "save-conversation", help="선택된 대화 범위를 구조화된 Markdown으로 저장"
    )
    conversation.add_argument("--payload", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        config = load_config(args.config)
        if args.command == "sync":
            result = asdict(sync_library(config))
        elif args.command == "status":
            result = library_status(config)
        elif args.command == "review-list":
            result = pending_reviews(config)
        elif args.command == "render-review":
            result = {
                "rendered": [
                    str(path)
                    for path in render_review_pages(
                        config, args.document, args.pages, args.dpi
                    )
                ]
            }
        elif args.command == "review-complete":
            result = {
                "updated": complete_reviews(
                    config,
                    args.document,
                    args.pages,
                    status=args.status,
                    reviewer_model=args.model,
                    notes=args.notes,
                )
            }
        else:
            result = {"saved": str(save_conversation(config, args.payload))}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
