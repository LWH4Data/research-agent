from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

from .config import Config, Source
from .imports import ImportedSource, library_sources, recover_imports
from .locking import conversation_lock as project_write_lock, sync_lock
from .operations import journaled_document_replace, recover_document_operation
from .progress import (
    ProgressCallback,
    ProgressEvent,
    emit_progress,
    sanitize_progress_text,
)
from .safety import (
    atomic_text,
    ensure_owned_directory,
    reject_linked_file,
    require_owned_path,
    safe_source_file,
    unlink_owned_file,
)
from .state import (
    LibraryState,
    normalize_review_pages,
    now,
    validate_reviewer_model,
)


PARSER_NAME = "pypdf"
PARSER_VERSION = "pypdf-v4-fonttools-read-only-store"


@dataclass(frozen=True)
class ConversionResult:
    markdown: str
    review_pages: dict[int, list[str]]


@dataclass(frozen=True)
class RenderResult:
    sha256: str
    paths: tuple[Path, ...]


Converter = Callable[[Path], str | ConversionResult]


@dataclass
class SyncStats:
    registered_sources: int = 0
    discovered: int = 0
    converted: int = 0
    unchanged: int = 0
    missing: int = 0
    failed: int = 0
    pages_needing_review: int = 0
    unavailable_sources: int = 0
    source_errors: list[dict[str, str]] = field(default_factory=list)


_PROGRESS_COUNTER_FIELDS = (
    "discovered",
    "converted",
    "unchanged",
    "missing",
    "failed",
    "pages_needing_review",
    "unavailable_sources",
)


def _progress_counters(
    stats: SyncStats, **overrides: int
) -> dict[str, int]:
    counters = {
        field_name: int(getattr(stats, field_name))
        for field_name in _PROGRESS_COUNTER_FIELDS
    }
    counters.update(overrides)
    return counters


def _progress_item(path: Path) -> str:
    return sanitize_progress_text(path.name, limit=160) or "PDF"


def _pending_review_records(
    document_key: str, reviews: dict[int, list[str]]
) -> list[dict[str, object]]:
    return [
        {
            "document_key": document_key,
            "page_number": page_number,
            "reasons": json.dumps(reasons, ensure_ascii=False),
            "status": "pending",
            "reviewed_at": None,
            "reviewer_model": None,
            "notes": None,
        }
        for page_number, reasons in sorted(reviews.items())
    ]


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _review_reasons(text: str, image_count: int) -> list[str]:
    reasons: list[str] = []
    lowered = text.casefold()
    if re.search(r"\b(table|표)\s*[\divxlcdm]*\b", lowered):
        reasons.append("table-caption")
    if re.search(r"\b(fig(?:ure)?\.?|그림)\s*\d+\b", lowered):
        reasons.append("figure-caption")
    if re.search(r"\b(eq(?:uation)?\.?|식)\s*\(?\d+\)?", lowered):
        reasons.append("equation-reference")

    math_symbols = sum(text.count(symbol) for symbol in "=∑∫√±≤≥≈∞∂∇⊗×")
    math_lines = sum(
        1 for line in text.splitlines() if "=" in line and len(line.strip()) <= 180
    )
    if math_symbols >= 3 or math_lines >= 2:
        reasons.append("math-density")
    if image_count:
        reasons.append("embedded-image")
    if len(text.strip()) < 80:
        reasons.append("low-extracted-text")
    return reasons


def pdf_converter(path: Path) -> ConversionResult:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PyPDF가 없습니다. 먼저 `uv sync`를 실행하세요.") from error

    reader = PdfReader(str(path))
    pages: list[str] = []
    reviews: dict[int, list[str]] = {}
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        image_count = len(page.images)
        reasons = _review_reasons(text, image_count)
        if reasons:
            reviews[page_number] = reasons
        body = text or "<!-- text-extraction: empty; visual review required -->"
        pages.append(f"<!-- page: {page_number} -->\n\n{body}")
    if not pages:
        raise RuntimeError("페이지가 없는 PDF입니다")
    return ConversionResult("\n\n".join(pages) + "\n", reviews)


def _frontmatter(
    source: Source,
    relative: Path,
    digest: str,
    modified_ns: int,
    review_pages: dict[int, list[str]],
) -> str:
    metadata = {
        "schema_version": 1,
        "type": "pdf-document",
        "document_id": f"sha256:{digest}",
        "source_id": source.id,
        "source_path": relative.as_posix(),
        "source_modified_ns": modified_ns,
        "parsed_at": now(),
        "language": "unknown",
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "visual_review": "pending" if review_pages else "not-needed",
        "visual_review_pages": sorted(review_pages),
        "visual_review_pending_pages": sorted(review_pages),
    }
    if isinstance(source, ImportedSource):
        metadata.update({
            "source_kind": "imported-pdf",
            "original_filename": source.original_name,
            "imported_at": source.imported_at,
            "import_origin_path": source.origin_path,
            "stored_pdf": str(source.path),
        })
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _validated_document_frontmatter(
    content: str,
    *,
    expected_sha256: str,
    expected_source_id: str,
    expected_source_path: str,
) -> tuple[list[str], int, int | None, int]:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("Markdown frontmatter를 찾을 수 없습니다")
    closing = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing is None:
        raise ValueError("Markdown frontmatter가 닫히지 않았습니다")

    required = {"document_id", "source_id", "source_path", "visual_review"}
    recognized = required | {
        "visual_review_pages",
        "visual_review_pending_pages",
    }
    values: dict[str, object] = {}
    indexes: dict[str, int] = {}
    for index in range(1, closing):
        key, separator, raw_value = lines[index].rstrip("\r\n").partition(":")
        if not separator or key not in recognized:
            continue
        if key in values:
            raise ValueError(f"Markdown frontmatter에 {key}가 중복되어 있습니다")
        try:
            values[key] = json.loads(raw_value.strip())
        except json.JSONDecodeError as error:
            raise ValueError(f"Markdown frontmatter의 {key}가 올바르지 않습니다") from error
        indexes[key] = index

    missing = required - values.keys()
    if missing:
        raise ValueError(
            "Markdown frontmatter에 필요한 값이 없습니다: "
            + ", ".join(sorted(missing))
        )
    expected = {
        "document_id": f"sha256:{expected_sha256}",
        "source_id": expected_source_id,
        "source_path": expected_source_path,
    }
    for key, value in expected.items():
        if values[key] != value:
            raise ValueError(f"Markdown frontmatter의 {key}가 현재 문서와 일치하지 않습니다")
    pending_pages = values.get("visual_review_pending_pages")
    if pending_pages is not None:
        if not isinstance(pending_pages, list) or any(
            isinstance(page, bool) or not isinstance(page, int) or page < 1
            for page in pending_pages
        ):
            raise ValueError(
                "Markdown frontmatter의 visual_review_pending_pages가 올바르지 않습니다"
            )
    return (
        lines,
        indexes["visual_review"],
        indexes.get("visual_review_pending_pages"),
        closing,
    )


