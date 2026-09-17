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
from .safety import (
    atomic_text,
    ensure_owned_directory,
    reject_linked_file,
    require_owned_path,
    safe_source_file,
)
from .state import LibraryState, now


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
    }
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
) -> tuple[list[str], int]:
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
    values: dict[str, object] = {}
    indexes: dict[str, int] = {}
    for index in range(1, closing):
        key, separator, raw_value = lines[index].rstrip("\r\n").partition(":")
        if not separator or key not in required:
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
    return lines, indexes["visual_review"]


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
    directory = Path(tempfile.mkdtemp(prefix="pdf-", dir=temp_root))
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


def sync_library(config: Config, converter: Converter = pdf_converter) -> SyncStats:
    stats = SyncStats(
        registered_sources=sum(1 for source in config.sources if source.enabled)
    )
    seen: set[str] = set()
    scanned_source_ids: set[str] = set()

    ensure_owned_directory(config.documents, config.root, label="문서 저장 폴더")
    ensure_owned_directory(config.conversations, config.root, label="대화 저장 폴더")
    ensure_owned_directory(config.assets, config.root, label="에셋 저장 폴더")
    ensure_owned_directory(config.temporary, config.root, label="임시 저장 폴더")

    with LibraryState(config.state, config.root) as state:
        migrate_outputs, force_conversions = _collision_migration_plan(
            config, state.documents()
        )
        for source in config.sources:
            if not source.enabled:
                continue
            if not source.available:
                stats.unavailable_sources += 1
                stats.source_errors.append(
                    {
                        "source_id": source.id,
                        "path": str(source.path),
                        "error": "원본 위치를 찾을 수 없습니다",
                    }
                )
                continue
            if (source.kind == "directory" and not source.path.is_dir()) or (
                source.kind == "file" and not source.path.is_file()
            ):
                stats.unavailable_sources += 1
                stats.source_errors.append(
                    {
                        "source_id": source.id,
                        "path": str(source.path),
                        "error": "원본 위치 종류가 등록 당시와 다릅니다",
                    }
                )
                continue
            try:
                pdfs = sorted(_iter_source_pdfs(source))
            except (OSError, ValueError) as error:
                if isinstance(error, PermissionError):
                    message = (
                        "읽기 권한이 없습니다. macOS의 시스템 설정 > 개인정보 보호 및 "
                        "보안 > 파일 및 폴더에서 Codex의 해당 위치 읽기 권한을 확인하세요."
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
                continue

            scanned_source_ids.add(source.id)
            for pdf in pdfs:
                relative = source.relative_path(pdf)
                key = f"{source.id}:{relative.as_posix()}"
                seen.add(key)
                stats.discovered += 1

                file_stat = pdf.stat()
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
                if (
                    previous
                    and not requires_conversion
                    and previous["size"] == file_stat.st_size
                    and previous["modified_ns"] == file_stat.st_mtime_ns
                    and previous["parser_version"] == PARSER_VERSION
                    and previous["present"] == 1
                    and previous["error"] is None
                    and output.is_file()
                ):
                    stats.unchanged += 1
                    continue

                try:
                    with _copy_for_conversion(
                        pdf, config.temporary, config.root
                    ) as (copied, digest):
                        if (
                            previous
                            and not requires_conversion
                            and previous["sha256"] == digest
                            and previous["parser_version"] == PARSER_VERSION
                            and output.is_file()
                        ):
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
                            stats.unchanged += 1
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
                        atomic_text(output, content, config.root)
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
                                sha256=digest,
                                parser_version=PARSER_VERSION,
                                present=1,
                                converted_at=now(),
                                checked_at=now(),
                                missing_since=None,
                                error=None,
                            )
                        )
                        state.replace_reviews(key, review_pages)
                        stats.converted += 1
                        stats.pages_needing_review += len(review_pages)
                except Exception as error:
                    state.upsert_document(
                        _document_record(
                            key=key,
                            source=source,
                            relative=relative,
                            output=previous_output or output,
                            config=config,
                            size=file_stat.st_size,
                            modified_ns=file_stat.st_mtime_ns,
                            previous=previous,
                            present=1,
                            checked_at=now(),
                            error=str(error),
                        )
                    )
                    stats.failed += 1

        stats.missing = state.mark_missing_except(seen, scanned_source_ids)
        state.set_metadata("last_sync", now())
        state.set_metadata("last_stats", json.dumps(asdict(stats), ensure_ascii=False))
    return stats


def library_status(config: Config) -> dict[str, object]:
    with LibraryState(config.state, config.root) as state:
        return state.status()


def pending_reviews(config: Config) -> list[dict[str, object]]:
    sources = {source.id: source for source in config.sources}
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
    if dpi < 120 or dpi > 400:
        raise ValueError("DPI는 120에서 400 사이여야 합니다")
    sources = {source.id: source for source in config.sources}
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
    with LibraryState(config.state, config.root) as state:
        document = state.get_document(document_key)
        if document is None:
            raise ValueError(f"문서를 찾을 수 없습니다: {document_key}")
        stored_digest = str(document.get("sha256") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ValueError("검토한 문서의 SHA-256이 올바르지 않습니다")
        if stored_digest != expected_sha256:
            raise ValueError(
                "렌더링 후 문서 버전이 바뀌었습니다. 페이지를 다시 렌더링하세요"
            )
        sources = {source.id: source for source in config.sources}
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
        frontmatter_lines, visual_review_index = _validated_document_frontmatter(
            content,
            expected_sha256=expected_sha256,
            expected_source_id=source.id,
            expected_source_path=relative.as_posix(),
        )
        prepared_notes: str | None = None
        if visual_notes is not None:
            prepared_notes = visual_notes.strip()
            if not prepared_notes:
                raise ValueError("시각 검토 노트가 비어 있습니다")
            if len(prepared_notes.encode("utf-8")) > 1024 * 1024:
                raise ValueError("시각 검토 노트는 1 MiB 이하여야 합니다")

        updated = state.complete_reviews(
            document_key,
            pages,
            status=status,
            reviewer_model=reviewer_model,
            notes=notes,
        )
        if updated != len(set(pages)):
            raise ValueError("검토 대기 중인 페이지와 요청한 페이지가 일치하지 않습니다")
        counts = state.review_counts(document_key)
        if counts.get("pending", 0):
            overall = "pending"
        elif counts.get("needs_review", 0):
            overall = "needs-review"
        else:
            overall = "verified"
        frontmatter_lines[visual_review_index] = (
            f"visual_review: {json.dumps(overall)}\n"
        )
        content = "".join(frontmatter_lines)
        if prepared_notes is not None:
            if "\n## Visual verification notes\n" not in content:
                content = content.rstrip() + "\n\n## Visual verification notes\n"
            reviewed_pages = ", ".join(str(page) for page in sorted(set(pages)))
            content = (
                content.rstrip()
                + f"\n\n### Pages {reviewed_pages}\n\n"
                + f"<!-- visual-review-pages: {reviewed_pages} -->\n\n"
                + f"<!-- visual-review-sha256: {expected_sha256} -->\n\n"
                + prepared_notes
                + "\n"
            )
        atomic_text(markdown, content, config.root)
        return updated
