from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .conversations import (
    delete_conversation,
    get_conversation,
    list_conversations,
    save_conversation,
    update_conversation,
)
from .config import load_config
from .operation_guard import operation_guard
from .picker import choose_source
from .progress import progress_renderer
from .search import search_library
from .safety import find_project_root
from .sources import (
    add_sources,
    default_config_path,
    initialize_config,
    remove_sources,
    source_rows,
)
from .state import LibraryState
from .sync import (
    complete_reviews,
    library_status,
    pending_reviews,
    render_review_pages,
    sync_library,
)


STDIN_SENTINEL = "__RESEARCH_STORE_STDIN_END__"
CONVERSATION_STDIN_LIMIT = 8 * 1024 * 1024
VISUAL_NOTES_STDIN_LIMIT = 1024 * 1024


def _read_stdin_text(*, label: str, max_bytes: int) -> str:
    """Read bounded UTF-8 input until an exact sentinel line or ordinary EOF."""
    sentinel = STDIN_SENTINEL.encode("ascii")
    chunks: list[bytes] = []
    total = 0
    while True:
        # The extra allowance lets a sentinel be recognized even when the payload
        # itself has reached its limit. A non-sentinel line still counts in full.
        allowance = max_bytes - total + len(sentinel) + 2
        line = sys.stdin.buffer.readline(allowance)
        if not line:
            break
        if line in (sentinel, sentinel + b"\n", sentinel + b"\r\n"):
            break
        total += len(line)
        if total > max_bytes:
            raise ValueError(f"{label}은 {max_bytes // (1024 * 1024)} MiB 이하여야 합니다")
        chunks.append(line)

    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label}은 올바른 UTF-8이어야 합니다") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-store",
        description="흩어진 PDF를 읽기 전용으로 찾아 Markdown 연구 저장소를 만듭니다.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="설정 파일 경로 (기본값: 프로젝트의 .research-store/config.toml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="프로젝트 내부 로컬 설정 생성")

    source_add = subparsers.add_parser(
        "source-add", help="읽기 전용 검색 위치 또는 PDF 등록"
    )
    source_add.add_argument("paths", type=Path, nargs="*")
    source_list = subparsers.add_parser(
        "source-list", help="등록된 읽기 전용 위치 목록"
    )
    source_list.add_argument(
        "--plain", action="store_true", help="사람이 읽기 쉬운 목록으로 표시"
    )
    source_remove = subparsers.add_parser(
        "source-remove", help="검색 대상에서 위치 제거 (원본과 변환 결과는 삭제하지 않음)"
    )
    source_remove.add_argument("source_ids", nargs="+")

    sync = subparsers.add_parser("sync", help="신규·변경 PDF를 Markdown으로 변환")
    sync.add_argument(
        "--progress",
        choices=("auto", "off", "jsonl"),
        default="auto",
        help="진행 표시 방식: 터미널 자동 표시, 끄기, 또는 Agent용 JSONL",
    )
    subparsers.add_parser("status", help="마지막 동기화 상태 출력")
    search = subparsers.add_parser(
        "search", help="PDF Markdown과 저장된 대화를 함께 검색"
    )
    search.add_argument("queries", nargs="+", help="하나 이상의 검색어")
    search.add_argument("--limit", type=int, default=50, help="최대 결과 개수 (1-200)")
    subparsers.add_parser("review-list", help="이미지 판독이 필요한 페이지 목록")

    render = subparsers.add_parser("render-review", help="검토할 PDF 페이지를 PNG로 렌더링")
    render.add_argument("document", help="review-list에 표시된 document_key")
    render.add_argument("--page", type=int, action="append", dest="pages")
    render.add_argument("--dpi", type=int, default=220)

    reviewed = subparsers.add_parser("review-complete", help="페이지 이미지 판독 상태 기록")
    reviewed.add_argument("document", help="review-list에 표시된 document_key")
    reviewed.add_argument(
        "--page",
        type=int,
        action="append",
        required=True,
        dest="pages",
        help="저장할 단일 페이지 번호(한 번만 지정)",
    )
    reviewed.add_argument(
        "--sha256", required=True, help="render-review가 반환한 문서 SHA-256"
    )
    reviewed.add_argument(
        "--status", choices=("verified", "needs_review"), default="verified"
    )
    reviewed.add_argument("--model", default="gpt-5.6-sol")
    reviewed.add_argument("--notes")
    reviewed.add_argument(
        "--visual-notes-stdin",
        action="store_true",
        help=(
            "표준 입력의 Markdown 검토 노트를 안전하게 문서에 추가 "
            f"(종료 줄: {STDIN_SENTINEL})"
        ),
    )

    subparsers.add_parser(
        "save-conversation", help="선택된 대화 범위를 구조화된 Markdown으로 저장"
    )
    subparsers.add_parser("conversation-list", help="저장된 대화 기록 목록")
    conversation_get = subparsers.add_parser(
        "conversation-get", help="저장된 대화의 수정 가능한 정리 정보 조회"
    )
    conversation_get.add_argument("conversation_id")
    conversation_update = subparsers.add_parser(
        "conversation-update", help="저장된 대화의 검색용 정리 정보 수정"
    )
    conversation_update.add_argument("conversation_id")
    conversation_update.add_argument(
        "--expected-revision", type=int, required=True
    )
    conversation_update.add_argument(
        "--confirm-legacy-promotion",
        action="store_true",
        help="검토한 v1/v2 정리 후보를 v3로 처음 승격",
    )
    conversation_delete = subparsers.add_parser(
        "conversation-delete", help="저장된 대화 기록 삭제"
    )
    conversation_delete.add_argument("conversation_id")
    conversation_delete.add_argument(
        "--expected-revision", type=int, required=True
    )
    return parser


