from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .config import Config, Source


Converter = Callable[[Path], str]


@dataclass
class SyncStats:
    discovered: int = 0
    converted: int = 0
    unchanged: int = 0
    missing: int = 0
    failed: int = 0


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "documents": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(f"상태 파일을 읽을 수 없습니다: {path}: {error}") from error


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


def markitdown_converter(path: Path) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError as error:
        raise RuntimeError("MarkItDown이 없습니다. 먼저 `uv sync`를 실행하세요.") from error

    result = MarkItDown(enable_plugins=False).convert(str(path))
    text = getattr(result, "text_content", None)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("변환 결과가 비어 있습니다")
    return text.strip() + "\n"


def _frontmatter(source: Source, relative: Path, digest: str, modified_ns: int) -> str:
    metadata = {
        "document_id": f"sha256:{digest}",
        "source_id": source.id,
        "source_path": relative.as_posix(),
        "source_modified_ns": modified_ns,
        "parsed_at": _now(),
        "language": "unknown",
        "parser": "markitdown",
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


def sync_library(config: Config, converter: Converter = markitdown_converter) -> SyncStats:
    state = _load_state(config.state)
    documents: dict[str, Any] = state.setdefault("documents", {})
    stats = SyncStats()
    seen: set[str] = set()

    config.documents.mkdir(parents=True, exist_ok=True)
    config.conversations.mkdir(parents=True, exist_ok=True)
    config.temporary.mkdir(parents=True, exist_ok=True)

    for source in config.sources:
        pdfs = sorted(
            path for path in source.path.rglob("*")
            if path.is_file() and path.suffix.casefold() == ".pdf"
        )
        for pdf in pdfs:
            relative = pdf.relative_to(source.path)
            key = f"{source.id}:{relative.as_posix()}"
            seen.add(key)
            stats.discovered += 1

            file_stat = pdf.stat()
            previous = documents.get(key, {})
            output = _output_path(config, source, relative)
            if (
                previous.get("size") == file_stat.st_size
                and previous.get("modified_ns") == file_stat.st_mtime_ns
                and previous.get("present") is True
                and output.is_file()
            ):
                stats.unchanged += 1
                continue

            copied: Path | None = None
            try:
                copied, digest = _copy_for_conversion(pdf, config.temporary)
                if previous.get("sha256") == digest and output.is_file():
                    previous.update(
                        size=file_stat.st_size,
                        modified_ns=file_stat.st_mtime_ns,
                        present=True,
                        checked_at=_now(),
                    )
                    stats.unchanged += 1
                    continue

                body = converter(copied)
                content = _frontmatter(source, relative, digest, file_stat.st_mtime_ns) + body
                _atomic_text(output, content)
                documents[key] = {
                    "source_id": source.id,
                    "source_path": relative.as_posix(),
                    "output": str(output.relative_to(config.root)),
                    "size": file_stat.st_size,
                    "modified_ns": file_stat.st_mtime_ns,
                    "sha256": digest,
                    "present": True,
                    "converted_at": _now(),
                    "error": None,
                }
                stats.converted += 1
            except Exception as error:
                documents[key] = {
                    **previous,
                    "source_id": source.id,
                    "source_path": relative.as_posix(),
                    "size": file_stat.st_size,
                    "modified_ns": file_stat.st_mtime_ns,
                    "present": True,
                    "checked_at": _now(),
                    "error": str(error),
                }
                stats.failed += 1
            finally:
                if copied is not None:
                    copied.unlink(missing_ok=True)

    for key, document in documents.items():
        if key not in seen and document.get("present") is not False:
            document["present"] = False
            document["missing_since"] = _now()
            stats.missing += 1

    state["last_sync"] = _now()
    state["last_stats"] = asdict(stats)
    _atomic_text(config.state, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return stats


def library_status(config: Config) -> dict[str, Any]:
    state = _load_state(config.state)
    documents = state.get("documents", {})
    return {
        "last_sync": state.get("last_sync"),
        "tracked": len(documents),
        "present": sum(1 for item in documents.values() if item.get("present") is True),
        "missing": sum(1 for item in documents.values() if item.get("present") is False),
        "failed": sum(1 for item in documents.values() if item.get("error")),
        "last_stats": state.get("last_stats"),
    }

