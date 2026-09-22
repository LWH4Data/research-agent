#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from research_store.progress import (
    JsonlProgressRenderer,
    ProgressEvent,
    TerminalProgressRenderer,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research Agent 진행 표시 미리 보기")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.14,
        help="각 표시 사이의 대기 시간(초)",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Agent 통합 테스트용 JSONL 진행 이벤트를 stderr로 출력",
    )
    arguments = parser.parse_args()
    if arguments.delay < 0 or arguments.delay > 2:
        parser.error("--delay는 0에서 2초 사이여야 합니다")
    return arguments


def _show_phase(
    renderer: Callable[[ProgressEvent], None],
    *,
    run_id: str,
    phase: str,
    total: int,
    delay: float,
    discovered: list[int] | None = None,
    final: bool = False,
) -> None:
    for current in range(total + 1):
        counters: dict[str, int] = {}
        if discovered is not None:
            counters["discovered"] = discovered[current]
        renderer(
            ProgressEvent(
                run_id=run_id,
                phase=phase,
                status="completed" if final and current == total else "progress",
                current=current,
                total=total,
                counters=counters,
            )
        )
        time.sleep(delay)


def main() -> None:
    arguments = _arguments()
    renderer: Callable[[ProgressEvent], None]
    if arguments.jsonl:
        renderer = JsonlProgressRenderer(sys.stderr)
    else:
        renderer = TerminalProgressRenderer(sys.stdout)
    run_id = "progress-preview"
    if not arguments.jsonl:
        print("Research Agent 진행 표시 미리 보기\n")
    try:
        _show_phase(
            renderer,
            run_id=run_id,
            phase="discover",
            total=3,
            delay=arguments.delay,
            discovered=[0, 4, 9, 12],
        )
        _show_phase(
            renderer,
            run_id=run_id,
            phase="documents",
            total=12,
            delay=arguments.delay,
        )
        _show_phase(
            renderer,
            run_id=run_id,
            phase="review",
            total=4,
            delay=arguments.delay,
            final=True,
        )
    except KeyboardInterrupt:
        if not arguments.jsonl:
            print("\n미리 보기를 중단했습니다.")
        raise SystemExit(130) from None
    if arguments.jsonl:
        print(
            json.dumps(
                {
                    "preview": "completed",
                    "sources": 3,
                    "documents": 12,
                    "review_pages": 4,
                    "store_modified": False,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    else:
        print("\n미리 보기가 끝났습니다. 실제 PDF와 저장소는 변경하지 않았습니다.")


if __name__ == "__main__":
    main()