def _config_path(value: Path | None) -> Path:
    if value is None:
        return default_config_path()
    path = value.expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def main() -> None:
    args = _parser().parse_args()
    guards = ExitStack()
    try:
        config_path = _config_path(args.config)
        guards.enter_context(operation_guard(find_project_root(config_path.parent)))
        if args.command == "init":
            initialized = initialize_config(config_path)
            config = load_config(initialized)
            # Installation and explicit initialization are the schema migration
            # boundary. Read-only commands never upgrade SQLite implicitly.
            with LibraryState(config.state, config.root):
                pass
            result: object = {"config": str(initialized)}
        elif args.command == "source-add":
            paths = list(args.paths)
            if not paths:
                selected = choose_source()
                paths = [] if selected is None else [selected]
            added = add_sources(config_path, paths)
            result = {
                "added": [
                    {
                        "id": source.id,
                        "path": str(source.path),
                        "access": "read-only",
                    }
                    for source in added
                ],
                "cancelled": not paths,
            }
        elif args.command == "source-list":
            initialize_config(config_path)
            rows = source_rows(config_path)
            if args.plain:
                if not rows:
                    print("등록된 PDF 위치가 없습니다.")
                    print("추가하려면 add-source.sh를 실행하세요.")
                else:
                    print(f"등록된 읽기 전용 위치: {len(rows)}개")
                    for index, row in enumerate(rows, start=1):
                        if not row["enabled"]:
                            state = "스캔 중단됨"
                        elif row["available"]:
                            state = "사용 가능"
                        else:
                            state = "현재 연결 안 됨"
                        print(f"{index}. {row['path']} ({state}, ID: {row['id']})")
                return
            result = rows
        elif args.command == "source-remove":
            removed = remove_sources(config_path, args.source_ids)
            result = {
                "removed_from_scan": [source.id for source in removed],
                "originals_deleted": False,
                "generated_files_deleted": False,
            }
        else:
            config = load_config(config_path)
            if args.command == "sync":
                result = asdict(
                    sync_library(
                        config,
                        progress=progress_renderer(args.progress),
                    )
                )
                if result["registered_sources"] == 0:
                    result["message"] = (
                        "등록된 PDF 위치가 없습니다. bash ./add-source.sh로 추가하세요."
                    )
            elif args.command == "status":
                result = library_status(config)
            elif args.command == "search":
                result = search_library(config, args.queries, limit=args.limit)
            elif args.command == "review-list":
                result = pending_reviews(config)
            elif args.command == "render-review":
                rendered = render_review_pages(
                    config, args.document, args.pages, args.dpi
                )
                result = {
                    "document": args.document,
                    "sha256": rendered.sha256,
                    "rendered": [str(path) for path in rendered.paths],
                }
            elif args.command == "review-complete":
                visual_notes = None
                if args.visual_notes_stdin:
                    visual_notes = _read_stdin_text(
                        label="시각 검토 노트",
                        max_bytes=VISUAL_NOTES_STDIN_LIMIT,
                    )
                    if not visual_notes.strip():
                        raise ValueError("시각 검토 노트가 비어 있습니다")
                result = {
                    "updated": complete_reviews(
                        config,
                        args.document,
                        args.pages,
                        expected_sha256=args.sha256,
                        status=args.status,
                        reviewer_model=args.model,
                        notes=args.notes,
                        visual_notes=visual_notes,
                    )
                }
            elif args.command == "conversation-list":
                result = {"conversations": list_conversations(config)}
            elif args.command == "conversation-get":
                result = get_conversation(config, args.conversation_id)
            elif args.command in {"save-conversation", "conversation-update"}:
                raw_input = _read_stdin_text(
                    label="대화 JSON",
                    max_bytes=CONVERSATION_STDIN_LIMIT,
                )
                if not raw_input.strip():
                    raise ValueError("표준 입력으로 대화 JSON을 전달해야 합니다")
                try:
                    payload = json.loads(raw_input)
                except json.JSONDecodeError as error:
                    raise ValueError(f"대화 JSON을 읽을 수 없습니다: {error}") from error
                if args.command == "save-conversation":
                    saved = save_conversation(config, payload)
                    result = {"saved": str(saved)}
                else:
                    result = update_conversation(
                        config,
                        args.conversation_id,
                        payload,
                        expected_revision=args.expected_revision,
                        confirm_legacy_promotion=args.confirm_legacy_promotion,
                    )
            elif args.command == "conversation-delete":
                result = delete_conversation(
                    config,
                    args.conversation_id,
                    expected_revision=args.expected_revision,
                )
            else:  # pragma: no cover - argparse restricts command values.
                raise RuntimeError(f"지원하지 않는 명령입니다: {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except KeyboardInterrupt as error:
        print(
            "\n작업을 안전하게 중단했습니다. 다음 실행에서 저장된 지점부터 다시 확인합니다.",
            file=sys.stderr,
        )
        raise SystemExit(130) from error
    except (OSError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    finally:
        guards.close()


if __name__ == "__main__":
    main()