@dataclass(frozen=True)
class _ReviewNoteBlock:
    start: int
    end: int
    pages: tuple[int, ...]


@dataclass(frozen=True)
class _ReviewSection:
    start: int
    body_start: int
    body_end: int
    end: int
    managed: bool


_VISUAL_REVIEW_SECTION_RE = re.compile(
    r"(?m)^## Visual verification notes[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_SECTION_BEGIN_RE = re.compile(
    r"(?m)^<!-- visual-review-section-begin:[ \t]*"
    r"sha256:([0-9a-f]{64})[ \t]*-->[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_SECTION_END_RE = re.compile(
    r"(?m)^<!-- visual-review-section-end:[ \t]*"
    r"sha256:([0-9a-f]{64})[ \t]*-->[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_BEGIN_RE = re.compile(
    r"(?m)^<!-- visual-review-begin:[ \t]*([^\r\n]*?)[ \t]*-->"
    r"[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_END_RE = re.compile(
    r"(?m)^<!-- visual-review-end:[ \t]*([^\r\n]*?)[ \t]*-->"
    r"[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_LEGACY_HEADING_RE = re.compile(
    r"(?m)^### Pages[ \t]+([0-9][0-9, \t]*)[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_PAGES_RE = re.compile(
    r"(?m)^<!-- visual-review-pages:[ \t]*([^\r\n]*?)[ \t]*-->"
    r"[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_SHA256_RE = re.compile(
    r"(?m)^<!-- visual-review-sha256:[ \t]*([0-9a-f]{64})[ \t]*-->"
    r"[ \t]*(?:\r?\n|$)"
)
_VISUAL_REVIEW_RESERVED_MARKER_RE = re.compile(
    r"(?mi)^[ \t]*<!--[ \t]*visual-review-[a-z0-9-]+[ \t]*:"
)
_BASE_PAGE_MARKER_RE = re.compile(
    r"(?m)^<!-- page:[ \t]*[1-9][0-9]*[ \t]*-->[ \t]*(?:\r?\n|$)"
)


def _parse_review_page_label(label: str, *, marker: str) -> tuple[int, ...]:
    stripped = label.strip()
    if not re.fullmatch(r"[0-9]+(?:[ \t]*,[ \t]*[0-9]+)*", stripped):
        raise ValueError(f"시각 검토 {marker}의 페이지 목록이 올바르지 않습니다")
    pages = [int(value.strip()) for value in stripped.split(",")]
    try:
        return tuple(normalize_review_pages(pages))
    except ValueError as error:
        raise ValueError(
            f"시각 검토 {marker}의 페이지 목록이 올바르지 않습니다"
        ) from error


def _review_note_blocks(
    body: str, *, expected_sha256: str
) -> list[_ReviewNoteBlock]:
    new_blocks: list[_ReviewNoteBlock] = []
    cursor = 0
    while True:
        begin = _VISUAL_REVIEW_BEGIN_RE.search(body, cursor)
        if begin is None:
            stray_end = _VISUAL_REVIEW_END_RE.search(body, cursor)
            if stray_end is not None:
                raise ValueError("시각 검토 종료 표식에 대응하는 시작 표식이 없습니다")
            break

        stray_end = _VISUAL_REVIEW_END_RE.search(body, cursor, begin.start())
        if stray_end is not None:
            raise ValueError("시각 검토 종료 표식에 대응하는 시작 표식이 없습니다")
        end = _VISUAL_REVIEW_END_RE.search(body, begin.end())
        next_begin = _VISUAL_REVIEW_BEGIN_RE.search(body, begin.end())
        if end is None or (
            next_begin is not None and next_begin.start() < end.start()
        ):
            raise ValueError("시각 검토 시작 표식이 올바르게 닫히지 않았습니다")

        begin_pages = _parse_review_page_label(
            begin.group(1), marker="시작 표식"
        )
        end_pages = _parse_review_page_label(end.group(1), marker="종료 표식")
        if begin_pages != end_pages:
            raise ValueError("시각 검토 시작·종료 표식의 페이지가 일치하지 않습니다")
        page_markers = list(
            _VISUAL_REVIEW_PAGES_RE.finditer(body, begin.end(), end.start())
        )
        if len(page_markers) != 1:
            raise ValueError(
                "시각 검토 블록에는 visual-review-pages 표식이 정확히 하나 필요합니다"
            )
        marker_pages = _parse_review_page_label(
            page_markers[0].group(1), marker="페이지 표식"
        )
        if marker_pages != begin_pages:
            raise ValueError(
                "시각 검토 블록 경계와 visual-review-pages 표식의 페이지가 "
                "일치하지 않습니다"
            )
        sha256_markers = list(
            _VISUAL_REVIEW_SHA256_RE.finditer(body, begin.end(), end.start())
        )
        if len(sha256_markers) != 1:
            raise ValueError(
                "시각 검토 블록에는 visual-review-sha256 표식이 정확히 하나 필요합니다"
            )
        if sha256_markers[0].group(1) != expected_sha256:
            raise ValueError(
                "시각 검토 블록의 SHA-256이 현재 문서와 일치하지 않습니다"
            )
        new_blocks.append(
            _ReviewNoteBlock(begin.start(), end.end(), begin_pages)
        )
        cursor = end.end()

    legacy_matches = [
        match
        for match in _VISUAL_REVIEW_LEGACY_HEADING_RE.finditer(body)
        if not any(block.start <= match.start() < block.end for block in new_blocks)
    ]
    starts = sorted(
        [block.start for block in new_blocks]
        + [match.start() for match in legacy_matches]
    )
    legacy_blocks: list[_ReviewNoteBlock] = []
    for match in legacy_matches:
        next_start = next(
            (start for start in starts if start > match.start()), len(body)
        )
        heading_pages = _parse_review_page_label(
            match.group(1), marker="레거시 제목"
        )
        page_markers = list(
            _VISUAL_REVIEW_PAGES_RE.finditer(body, match.end(), next_start)
        )
        if len(page_markers) != 1:
            raise ValueError(
                "레거시 시각 검토 블록에는 visual-review-pages 표식이 "
                "정확히 하나 필요합니다"
            )
        marker_pages = _parse_review_page_label(
            page_markers[0].group(1), marker="레거시 페이지 표식"
        )
        if marker_pages != heading_pages:
            raise ValueError(
                "레거시 시각 검토 제목과 visual-review-pages 표식의 페이지가 "
                "일치하지 않습니다"
            )
        sha256_markers = list(
            _VISUAL_REVIEW_SHA256_RE.finditer(body, match.end(), next_start)
        )
        if len(sha256_markers) != 1:
            raise ValueError(
                "레거시 시각 검토 블록에는 visual-review-sha256 표식이 "
                "정확히 하나 필요합니다"
            )
        if sha256_markers[0].group(1) != expected_sha256:
            raise ValueError(
                "레거시 시각 검토 블록의 SHA-256이 현재 문서와 일치하지 않습니다"
            )
        legacy_blocks.append(
            _ReviewNoteBlock(
                match.start(),
                next_start,
                heading_pages,
            )
        )
    return sorted([*new_blocks, *legacy_blocks], key=lambda block: block.start)


