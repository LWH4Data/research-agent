from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import sys
from typing import Callable, TextIO
import unicodedata


PROGRESS_PREFIX = "RESEARCH_PROGRESS "
PROGRESS_SCHEMA_VERSION = 1


def sanitize_progress_text(value: str | None, *, limit: int = 160) -> str | None:
    """Return one safe display line without terminal control characters."""

    if value is None:
        return None
    cleaned = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in str(value)
    )
    cleaned = " ".join(cleaned.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


@dataclass(frozen=True)
class ProgressEvent:
    run_id: str
    phase: str
    status: str
    current: int
    total: int
    counters: dict[str, int] = field(default_factory=dict)
    last_item: str | None = None
    message: str | None = None
    operation: str = "sync"
    type: str = "research_progress"
    schema_version: int = PROGRESS_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["last_item"] = sanitize_progress_text(self.last_item)
        payload["message"] = sanitize_progress_text(self.message, limit=320)
        return payload


ProgressCallback = Callable[[ProgressEvent], None]


def emit_progress(
    callback: ProgressCallback | None, event: ProgressEvent
) -> None:
    """Progress is best-effort telemetry and must never corrupt library work."""

    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        # A closed terminal, malformed display stream, or renderer bug must not
        # turn a successfully committed document into a failed sync.
        return


class JsonlProgressRenderer:
    """Write milestone events to stderr without changing stdout JSON."""

    def __init__(self, stream: TextIO):
        self.stream = stream
        self._last_phase: str | None = None
        self._last_bucket: dict[str, int] = {}

    def __call__(self, event: ProgressEvent) -> None:
        phase_changed = event.phase != self._last_phase
        always = event.status in {
            "started",
            "warning",
            "error",
            "failed",
            "interrupted",
            "completed",
            "completed_with_errors",
        }
        if event.total > 0:
            bucket = min(10, (event.current * 10) // event.total)
        else:
            bucket = 0
        milestone = bucket > self._last_bucket.get(event.phase, -1)
        if not (phase_changed or always or milestone):
            return
        self._last_phase = event.phase
        self._last_bucket[event.phase] = bucket
        self.stream.write(
            PROGRESS_PREFIX
            + json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )
        self.stream.flush()


class TerminalProgressRenderer:
    """Render a compact in-place bar for a person using a terminal."""

    _PHASE_LABELS = {
        "recovery": "중단된 작업 확인",
        "discover": "1/3 원본 위치를 확인하고 있어요",
        "documents": "2/3 문서를 정리하고 있어요",
        "finalize": "2/3 정리 결과를 확인하고 있어요",
        "review": "3/3 그림과 수식을 확인하고 있어요",
    }

    def __init__(self, stream: TextIO, *, width: int = 10):
        self.stream = stream
        self.width = width
        self._last_phase: str | None = None

    def __call__(self, event: ProgressEvent) -> None:
        label = self._PHASE_LABELS.get(event.phase, "연구 자료를 정리하고 있어요")
        total = max(0, event.total)
        current = min(max(0, event.current), total) if total else 0
        ratio = current / total if total else 0.0
        filled = min(self.width, int(ratio * self.width))
        bar = "█" * filled + "░" * (self.width - filled)
        percent = int(ratio * 100)
        suffix = f" {current}/{total} · {percent}%" if total else ""
        if event.phase == "discover":
            suffix += f" · PDF {event.counters.get('discovered', 0)}개 발견"
        if event.phase != self._last_phase:
            if self._last_phase is not None:
                self.stream.write("\n")
            self.stream.write(label + "\n")
            self._last_phase = event.phase
        self.stream.write(f"\r[{bar}]{suffix}\033[K")
        if event.status in {
            "completed",
            "completed_with_errors",
            "interrupted",
            "error",
            "failed",
        }:
            self.stream.write("\n")
        self.stream.flush()


def progress_renderer(
    mode: str,
    *,
    stream: TextIO | None = None,
) -> ProgressCallback | None:
    """Build the CLI renderer. Non-interactive auto mode stays silent."""

    output = stream or sys.stderr
    if mode == "off":
        return None
    if mode == "jsonl":
        return JsonlProgressRenderer(output)
    if mode != "auto":
        raise ValueError(f"지원하지 않는 진행 표시 방식입니다: {mode}")
    if not output.isatty():
        return None
    return TerminalProgressRenderer(output)
