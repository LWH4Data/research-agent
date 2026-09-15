from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .config import Config, Source
from .state import LibraryState, now


PARSER_NAME = "pypdf"
PARSER_VERSION = "pypdf-v2-review-queue"


@dataclass(frozen=True)
class ConversionResult:
    markdown: str
    review_pages: dict[int, list[str]]


Converter = Callable[[Path], str | ConversionResult]


@dataclass
class SyncStats:
    discovered: int = 0
    converted: int = 0
    unchanged: int = 0
    missing: int = 0
    failed: int = 0
    pages_needing_review: int = 0


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


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
        "type": "paper",
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


def _output_path(config: Config, source: Source, relative: Path) -> Path:
    return config.documents / source.id / relative.with_suffix(".md")


def _copy_for_conversion(pdf: Path, temporary: Path) -> tuple[Path, str]:
    temporary.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pdf-", dir=temporary) as directory:
        copied = Path(directory) / pdf.name
        shutil.copyfile(pdf, copied)
        digest = _hash(copied)
        durable = temporary / f"current-{digest[:16]}.pdf"
        shutil.copyfile(copied, durable)
    return durable, digest


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
    record: dict[str, object] = {
        "document_key": key,
        "source_id": source.id,
        "source_path": relative.as_posix(),
        "output_path": str(output.relative_to(config.root)),
        "size": size,
        "modified_ns": modified_ns,
        "sha256": None,
        "parser_version": None,
        "present": 1,
        "converted_at": None,
        "checked_at": now(),
        "missing_since": None,
        "error": None,
    }
    if previous:
        record.update(previous)
    record.update(updates)
    return record


def sync_library(config: Config, converter: Converter = pdf_converter) -> SyncStats:
    stats = SyncStats()
    seen: set[str] = set()

    config.documents.mkdir(parents=True, exist_ok=True)
    config.conversations.mkdir(parents=True, exist_ok=True)
    config.assets.mkdir(parents=True, exist_ok=True)
    config.temporary.mkdir(parents=True, exist_ok=True)

    with LibraryState(config.state) as state:
        for source in config.sources:
            pdfs = sorted(
                path
                for path in source.path.rglob("*")
                if path.is_file() and path.suffix.casefold() == ".pdf"
            )
            for pdf in pdfs:
                relative = pdf.relative_to(source.path)
                key = f"{source.id}:{relative.as_posix()}"
                seen.add(key)
                stats.discovered += 1

                file_stat = pdf.stat()
                previous = state.get_document(key)
                output = _output_path(config, source, relative)
                if (
                    previous
                    and previous["size"] == file_stat.st_size
                    and previous["modified_ns"] == file_stat.st_mtime_ns
                    and previous["parser_version"] == PARSER_VERSION
                    and previous["present"] == 1
                    and output.is_file()
                ):
                    stats.unchanged += 1
                    continue

                copied: Path | None = None
                try:
                    copied, digest = _copy_for_conversion(pdf, config.temporary)
                    if (
                        previous
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
                    content = _frontmatter(
                        source, relative, digest, file_stat.st_mtime_ns, review_pages
                    ) + body
                    _atomic_text(output, content)
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
                            output=output,
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
                finally:
                    if copied is not None:
                        copied.unlink(missing_ok=True)

        stats.missing = state.mark_missing_except(seen)
        state.set_metadata("last_sync", now())
        state.set_metadata("last_stats", json.dumps(asdict(stats), ensure_ascii=False))
    return stats


def library_status(config: Config) -> dict[str, object]:
    with LibraryState(config.state) as state:
        return state.status()


def pending_reviews(config: Config) -> list[dict[str, object]]:
    source_paths = {source.id: source.path for source in config.sources}
    with LibraryState(config.state) as state:
        reviews = state.pending_reviews()
    for review in reviews:
        review["original_pdf"] = str(
            source_paths[str(review["source_id"])] / str(review["source_path"])
        )
    return reviews


def render_review_pages(
    config: Config, document_key: str, pages: list[int] | None = None, dpi: int = 220
) -> list[Path]:
    if dpi < 120 or dpi > 400:
        raise ValueError("DPI는 120에서 400 사이여야 합니다")
    source_paths = {source.id: source.path for source in config.sources}
    with LibraryState(config.state) as state:
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
        return []
    pdf = source_paths[str(document["source_id"])] / str(document["source_path"])
    output_directory = (
        config.temporary
        / "review"
        / str(document["source_id"])
        / Path(str(document["source_path"])).with_suffix("")
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for page in selected:
        if page < 1:
            raise ValueError("페이지 번호는 1 이상이어야 합니다")
        prefix = output_directory / f"page-{page:04d}"
        command = [
            "pdftoppm",
            "-f",
            str(page),
            "-l",
            str(page),
            "-r",
            str(dpi),
            "-png",
            "-singlefile",
            str(pdf),
            str(prefix),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError(
                "pdftoppm을 찾을 수 없어 페이지 이미지를 만들 수 없습니다"
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                error.stderr.strip() or "PDF 페이지 렌더링에 실패했습니다"
            ) from error
        rendered.append(prefix.with_suffix(".png"))
    return rendered


def complete_reviews(
    config: Config,
    document_key: str,
    pages: list[int],
    *,
    status: str,
    reviewer_model: str,
    notes: str | None,
) -> int:
    with LibraryState(config.state) as state:
        updated = state.complete_reviews(
            document_key,
            pages,
            status=status,
            reviewer_model=reviewer_model,
            notes=notes,
        )
        document = state.get_document(document_key)
        counts = state.review_counts(document_key)
    if document is not None:
        if counts.get("pending", 0):
            overall = "pending"
        elif counts.get("needs_review", 0):
            overall = "needs-review"
        else:
            overall = "verified"
        markdown = config.root / str(document["output_path"])
        if markdown.is_file():
            content = markdown.read_text(encoding="utf-8")
            content = re.sub(
                r'^visual_review: .*$',
                f'visual_review: {json.dumps(overall)}',
                content,
                count=1,
                flags=re.MULTILINE,
            )
            _atomic_text(markdown, content)
    return updated
