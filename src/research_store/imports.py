"""Durable, content-addressed snapshots of explicitly saved PDF attachments.

These are owned copies, never entries in the external read-only sources config.
A directory rename publishes the PDF and its metadata together. Interrupted
unpublished copies are discarded on the next import or synchronization.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time
from typing import BinaryIO

from .config import Config, Source
from .locking import conversation_lock as project_write_lock, sync_lock
from .operations import recover_document_operation
from .safety import _open_owned_directory, reject_linked_file, require_owned_path
from .state import LibraryState, now


MAX_PDF_BYTES = 256 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}")
_PENDING = re.compile(r"\.pending-[0-9a-f]{24}")


@dataclass(frozen=True)
class ImportedSource(Source):
    original_name: str = ""
    origin_path: str | None = None
    imported_at: str = ""
    content_sha256: str = ""

    def relative_path(self, pdf: Path) -> Path:
        return Path(self.original_name)

    def document_path(self, relative: Path) -> Path:
        if relative != Path(self.original_name):
            raise ValueError("저장한 첨부 PDF의 파일 이름과 일치하지 않습니다")
        return self.path


def _filename(value: str) -> str:
    if (not isinstance(value, str) or not value or value in {".", ".."}
            or "/" in value or "\\" in value or "\0" in value
            or Path(value).suffix.casefold() != ".pdf"
            or len(value.encode("utf-8")) > 255):
        raise ValueError("첨부 PDF의 파일 이름이 올바르지 않습니다")
    return value


def _directory(config: Config) -> Path:
    return require_owned_path(config.root / ".research-store/imports", config.root,
                              label="첨부 PDF 저장 폴더")


def _source(config: Config, directory: Path) -> ImportedSource:
    metadata_path = reject_linked_file(directory / "metadata.json", config.root,
                                       label="첨부 PDF 정보")
    if metadata_path.stat().st_size > 8192:
        raise ValueError("첨부 PDF 정보가 너무 큽니다")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("첨부 PDF 정보를 읽을 수 없습니다") from error
    if (not isinstance(metadata, dict) or metadata.get("schema_version") != 1
            or metadata.get("sha256") != directory.name
            or not isinstance(metadata.get("imported_at"), str)
            or not metadata["imported_at"]
            or not isinstance(metadata.get("size"), int)
            or not 0 < metadata["size"] <= MAX_PDF_BYTES
            or (metadata.get("origin_path") is not None
                and not isinstance(metadata["origin_path"], str))):
        raise ValueError("첨부 PDF 정보가 저장 구조와 일치하지 않습니다")
    name = _filename(metadata.get("original_name"))
    pdf = reject_linked_file(directory / "document.pdf", config.root,
                            label="저장한 첨부 PDF")
    # Missing copies remain identifiable for unavailable-source reporting.
    if pdf.exists() and pdf.stat().st_size != metadata["size"]:
        raise ValueError("저장한 첨부 PDF의 크기가 변경되었습니다")
    return ImportedSource("import-" + directory.name, pdf, "file", True,
                          name, metadata.get("origin_path"),
                          metadata["imported_at"], directory.name)


def imported_sources(config: Config) -> tuple[ImportedSource, ...]:
    directory = _directory(config)
    if not directory.exists():
        return ()
    sources = []
    for child in sorted(directory.iterdir()):
        if _PENDING.fullmatch(child.name):
            continue
        if not _DIGEST.fullmatch(child.name):
            raise ValueError(f"알 수 없는 첨부 PDF 저장 항목입니다: {child.name}")
        require_owned_path(child, config.root, label="첨부 PDF 항목")
        if not child.is_dir():
            raise ValueError("첨부 PDF 항목은 폴더여야 합니다")
        sources.append(_source(config, child))
    return tuple(sources)


def library_sources(config: Config) -> tuple[Source, ...]:
    sources = config.sources + imported_sources(config)
    if len({source.id for source in sources}) != len(sources):
        raise ValueError("첨부 PDF와 원본 위치의 ID가 충돌합니다")
    return sources


def _discard_pending(parent_fd: int, name: str) -> None:
    """Remove only fixed private staging files, using anchored descriptors."""
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                 dir_fd=parent_fd)
    try:
        entries = os.listdir(fd)
        if set(entries) - {"document.pdf", "metadata.json"}:
            raise ValueError("중단된 첨부 PDF 폴더에 알 수 없는 파일이 있습니다")
        for entry in entries:
            info = os.stat(entry, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("중단된 첨부 PDF 파일이 안전하지 않습니다")
        for entry in entries:
            os.unlink(entry, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def recover_imports(config: Config) -> None:
    """Caller holds sync_lock; never follows a staged symlink."""
    directory = _directory(config)
    if not directory.exists():
        return
    fd, _ = _open_owned_directory(directory, config.root,
                                   label="첨부 PDF 저장 폴더", create=False)
    try:
        for name in os.listdir(fd):
            if _PENDING.fullmatch(name):
                _discard_pending(fd, name)
    finally:
        os.close(fd)


def _validate_pdf(path: Path) -> None:
    from pypdf import PdfReader
    try:
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError("PDF 파일 형식이 아닙니다")
            handle.seek(0)
            reader = PdfReader(handle)
            if reader.is_encrypted:
                raise ValueError("암호화된 PDF는 첨부 저장을 지원하지 않습니다")
            if not reader.pages:
                raise ValueError("페이지가 없는 PDF입니다")
    except Exception as error:
        raise ValueError(f"첨부 PDF를 읽을 수 없습니다: {error}") from error


def import_pdf(config: Config, stream: BinaryIO, *, name: str,
               origin_path: str | None = None, request_id: str | None = None,
               item_id: str | None = None) -> dict[str, object]:
    """Store one PDF snapshot. Conversion is a separate resumable sync step."""
    name = _filename(name)
    if (request_id is None) != (item_id is None):
        raise ValueError("접수 요청 ID와 항목 ID를 함께 지정해야 합니다")
    with sync_lock(config.root):
        with project_write_lock(config.root):
            with LibraryState(config.state, config.root):
                pass
            recover_document_operation(config, lock_held=True)
            _validate_intake_authority(config, request_id, item_id)
        recover_imports(config)
        parent_fd, directory = _open_owned_directory(
            _directory(config), config.root, label="첨부 PDF 저장 폴더", create=True)
        staging = ".pending-" + secrets.token_hex(12)
        published = False
        try:
            os.mkdir(staging, mode=0o700, dir_fd=parent_fd)
            fd = os.open(staging, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=parent_fd)
            try:
                pdf_fd = os.open("document.pdf", os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                digest = hashlib.sha256()
                size = 0
                with os.fdopen(pdf_fd, "wb") as output:
                    while True:
                        chunk = stream.read(min(1024 * 1024, MAX_PDF_BYTES - size + 1))
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_PDF_BYTES:
                            raise ValueError("첨부 PDF는 256 MiB 이하여야 합니다")
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                _validate_pdf(directory / staging / "document.pdf")
                sha256 = digest.hexdigest()
                target = directory / sha256
                source_id = "import-" + sha256
                if any(source.id == source_id for source in config.sources):
                    raise ValueError("첨부 PDF와 원본 위치의 ID가 충돌합니다")
                with project_write_lock(config.root), LibraryState(config.state, config.root) as state:
                    if target.exists() or target.is_symlink():
                        require_owned_path(target, config.root, label="첨부 PDF 항목")
                        existing = _source(config, target)
                        with existing.path.open("rb") as saved:
                            if hashlib.file_digest(saved, "sha256").hexdigest() != sha256:
                                raise ValueError("기존 첨부 PDF 내용이 변경되었습니다")
                        source = existing
                        duplicate = True
                        _record_import_intake(config, request_id, item_id, f"{source.id}:{source.original_name}", sha256, state=state)
                    else:
                        metadata = {"schema_version": 1, "sha256": sha256,
                                    "original_name": name, "origin_path": origin_path,
                                    "imported_at": now(), "size": size}
                        body = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
                        if len(body) > 8192:
                            raise ValueError("첨부 PDF 정보가 너무 큽니다")
                        metadata_fd = os.open("metadata.json", os.O_WRONLY | os.O_CREAT
                                              | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                        with os.fdopen(metadata_fd, "wb") as output:
                            output.write(body)
                            output.flush()
                            os.fsync(output.fileno())
                        os.fsync(fd)
                        # Durable association precedes publication. If the caller
                        # dies after rename, the receipt finds this owned copy even
                        # after the original attachment path has disappeared.
                        _record_import_intake(config, request_id, item_id, f"{source_id}:{name}", sha256, state=state)
                        os.rename(staging, sha256, src_dir_fd=parent_fd,
                                  dst_dir_fd=parent_fd)
                        published = True
                        os.fsync(parent_fd)
                        source = _source(config, target)
                        duplicate = False
                    return {"document_key": f"{source.id}:{source.original_name}",
                            "sha256": sha256, "original_name": source.original_name,
                            "stored_pdf": str(source.path), "duplicate": duplicate,
                            "stored": True, "next_step": "sync"}
            finally:
                os.close(fd)
        finally:
            try:
                if not published and staging in os.listdir(parent_fd):
                    _discard_pending(parent_fd, staging)
            finally:
                os.close(parent_fd)


def _validate_intake_authority(config: Config, request_id: str | None,
                               item_id: str | None) -> None:
    """Recheck current intake intent under storage; never acquire control."""
    if request_id is None:
        return  # Explicit standalone import remains a separate operation.
    from .review_lifecycle import DIRECTORY, STATE_FILE, read_record
    lifecycle = reject_linked_file(config.root / DIRECTORY / STATE_FILE,
                                   config.root, label="첨부 접수 권한")
    if not lifecycle.exists():
        return  # Compatibility for stores that have never adopted lifecycle.
    request = read_record(config.root)["requests"].get(request_id)
    if (request is None or request.get("state") in {"cancelled", "expired"}
            or (request.get("expires_at") is not None
                and request["expires_at"] <= time.time())):
        raise ValueError("첨부 접수 요청의 저장 권한이 없거나 만료되었습니다")
    item = request["items"].get(item_id)
    if item is None or item.get("state") == "deleted":
        raise ValueError("삭제되었거나 없는 첨부 접수 항목은 다시 가져올 수 없습니다")
    intent = next((item for item in request["spec"]["items"]
                   if item["item_id"] == item_id), None)
    if intent is None or "attachment" not in intent:
        raise ValueError("첨부 저장이 허용된 정확한 접수 항목이 필요합니다")


def _record_import_intake(config: Config, request_id: str | None,
                          item_id: str | None, document_key: str, sha256: str,
                          *, state: LibraryState) -> None:
    # The caller holds storage through both this durable receipt and publishing
    # the copy. A concurrent deletion therefore either rejects this intake or
    # runs after publication; it cannot fall between validation and publication.
    _validate_intake_authority(config, request_id, item_id)
    if request_id is not None:
        state.record_intake_receipt({"request_id": request_id, "item_id": item_id, "document_key": document_key, "sha256": sha256, "stage": "stored"})
    state.clear_document_exclusions(document_key=document_key)
    state.commit()


def import_pdf_path(config: Config, path: Path, *, request_id: str | None = None,
                    item_id: str | None = None) -> dict[str, object]:
    requested = path.expanduser()
    name = _filename(requested.name)
    if requested.is_symlink():
        raise ValueError("심볼릭 링크 PDF는 가져오지 않습니다")
    # O_NONBLOCK prevents a disguised FIFO from hanging before fstat validation.
    fd = os.open(requested, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("첨부 PDF는 일반 파일이어야 합니다")
        if info.st_size > MAX_PDF_BYTES:
            raise ValueError("첨부 PDF는 256 MiB 이하여야 합니다")
        return import_pdf(config, stream, name=name,
                          origin_path=str(requested.resolve()),
                          request_id=request_id, item_id=item_id)
