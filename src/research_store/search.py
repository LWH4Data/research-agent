from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

from .config import Config
from .conversations import recover_conversations
from .locking import conversation_lock
from .operations import recover_document_operation
from .safety import reject_linked_file, require_owned_path
from .search_results import CandidateBuffer, SearchHit, diversify_results, extract_passages


SEARCH_VERSION = "passages-v1"
MAX_SEARCH_WINDOW = 10_000


def _markdown_files(root: Path, config: Config) -> list[Path]:
    owned = require_owned_path(root, config.root, label="검색 폴더")
    if not owned.exists():
        return []
    if owned.is_symlink() or not owned.is_dir():
        raise ValueError(f"검색 경로가 안전한 폴더가 아닙니다: {owned}")

    files: list[Path] = []
    for current, directory_names, file_names in os.walk(
        owned, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if not (current_path / name).is_symlink()
        )
        for name in sorted(file_names):
            candidate = current_path / name
            if candidate.suffix.casefold() != ".md" or candidate.is_symlink():
                continue
            files.append(
                reject_linked_file(
                    candidate, config.root, label="검색할 Markdown"
                )
            )
    return files




def _file_signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _scan_document(
    path: Path, config: Config, record_type: str,
    prepared: list[tuple[str, str]], capacity: int,
) -> tuple[list[SearchHit], str, tuple[int, ...]]:
    buffer = CandidateBuffer(capacity)
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("검색 파일이 안전한 일반 파일이 아닙니다")

        def lines():
            for raw in stream:
                digest.update(raw)
                yield raw.decode("utf-8")

        for hit in extract_passages(
            lines(), record_type, path.relative_to(config.root).as_posix(), prepared
        ):
            buffer.add(hit)
        after = os.fstat(stream.fileno())
        reject_linked_file(path, config.root, label="검색할 Markdown")
        current = path.stat()
        if _file_signature(before) != _file_signature(after) or _file_signature(after) != _file_signature(current):
            raise ValueError("검색 중 자료가 변경되었습니다. 처음부터 다시 검색하세요")
    return buffer.ranked(), digest.hexdigest(), _file_signature(current)


def search_library(
    config: Config, queries: list[str], *, limit: int = 50,
    scope: str = "all", offset: int = 0, snapshot: str | None = None,
) -> dict[str, object]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("검색 결과 개수는 1에서 200 사이여야 합니다")
    if scope not in {"all", "pdf", "conversation"}:
        raise ValueError("검색 범위는 all, pdf, conversation 중 하나여야 합니다")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("검색 시작 위치는 0 이상의 정수여야 합니다")
    if offset + limit > MAX_SEARCH_WINDOW:
        raise ValueError("한 검색에서 10000개까지 조회할 수 있습니다. 검색어 또는 범위를 좁히세요")
    if offset and not snapshot:
        raise ValueError("추가 조회에는 이전 검색의 snapshot이 필요합니다")
    if snapshot is not None and (
        not isinstance(snapshot, str) or len(snapshot) != 64
        or any(character not in "0123456789abcdef" for character in snapshot)
    ):
        raise ValueError("올바르지 않은 검색 snapshot입니다")

    prepared: list[tuple[str, str]] = []
    seen_queries: set[str] = set()
    for query in queries:
        value = query.strip()
        if not value:
            continue
        if len(value) > 500:
            raise ValueError("검색어는 500자 이하여야 합니다")
        normalized = value.casefold()
        if normalized in seen_queries:
            continue
        seen_queries.add(normalized)
        prepared.append((value, normalized))
    if not prepared:
        raise ValueError("하나 이상의 검색어가 필요합니다")
    if len(prepared) > 32:
        raise ValueError("검색어는 한 번에 32개까지 사용할 수 있습니다")

    roots = [
        (record_type, root) for record_type, root in (
            ("pdf-document", config.documents), ("conversation", config.conversations),
        )
        if scope == "all" or record_type == {"pdf": "pdf-document", "conversation": "conversation"}.get(scope)
    ]
    digest = hashlib.sha256(json.dumps(
        [SEARCH_VERSION, scope, [value for value, _ in prepared]], ensure_ascii=False
    ).encode("utf-8"))
    documents: list[list[SearchHit]] = []
    signatures: dict[Path, tuple[int, ...]] = {}
    # PDF commits and conversation mutations share this lock. Recover and read a
    # coherent library version; keep the lock until the content digest is ready.
    with conversation_lock(config.root):
        recover_document_operation(config, lock_held=True)
        recover_conversations(config, lock_held=True)
        inventories = [(record_type, root, _markdown_files(root, config))
                       for record_type, root in roots]
        for record_type, _, paths in inventories:
            for path in paths:
                hits, content_digest, signature = _scan_document(
                    path, config, record_type, prepared, offset + limit + 1
                )
                signatures[path] = signature
                digest.update(json.dumps([
                    record_type, path.relative_to(config.root).as_posix(), content_digest
                ]).encode("utf-8"))
                if hits:
                    documents.append(hits)
        # Also reject external file additions/removals during the scan. The lock
        # serializes our own writers; file checks catch ordinary external edits.
        for _, root, paths in inventories:
            if _markdown_files(root, config) != paths:
                raise ValueError("검색 중 자료 목록이 변경되었습니다. 처음부터 다시 검색하세요")
            for path in paths:
                if _file_signature(path.stat()) != signatures[path]:
                    raise ValueError("검색 중 자료가 변경되었습니다. 처음부터 다시 검색하세요")

    current_snapshot = digest.hexdigest()
    if snapshot is not None and snapshot != current_snapshot:
        raise ValueError("자료 또는 검색 조건이 변경되었습니다. 처음부터 다시 검색하세요")

    ranked = diversify_results(documents, offset + limit + 1)
    selected = ranked[offset:offset + limit]
    has_more = len(ranked) > offset + limit
    next_offset = offset + len(selected) if has_more else None
    window_exhausted = bool(has_more and next_offset >= MAX_SEARCH_WINDOW)
    return {
        "queries": [value for value, _ in prepared],
        "scope": scope,
        "matches": [hit.as_dict() for hit in selected],
        "truncated": has_more,
        "has_more": has_more,
        "offset": offset,
        "next_offset": None if window_exhausted else next_offset,
        "snapshot": current_snapshot,
        "window_exhausted": window_exhausted,
        "matching_documents": len(documents),
    }