def _validated_review_section_body(
    body: str, *, expected_sha256: str, allow_empty: bool = False
) -> list[_ReviewNoteBlock]:
    blocks = _review_note_blocks(body, expected_sha256=expected_sha256)
    if not blocks:
        if allow_empty and not body.strip():
            return []
        raise ValueError("시각 검토 섹션에 검토 블록이 없습니다")
    cursor = 0
    for block in blocks:
        if body[cursor : block.start].strip():
            raise ValueError("시각 검토 섹션의 블록 바깥에 알 수 없는 내용이 있습니다")
        cursor = block.end
    if body[cursor:].strip():
        raise ValueError("시각 검토 섹션의 블록 바깥에 알 수 없는 내용이 있습니다")
    return blocks


def _managed_review_section(
    content: str, *, expected_sha256: str
) -> tuple[_ReviewSection, list[_ReviewNoteBlock]] | None:
    begins = [
        match
        for match in _VISUAL_REVIEW_SECTION_BEGIN_RE.finditer(content)
        if match.group(1) == expected_sha256
    ]
    ends = [
        match
        for match in _VISUAL_REVIEW_SECTION_END_RE.finditer(content)
        if match.group(1) == expected_sha256
    ]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1:
        raise ValueError(
            "현재 문서에 결합된 시각 검토 섹션 경계가 정확히 한 쌍이어야 합니다"
        )

    begin = begins[0]
    end = ends[0]
    if end.start() <= begin.end():
        raise ValueError("시각 검토 섹션 경계의 순서가 올바르지 않습니다")
    page_markers = list(_BASE_PAGE_MARKER_RE.finditer(content))
    if page_markers and begin.start() < page_markers[-1].end():
        raise ValueError(
            "관리되는 시각 검토 섹션은 기본 PDF 페이지 추출 뒤에 있어야 합니다"
        )
    heading = _VISUAL_REVIEW_SECTION_RE.match(content, begin.end())
    if heading is None or heading.end() > end.start():
        raise ValueError("관리되는 시각 검토 섹션 제목을 찾을 수 없습니다")
    if content[end.end() :].strip():
        raise ValueError(
            "관리되는 시각 검토 섹션 뒤에 알 수 없는 내용이 있습니다"
        )

    body = content[heading.end() : end.start()]
    blocks = _validated_review_section_body(
        body,
        expected_sha256=expected_sha256,
        allow_empty=True,
    )
    return (
        _ReviewSection(
            start=begin.start(),
            body_start=heading.end(),
            body_end=end.start(),
            end=end.end(),
            managed=True,
        ),
        blocks,
    )


def _legacy_review_section(
    content: str, *, expected_sha256: str
) -> tuple[_ReviewSection, list[_ReviewNoteBlock]] | None:
    page_markers = list(_BASE_PAGE_MARKER_RE.finditer(content))
    base_end = page_markers[-1].end() if page_markers else 0
    headings = [
        match
        for match in _VISUAL_REVIEW_SECTION_RE.finditer(content)
        if match.start() >= base_end
    ]
    if not headings:
        return None

    authenticated: list[tuple[_ReviewSection, list[_ReviewNoteBlock]]] = []
    strong_errors: list[ValueError] = []
    ambiguous = False
    for heading in headings:
        body = content[heading.end() :]
        try:
            blocks = _validated_review_section_body(
                body, expected_sha256=expected_sha256
            )
        except ValueError as error:
            sha256_markers = list(_VISUAL_REVIEW_SHA256_RE.finditer(body))
            if any(
                marker.group(1) == expected_sha256
                for marker in sha256_markers
            ):
                strong_errors.append(error)
            if (
                _VISUAL_REVIEW_LEGACY_HEADING_RE.search(body) is not None
                or _VISUAL_REVIEW_RESERVED_MARKER_RE.search(body) is not None
            ):
                ambiguous = True
            continue
        authenticated.append(
            (
                _ReviewSection(
                    start=heading.start(),
                    body_start=heading.end(),
                    body_end=len(content),
                    end=len(content),
                    managed=False,
                ),
                blocks,
            )
        )

    if len(authenticated) == 1:
        return authenticated[0]
    if len(authenticated) > 1:
        raise ValueError(
            "관리 경계가 없는 시각 검토 섹션이 여러 개라 자동 마이그레이션할 수 "
            "없습니다"
        )
    if strong_errors:
        raise strong_errors[0]
    if ambiguous:
        raise ValueError(
            "관리 경계가 없는 시각 검토 섹션을 현재 문서에 속한 것으로 "
            "인증할 수 없습니다. 기존 내용을 보존했으며 명시적인 "
            "마이그레이션이 필요합니다"
        )
    return None


def _review_section_and_blocks(
    content: str, *, expected_sha256: str
) -> tuple[_ReviewSection | None, list[_ReviewNoteBlock]]:
    managed = _managed_review_section(
        content, expected_sha256=expected_sha256
    )
    if managed is not None:
        return managed
    legacy = _legacy_review_section(content, expected_sha256=expected_sha256)
    if legacy is not None:
        return legacy
    return None, []


def _compatible_review_blocks(
    blocks: list[_ReviewNoteBlock], requested: tuple[int, ...]
) -> list[_ReviewNoteBlock]:
    requested_set = set(requested)
    for block in blocks:
        overlap = requested_set.intersection(block.pages)
        if overlap and block.pages != requested:
            existing = ", ".join(str(page) for page in block.pages)
            incoming = ", ".join(str(page) for page in requested)
            raise ValueError(
                "기존 여러 페이지 시각 검토 블록은 페이지별로 자동 분할할 수 "
                "없습니다: "
                f"기존 [{existing}], 요청 [{incoming}]. 기존 노트와 검토 상태는 "
                "변경하지 않았습니다. 먼저 명시적인 마이그레이션으로 기존 "
                "블록을 페이지별로 분리하세요"
            )
    return [block for block in blocks if block.pages == requested]


def _visual_review_note(
    *,
    pages: list[int],
    expected_sha256: str,
    reviewer_model: str,
    status: str,
    reviewed_at: str,
    notes: str,
) -> str:
    page_label = ", ".join(str(page) for page in pages)
    return (
        f"<!-- visual-review-begin: {page_label} -->\n\n"
        f"### Pages {page_label}\n\n"
        f"<!-- visual-review-pages: {page_label} -->\n"
        f"<!-- visual-review-sha256: {expected_sha256} -->\n"
        f"<!-- visual-review-model: {reviewer_model} -->\n"
        f"<!-- visual-review-status: {status} -->\n"
        f"<!-- visual-review-reviewed-at: {reviewed_at} -->\n\n"
        f"{notes}\n\n"
        f"<!-- visual-review-end: {page_label} -->"
    )


def _managed_visual_review_section(
    *, expected_sha256: str, body: str
) -> str:
    prepared_body = body.strip()
    body_text = f"{prepared_body}\n\n" if prepared_body else ""
    return (
        "<!-- visual-review-section-begin: "
        f"sha256:{expected_sha256} -->\n"
        "## Visual verification notes\n\n"
        f"{body_text}"
        "<!-- visual-review-section-end: "
        f"sha256:{expected_sha256} -->"
    )


def _append_markdown_block(content: str, block: str) -> str:
    if not content or content.endswith("\n\n"):
        separator = ""
    elif content.endswith("\n"):
        separator = "\n"
    else:
        separator = "\n\n"
    return content + separator + block + "\n"


def _upsert_visual_review_note(
    content: str,
    *,
    pages: list[int],
    expected_sha256: str,
    reviewer_model: str,
    status: str,
    reviewed_at: str,
    notes: str,
) -> str:
    requested = tuple(pages)
    replacement = _visual_review_note(
        pages=pages,
        expected_sha256=expected_sha256,
        reviewer_model=reviewer_model,
        status=status,
        reviewed_at=reviewed_at,
        notes=notes,
    )
    section, blocks = _review_section_and_blocks(
        content, expected_sha256=expected_sha256
    )
    if section is None:
        return _append_markdown_block(
            content,
            _managed_visual_review_section(
                expected_sha256=expected_sha256,
                body=replacement,
            ),
        )

    body = content[section.body_start : section.body_end]
    exact = _compatible_review_blocks(blocks, requested)
    if not exact:
        updated_body = body.rstrip() + "\n\n" + replacement
    else:
        first_start = exact[0].start
        pieces: list[str] = []
        cursor = 0
        inserted = False
        for block in exact:
            pieces.append(body[cursor : block.start])
            if not inserted and block.start == first_start:
                pieces.append(replacement)
                inserted = True
            cursor = block.end
        pieces.append(body[cursor:])
        updated_body = "".join(pieces)

    suffix = content[section.end :]
    if not suffix:
        suffix = "\n"
    return (
        content[: section.start]
        + _managed_visual_review_section(
            expected_sha256=expected_sha256,
            body=updated_body,
        )
        + suffix
    )


def _output_path(config: Config, source: Source, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"안전하지 않은 문서 상대 경로입니다: {relative}")
    storage_key = hashlib.sha256(
        source.id.encode("utf-8") + b"\0" + relative.as_posix().encode("utf-8")
    ).hexdigest()
    return require_owned_path(
        config.documents / storage_key[:2] / f"{storage_key}.md",
        config.root,
        label="Markdown 출력 경로",
    )


def _legacy_output_path(config: Config, source: Source, relative: Path) -> Path:
    """Return the path used by releases before collision-safe storage keys."""
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"안전하지 않은 문서 상대 경로입니다: {relative}")
    return require_owned_path(
        config.documents / source.id / relative.with_suffix(".md"),
        config.root,
        label="기존 Markdown 출력 경로",
    )


def _recorded_output_path(
    config: Config,
    source: Source,
    relative: Path,
    stored_output: object,
) -> Path:
    stored = Path(str(stored_output))
    if stored.is_absolute() or ".." in stored.parts:
        raise ValueError("SQLite의 출력 경로가 안전하지 않습니다")
    canonical = _output_path(config, source, relative)
    legacy = _legacy_output_path(config, source, relative)
    allowed = {
        canonical.relative_to(config.root).as_posix(),
        legacy.relative_to(config.root).as_posix(),
    }
    if stored.as_posix() not in allowed:
        raise ValueError("SQLite의 출력 경로가 예상 경로와 일치하지 않습니다")
    return require_owned_path(
        config.root / stored,
        config.root,
        label="SQLite Markdown 출력 경로",
    )


def _collision_migration_plan(
    config: Config, documents: list[dict[str, object]]
) -> tuple[set[str], set[str]]:
    """Choose deterministic keepers for legacy paths that alias on this FS.

    The first set moves non-keepers to their hash path. The second forces a
    fresh conversion when multiple rows may already refer to the same bytes.
    """
    buckets: dict[str, list[dict[str, object]]] = {}
    for document in documents:
        raw = str(document.get("output_path") or "")
        path = Path(raw)
        if not raw or path.is_absolute() or ".." in path.parts:
            continue
        key = unicodedata.normalize("NFC", path.as_posix()).casefold()
        buckets.setdefault(key, []).append(document)

    migrate: set[str] = set()
    force: set[str] = set()
    for group in buckets.values():
        if len(group) < 2:
            continue
        raw_paths = [str(item["output_path"]) for item in group]
        paths = [config.root / Path(value) for value in raw_paths]
        exact_collision = len(set(raw_paths)) != len(raw_paths)
        existing = [path.exists() for path in paths]
        physical_collision = exact_collision
        if not physical_collision and all(existing):
            physical_collision = any(
                os.path.samefile(paths[left], paths[right])
                for left in range(len(paths))
                for right in range(left + 1, len(paths))
            )
        if not physical_collision and all(existing):
            # This is a case-sensitive filesystem where both legacy paths are
            # distinct. Preserve them rather than creating stale orphan files.
            continue

        keeper = min(
            group,
            key=lambda item: (
                not (config.root / Path(str(item["output_path"]))).exists(),
                str(item["document_key"]),
            ),
        )
        keeper_key = str(keeper["document_key"])
        migrate.update(
            str(item["document_key"])
            for item in group
            if str(item["document_key"]) != keeper_key
        )
        if physical_collision:
            force.update(str(item["document_key"]) for item in group)
    return migrate, force


@contextmanager
def _copy_for_conversion(
    pdf: Path, temporary: Path, root: Path
) -> Iterator[tuple[Path, str]]:
    temp_root = ensure_owned_directory(temporary, root, label="임시 변환 폴더")
    directory = Path(
        tempfile.mkdtemp(prefix=f"pdf-{os.getpid()}-", dir=temp_root)
    )
    require_owned_path(directory, root, label="임시 변환 폴더")
    copied = directory / "source.pdf"
    try:
        descriptor = os.open(copied, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with pdf.open("rb") as source_file, os.fdopen(descriptor, "wb") as output_file:
            shutil.copyfileobj(source_file, output_file, length=1024 * 1024)
            output_file.flush()
            os.fsync(output_file.fileno())
        copied = require_owned_path(copied, root, label="임시 PDF")
        yield copied, _hash(copied)
    finally:
        directory = require_owned_path(directory, root, label="임시 삭제 폴더")
        shutil.rmtree(directory, ignore_errors=False)


def _process_is_running(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _cleanup_stale_conversion_copies(temporary: Path, root: Path) -> int:
    """Remove project-owned PDF copies left by processes that no longer exist."""

    temp_root = ensure_owned_directory(temporary, root, label="임시 변환 폴더")
    removed = 0
    for candidate in temp_root.iterdir():
        match = re.fullmatch(r"pdf-([1-9][0-9]*)-.+", candidate.name)
        if match is None or _process_is_running(int(match.group(1))):
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        owned = require_owned_path(
            candidate,
            root,
            label="중단된 임시 PDF 폴더",
        )
        try:
            shutil.rmtree(owned, ignore_errors=False)
        except FileNotFoundError:
            continue
        removed += 1
    return removed


def _iter_source_pdfs(source: Source) -> Iterator[Path]:
    if source.kind == "file":
        yield safe_source_file(source.path, source.path)
        return

    def raise_walk_error(error: OSError) -> None:
        raise error

    for current, directory_names, file_names in os.walk(
        source.path,
        topdown=True,
        onerror=raise_walk_error,
        followlinks=False,
    ):
        current_path = Path(current)
        directory_names[:] = [
            name
            for name in directory_names
            if not (current_path / name).is_symlink()
        ]
        for name in sorted(file_names):
            candidate = current_path / name
            if candidate.suffix.casefold() != ".pdf" or candidate.is_symlink():
                continue
            yield safe_source_file(candidate, source.path)


def _document_record(
    *,
    key: str,
    source: Source,
    relative: Path,
    output: Path,
    config: Config,
    size: int,
    modified_ns: int,
    previous: dict[str, object] | None,
    **updates: object,
) -> dict[str, object]:
    record: dict[str, object] = dict(previous or {})
    if not previous:
        record.update(
            {
                "sha256": None,
                "parser_version": None,
                "converted_at": None,
            }
        )
    record.update({
        "document_key": key,
        "source_id": source.id,
        "source_path": relative.as_posix(),
        "output_path": str(output.relative_to(config.root)),
        "size": size,
        "modified_ns": modified_ns,
        "present": 1,
        "checked_at": now(),
        "missing_since": None,
        "error": None,
    })
    record.update(updates)
    return record


def sync_library(
    config: Config,
    converter: Converter = pdf_converter,
    progress: ProgressCallback | None = None,
    *,
    imported_document: str | None = None,
) -> SyncStats:
    stats = SyncStats()
    seen: set[str] = set()
    scanned_source_ids: set[str] = set()
    enabled_sources: list[Source] = []
    inventory: list[tuple[Source, Path, Path, str]] = []
    processed = 0
    document_total = 0
    phase = "discover"

    ensure_owned_directory(config.documents, config.root, label="문서 저장 폴더")
    ensure_owned_directory(config.conversations, config.root, label="대화 저장 폴더")
    ensure_owned_directory(config.assets, config.root, label="에셋 저장 폴더")
    ensure_owned_directory(config.temporary, config.root, label="임시 저장 폴더")

    with sync_lock(config.root):
        recover_imports(config)
        enabled_sources = [source for source in library_sources(config) if source.enabled]
        if imported_document is not None:
            enabled_sources = [
                source for source in enabled_sources
                if isinstance(source, ImportedSource)
                and f"{source.id}:{source.original_name}" == imported_document
            ]
            if not enabled_sources:
                raise ValueError("저장한 첨부 PDF의 정확한 문서 키를 찾을 수 없습니다")
        stats.registered_sources = len(enabled_sources)
        _cleanup_stale_conversion_copies(config.temporary, config.root)
        # Sync is an explicit write operation and therefore the migration
        # boundary for a missing or older local store. Avoid opening a writer
        # when the current schema already validates so read-only recovery checks
        # do not create extra commits.
        migrate_schema = not config.state.is_file()
        if not migrate_schema:
            try:
                with LibraryState(config.state, config.root, read_only=True):
                    pass
            except RuntimeError as error:
                if "먼저 최신 형식으로 갱신" not in str(error):
                    raise
                migrate_schema = True
        if migrate_schema:
            with LibraryState(config.state, config.root):
                pass
        recovered_document = recover_document_operation(config)
        with LibraryState(config.state, config.root) as state:
            started = state.begin_library_run(
                kind="sync",
                phase=phase,
                total=len(enabled_sources),
                counters=_progress_counters(stats),
            )
            run_id = str(started["run_id"])
            for interrupted in started["interrupted"]:
                emit_progress(
                    progress,
                    ProgressEvent(
                        run_id=str(interrupted["run_id"]),
                        phase="recovery",
                        status="interrupted",
                        current=int(interrupted["current"]),
                        total=int(interrupted["total"]),
                        counters=dict(interrupted["counters"]),
                        message=(
                            "이전에 중단된 작업의 저장 지점을 확인했습니다. "
                            "완료된 문서는 다시 변환하지 않습니다."
                        ),
                    ),
                )
            if recovered_document:
                emit_progress(
                    progress,
                    ProgressEvent(
                        run_id=run_id,
                        phase="recovery",
                        status="warning",
                        current=0,
                        total=0,
                        counters=_progress_counters(stats),
                        message="중단된 문서 저장을 안전하게 복구했습니다.",
                    ),
                )
            emit_progress(
                progress,
                ProgressEvent(
                    run_id=run_id,
                    phase=phase,
                    status="started",
                    current=0,
                    total=len(enabled_sources),
                    counters=_progress_counters(stats),
                    message="등록된 위치에서 PDF를 찾고 있습니다.",
                ),
            )

            try:
                for source_index, source in enumerate(enabled_sources, start=1):
                    source_pdfs: list[Path] = []
                    if not source.available:
                        stats.unavailable_sources += 1
                        stats.source_errors.append(
                            {
                                "source_id": source.id,
                                "path": str(source.path),
                                "error": "원본 위치를 찾을 수 없습니다",
                            }
                        )
                    elif (
                        source.kind == "directory" and not source.path.is_dir()
                    ) or (source.kind == "file" and not source.path.is_file()):
                        stats.unavailable_sources += 1
                        stats.source_errors.append(
                            {
                                "source_id": source.id,
                                "path": str(source.path),
                                "error": "원본 위치 종류가 등록 당시와 다릅니다",
                            }
                        )
                    else:
                        try:
                            source_pdfs = sorted(_iter_source_pdfs(source))
                        except (OSError, ValueError) as error:
                            if isinstance(error, PermissionError):
                                message = (
                                    "읽기 권한이 없습니다. macOS의 시스템 설정 > "
                                    "개인정보 보호 및 보안 > 파일 및 폴더에서 Codex의 "
                                    "해당 위치 읽기 권한을 확인하세요."
                                )
                            else:
                                message = str(error)
                            stats.unavailable_sources += 1
                            stats.source_errors.append(
                                {
                                    "source_id": source.id,
                                    "path": str(source.path),
                                    "error": message,
                                }
                            )
                        else:
                            scanned_source_ids.add(source.id)
                            for pdf in source_pdfs:
                                relative = source.relative_path(pdf)
                                key = f"{source.id}:{relative.as_posix()}"
                                inventory.append((source, pdf, relative, key))
                                seen.add(key)
                    stats.discovered = len(inventory)
                    state.begin_immediate()
                    state.update_library_run(
                        run_id,
                        phase=phase,
                        current=source_index,
                        total=len(enabled_sources),
                        counters=_progress_counters(stats),
                        last_item=source.id,
                    )
                    state.commit()
                    emit_progress(
                        progress,
                        ProgressEvent(
                            run_id=run_id,
                            phase=phase,
                            status="progress",
                            current=source_index,
                            total=len(enabled_sources),
                            counters=_progress_counters(stats),
                            last_item=source.id,
                        ),
                    )

                inventory.sort(key=lambda item: (item[0].id, item[2].as_posix()))
                document_total = len(inventory)
                phase = "documents"
                state.begin_immediate()
                state.update_library_run(
                    run_id,
                    phase=phase,
                    current=0,
                    total=document_total,
                    counters=_progress_counters(stats),
                )
                state.commit()
                emit_progress(
                    progress,
                    ProgressEvent(
                        run_id=run_id,
                        phase=phase,
                        status="started",
                        current=0,
                        total=document_total,
                        counters=_progress_counters(stats),
                        message=f"정리할 PDF {document_total}개를 확인했습니다.",
                    ),
                )

                migrate_outputs, force_conversions = _collision_migration_plan(
                    config, state.documents()
                )
                for source, pdf, relative, key in inventory:
                    file_stat: os.stat_result | None = None
                    previous = state.get_document(key)
                    canonical_output = _output_path(config, source, relative)
                    previous_output = (
                        _recorded_output_path(
                            config, source, relative, previous["output_path"]
                        )
                        if previous
                        else None
                    )
                    output = (
                        canonical_output
                        if previous is None or key in migrate_outputs
                        else previous_output
                    )
                    requires_conversion = (
                        key in migrate_outputs or key in force_conversions
                    )
                    item_name = _progress_item(pdf)
                    try:
                        file_stat = pdf.stat()
                        if (
                            previous
                            and not requires_conversion
                            and not isinstance(source, ImportedSource)
                            and previous["size"] == file_stat.st_size
                            and previous["modified_ns"] == file_stat.st_mtime_ns
                            and previous["parser_version"] == PARSER_VERSION
                            and previous["present"] == 1
                            and previous["error"] is None
                            and output.is_file()
                        ):
                            state.begin_immediate()
                            state.update_library_run(
                                run_id,
                                phase=phase,
                                current=processed + 1,
                                total=document_total,
                                counters=_progress_counters(
                                    stats, unchanged=stats.unchanged + 1
                                ),
                                last_item=item_name,
                            )
                            state.commit()
                            stats.unchanged += 1
                            processed += 1
                            emit_progress(
                                progress,
                                ProgressEvent(
                                    run_id=run_id,
                                    phase=phase,
                                    status="progress",
                                    current=processed,
                                    total=document_total,
                                    counters=_progress_counters(stats),
                                    last_item=item_name,
                                ),
                            )
                            continue

                        with _copy_for_conversion(
                            pdf, config.temporary, config.root
                        ) as (copied, digest):
                            if (isinstance(source, ImportedSource)
                                    and digest != source.content_sha256):
                                raise ValueError("저장한 첨부 PDF 내용이 변경되었습니다")
                            if (
                                previous
                                and not requires_conversion
                                and previous["sha256"] == digest
                                and previous["parser_version"] == PARSER_VERSION
                                and output.is_file()
                            ):
                                state.begin_immediate()
                                state.upsert_document(
                                    _document_record(
                                        key=key,
                                        source=source,
                                        relative=relative,
                                        output=output,
                                        config=config,
                                        size=file_stat.st_size,
                                        modified_ns=file_stat.st_mtime_ns,
                                        previous=previous,
                                        present=1,
                                        checked_at=now(),
                                        missing_since=None,
                                        error=None,
                                    )
                                )
                                state.update_library_run(
                                    run_id,
                                    phase=phase,
                                    current=processed + 1,
                                    total=document_total,
                                    counters=_progress_counters(
                                        stats, unchanged=stats.unchanged + 1
                                    ),
                                    last_item=item_name,
                                )
                                state.commit()
                                stats.unchanged += 1
                                processed += 1
                                emit_progress(
                                    progress,
                                    ProgressEvent(
                                        run_id=run_id,
                                        phase=phase,
                                        status="progress",
                                        current=processed,
                                        total=document_total,
                                        counters=_progress_counters(stats),
                                        last_item=item_name,
                                    ),
                                )
                                continue

                            converted = converter(copied)
                            if isinstance(converted, ConversionResult):
                                body = converted.markdown
                                review_pages = converted.review_pages
                            else:
                                body = converted
                                review_pages = {}
                            source_after = pdf.stat()
                            if (
                                source_after.st_size != file_stat.st_size
                                or source_after.st_mtime_ns != file_stat.st_mtime_ns
                            ):
                                raise RuntimeError(
                                    "읽는 동안 원본 PDF가 변경되어 변환 결과를 저장하지 않습니다"
                                )
                            content = _frontmatter(
                                source,
                                relative,
                                digest,
                                file_stat.st_mtime_ns,
                                review_pages,
                            ) + body
                            if review_pages:
                                content = _append_markdown_block(
                                    content,
                                    _managed_visual_review_section(
                                        expected_sha256=digest,
                                        body="",
                                    ),
                                )
                            with project_write_lock(config.root):
                                current_document = state.get_document(key)
                                base_reviews = state.document_reviews(key)
                                target_document = _document_record(
                                    key=key,
                                    source=source,
                                    relative=relative,
                                    output=output,
                                    config=config,
                                    size=file_stat.st_size,
                                    modified_ns=file_stat.st_mtime_ns,
                                    previous=current_document,
                                    sha256=digest,
                                    parser_version=PARSER_VERSION,
                                    present=1,
                                    converted_at=now(),
                                    checked_at=now(),
                                    missing_since=None,
                                    error=None,
                                )
                                target_reviews = _pending_review_records(
                                    key, review_pages
                                )

                                def update_progress(
                                    current_state: LibraryState,
                                    *,
                                    next_current: int = processed + 1,
                                    next_converted: int = stats.converted + 1,
                                    next_pages: int = (
                                        stats.pages_needing_review
                                        + len(review_pages)
                                    ),
                                ) -> None:
                                    current_state.update_library_run(
                                        run_id,
                                        phase=phase,
                                        current=next_current,
                                        total=document_total,
                                        counters=_progress_counters(
                                            stats,
                                            converted=next_converted,
                                            pages_needing_review=next_pages,
                                        ),
                                        last_item=item_name,
                                    )

                                journaled_document_replace(
                                    config,
                                    state,
                                    operation="sync-document",
                                    document_key=key,
                                    output=output,
                                    base_document=current_document,
                                    target_document=target_document,
                                    base_reviews=base_reviews,
                                    target_reviews=target_reviews,
                                    target_markdown=content,
                                    after_state_update=update_progress,
                                )
                            stats.converted += 1
                            stats.pages_needing_review += len(review_pages)
                            processed += 1
                            emit_progress(
                                progress,
                                ProgressEvent(
                                    run_id=run_id,
                                    phase=phase,
                                    status="progress",
                                    current=processed,
                                    total=document_total,
                                    counters=_progress_counters(stats),
                                    last_item=item_name,
                                ),
                            )
                    except Exception as error:
                        if state.connection.in_transaction:
                            state.connection.rollback()
                        # A durable document journal means the file/SQLite
                        # boundary still needs recovery. Do not hide that state
                        # behind an ordinary per-document error row.
                        if state.get_pending_document_operation() is not None:
                            raise
                        current_document = state.get_document(key)
                        fallback_output = previous_output or output
                        state.begin_immediate()
                        state.upsert_document(
                            _document_record(
                                key=key,
                                source=source,
                                relative=relative,
                                output=fallback_output,
                                config=config,
                                size=(
                                    file_stat.st_size
                                    if file_stat is not None
                                    else int(current_document.get("size", 0))
                                    if current_document
                                    else 0
                                ),
                                modified_ns=(
                                    file_stat.st_mtime_ns
                                    if file_stat is not None
                                    else int(current_document.get("modified_ns", 0))
                                    if current_document
                                    else 0
                                ),
                                previous=current_document,
                                present=1,
                                checked_at=now(),
                                error=str(error),
                            )
                        )
                        state.update_library_run(
                            run_id,
                            phase=phase,
                            current=processed + 1,
                            total=document_total,
                            counters=_progress_counters(
                                stats, failed=stats.failed + 1
                            ),
                            last_item=item_name,
                        )
                        state.commit()
                        stats.failed += 1
                        processed += 1
                        emit_progress(
                            progress,
                            ProgressEvent(
                                run_id=run_id,
                                phase=phase,
                                status="error",
                                current=processed,
                                total=document_total,
                                counters=_progress_counters(stats),
                                last_item=item_name,
                                message="이 문서를 정리하지 못했습니다.",
                            ),
                        )

                phase = "finalize"
                state.begin_immediate()
                stats.missing = state.mark_missing_except(
                    seen, scanned_source_ids
                )
                final_status = (
                    "completed_with_errors"
                    if stats.failed or stats.unavailable_sources
                    else "completed"
                )
                state.finish_library_run(
                    run_id,
                    status=final_status,
                    phase=phase,
                    current=processed,
                    total=document_total,
                    counters=_progress_counters(stats),
                )
                state.set_metadata("last_sync", now())
                state.set_metadata(
                    "last_stats", json.dumps(asdict(stats), ensure_ascii=False)
                )
                state.commit()
                emit_progress(
                    progress,
                    ProgressEvent(
                        run_id=run_id,
                        phase=phase,
                        status=final_status,
                        current=processed,
                        total=document_total,
                        counters=_progress_counters(stats),
                        message=(
                            "일부 문서를 정리하지 못했습니다."
                            if final_status == "completed_with_errors"
                            else "문서 정리를 마쳤습니다."
                        ),
                    ),
                )
            except BaseException as error:
                if state.connection.in_transaction:
                    state.connection.rollback()
                stopped_by_user = isinstance(error, (KeyboardInterrupt, SystemExit))
                failure_status = "interrupted" if stopped_by_user else "failed"
                try:
                    state.begin_immediate()
                    state.finish_library_run(
                        run_id,
                        status=failure_status,
                        phase=phase,
                        current=processed,
                        total=(
                            document_total
                            if phase != "discover"
                            else len(enabled_sources)
                        ),
                        counters=_progress_counters(stats),
                        error=str(error) or type(error).__name__,
                    )
                    state.commit()
                except BaseException:
                    if state.connection.in_transaction:
                        state.connection.rollback()
                emit_progress(
                    progress,
                    ProgressEvent(
                        run_id=run_id,
                        phase=phase,
                        status=failure_status,
                        current=processed,
                        total=(
                            document_total
                            if phase != "discover"
                            else len(enabled_sources)
                        ),
                        counters=_progress_counters(stats),
                        message=(
                            "작업을 중단했습니다. 저장된 지점부터 다시 시작할 수 있습니다."
                            if stopped_by_user
                            else "작업 중 문제가 발생했습니다. 저장된 결과는 유지했습니다."
                        ),
                    ),
                )
                raise
    return stats


def library_status(config: Config) -> dict[str, object]:
    recover_document_operation(config)
    with LibraryState(config.state, config.root) as state:
        return state.status()


def pending_reviews(config: Config) -> list[dict[str, object]]:
    recover_document_operation(config)
    sources = {source.id: source for source in library_sources(config)}
    with LibraryState(config.state, config.root) as state:
        reviews = state.pending_reviews()
    for review in reviews:
        source = sources.get(str(review["source_id"]))
        if source is None or not source.available:
            review["original_pdf"] = None
            review["source_available"] = False
            continue
        relative = Path(str(review["source_path"]))
        review["original_pdf"] = str(
            safe_source_file(source.document_path(relative), source.path)
        )
        review["source_available"] = True
    return reviews


def render_review_pages(
    config: Config, document_key: str, pages: list[int] | None = None, dpi: int = 220
) -> RenderResult:
    recover_document_operation(config)
    if dpi < 120 or dpi > 400:
        raise ValueError("DPI는 120에서 400 사이여야 합니다")
    sources = {source.id: source for source in library_sources(config)}
    with LibraryState(config.state, config.root) as state:
        document = state.get_document(document_key)
        if document is None or document["present"] != 1:
            raise ValueError(f"현재 존재하는 문서를 찾을 수 없습니다: {document_key}")
        pending = [
            int(item["page_number"])
            for item in state.pending_reviews()
            if item["document_key"] == document_key
        ]

    selected = sorted(set(pages if pages is not None else pending))
    if not selected:
        return RenderResult(str(document.get("sha256") or ""), ())
    source_id = str(document["source_id"])
    if source_id not in sources:
        raise ValueError(f"등록되지 않은 source id입니다: {source_id}")
    source = sources[source_id]
    relative = Path(str(document["source_path"]))
    pdf = safe_source_file(source.document_path(relative), source.path)
    expected_digest = str(document.get("sha256") or "")
    if not expected_digest:
        raise ValueError("문서 해시가 없습니다. 먼저 동기화를 다시 실행하세요")

    try:
        import pypdfium2 as pdfium
    except ImportError as error:
        raise RuntimeError(
            "pypdfium2가 없습니다. 먼저 install.sh를 실행하세요."
        ) from error

    rendered: list[Path] = []
    with _copy_for_conversion(pdf, config.temporary, config.root) as (
        copied,
        current_digest,
    ):
        if current_digest != expected_digest:
            raise ValueError(
                "원본 PDF가 마지막 동기화 후 변경되었습니다. 먼저 sync를 실행하세요"
            )
        review_root = ensure_owned_directory(
            config.temporary / "review" / source_id,
            config.root,
            label="페이지 렌더링 폴더",
        )
        output_directory = Path(tempfile.mkdtemp(prefix="render-", dir=review_root))
        require_owned_path(output_directory, config.root, label="페이지 렌더링 폴더")
        document_pdf = pdfium.PdfDocument(str(copied))
        try:
            for page_number in selected:
                if page_number < 1 or page_number > len(document_pdf):
                    raise ValueError(
                        f"페이지 번호는 1에서 {len(document_pdf)} 사이여야 합니다"
                    )
                output = require_owned_path(
                    output_directory / f"page-{page_number:04d}.png",
                    config.root,
                    label="페이지 이미지 경로",
                )
                page = document_pdf[page_number - 1]
                try:
                    bitmap = page.render(scale=dpi / 72)
                    try:
                        image = bitmap.to_pil()
                        image.save(output, format="PNG")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                rendered.append(output)
        finally:
            document_pdf.close()
    return RenderResult(expected_digest, tuple(rendered))


def complete_reviews(
    config: Config,
    document_key: str,
    pages: list[int],
    *,
    expected_sha256: str,
    status: str,
    reviewer_model: str,
    notes: str | None,
    visual_notes: str | None = None,
) -> int:
    normalized_pages = normalize_review_pages(pages)
    if status not in {"verified", "needs_review"}:
        raise ValueError(f"지원하지 않는 검토 상태입니다: {status}")
    if len(normalized_pages) != 1:
        raise ValueError(
            "시각 검토 결과는 페이지 하나당 블록 하나로 저장합니다. "
            "review-complete를 페이지별로 한 번씩 실행하세요"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("검토한 문서의 SHA-256이 올바르지 않습니다")
    reviewer_model = validate_reviewer_model(reviewer_model)
    if status == "verified" and visual_notes is None:
        raise ValueError(
            "verified로 저장하려면 --visual-notes-stdin으로 해당 페이지의 "
            "최종 시각 검토 노트를 제출해야 합니다. --notes만으로는 "
            "검증 완료로 저장할 수 없습니다"
        )
    prepared_notes: str | None = None
    if visual_notes is not None:
        prepared_notes = visual_notes.strip()
        if not prepared_notes:
            raise ValueError("시각 검토 노트가 비어 있습니다")
        if len(prepared_notes.encode("utf-8")) > 1024 * 1024:
            raise ValueError("시각 검토 노트는 1 MiB 이하여야 합니다")
        if _VISUAL_REVIEW_RESERVED_MARKER_RE.search(prepared_notes):
            raise ValueError(
                "시각 검토 노트에 예약된 visual-review 표식을 사용할 수 없습니다"
            )
        if _BASE_PAGE_MARKER_RE.search(prepared_notes):
            raise ValueError(
                "시각 검토 노트에 예약된 PDF 페이지 표식을 사용할 수 없습니다"
            )

    recover_document_operation(config)
    with project_write_lock(config.root), LibraryState(
        config.state, config.root
    ) as state:
        document = state.get_document(document_key)
        if document is None:
            raise ValueError(f"문서를 찾을 수 없습니다: {document_key}")
        stored_digest = str(document.get("sha256") or "")
        if stored_digest != expected_sha256:
            raise ValueError(
                "렌더링 후 문서 버전이 바뀌었습니다. 페이지를 다시 렌더링하세요"
            )
        sources = {source.id: source for source in library_sources(config)}
        source_id = str(document["source_id"])
        if source_id not in sources:
            raise ValueError(f"등록되지 않은 source id입니다: {source_id}")
        source = sources[source_id]
        relative = Path(str(document["source_path"]))
        pdf = safe_source_file(source.document_path(relative), source.path)
        with _copy_for_conversion(pdf, config.temporary, config.root) as (
            _,
            current_digest,
        ):
            if current_digest != expected_sha256:
                raise ValueError(
                    "원본 PDF가 검토 중 변경되었습니다. 먼저 sync를 실행하세요"
                )
        markdown = _recorded_output_path(
            config, source, relative, document["output_path"]
        )
        if not markdown.is_file():
            raise ValueError(f"검토할 Markdown을 찾을 수 없습니다: {markdown}")
        markdown = reject_linked_file(
            markdown, config.root, label="Markdown 검토 대상"
        )
        content = markdown.read_text(encoding="utf-8")
        _, existing_blocks = _review_section_and_blocks(
            content, expected_sha256=expected_sha256
        )
        exact_blocks = _compatible_review_blocks(
            existing_blocks, tuple(normalized_pages)
        )
        if prepared_notes is None and exact_blocks:
            raise ValueError(
                "기존 시각 검토 블록의 상태와 출처 정보를 함께 갱신하려면 "
                "--visual-notes-stdin으로 해당 페이지의 최종 노트를 다시 "
                "제출하세요"
            )
        (
            frontmatter_lines,
            visual_review_index,
            pending_pages_index,
            frontmatter_closing,
        ) = _validated_document_frontmatter(
            content,
            expected_sha256=expected_sha256,
            expected_source_id=source.id,
            expected_source_path=relative.as_posix(),
        )

        reviewed_at = now()
        base_reviews = state.document_reviews(document_key)
        target_reviews = [dict(review) for review in base_reviews]
        updated = 0
        for review in target_reviews:
            if int(review["page_number"]) not in normalized_pages:
                continue
            review["status"] = status
            review["reviewed_at"] = reviewed_at
            review["reviewer_model"] = reviewer_model
            review["notes"] = notes
            updated += 1
        if updated != len(normalized_pages):
            raise ValueError("검토 대기 중인 페이지와 요청한 페이지가 일치하지 않습니다")
        counts: dict[str, int] = {}
        for review in target_reviews:
            review_status = str(review["status"])
            counts[review_status] = counts.get(review_status, 0) + 1
        if counts.get("pending", 0):
            overall = "pending"
        elif counts.get("needs_review", 0):
            overall = "needs-review"
        else:
            overall = "verified"
        frontmatter_lines[visual_review_index] = (
            f"visual_review: {json.dumps(overall)}\n"
        )
        pending_pages = sorted(
            int(review["page_number"])
            for review in target_reviews
            if review["status"] in {"pending", "needs_review"}
        )
        pending_line = (
            "visual_review_pending_pages: "
            + json.dumps(pending_pages, ensure_ascii=False)
            + "\n"
        )
        if pending_pages_index is None:
            frontmatter_lines.insert(frontmatter_closing, pending_line)
        else:
            frontmatter_lines[pending_pages_index] = pending_line
        content = "".join(frontmatter_lines)
        if prepared_notes is not None:
            content = _upsert_visual_review_note(
                content,
                pages=normalized_pages,
                expected_sha256=expected_sha256,
                reviewer_model=reviewer_model,
                status=status,
                reviewed_at=reviewed_at,
                notes=prepared_notes,
            )
        journaled_document_replace(
            config,
            state,
            operation="review-page",
            document_key=document_key,
            output=markdown,
            base_document=document,
            target_document=document,
            base_reviews=base_reviews,
            target_reviews=target_reviews,
            target_markdown=content,
        )
        return updated
