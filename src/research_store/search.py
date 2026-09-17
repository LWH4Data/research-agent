from __future__ import annotations

import os
from pathlib import Path

from .config import Config
from .safety import reject_linked_file, require_owned_path


def _excerpt(line: str, positions: list[int], width: int = 500) -> str:
    text = line.strip()
    if len(text) <= width:
        return text
    position = min(positions)
    start = max(0, position - width // 3)
    end = min(len(text), start + width)
    start = max(0, end - width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


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


def search_library(
    config: Config, queries: list[str], *, limit: int = 50
) -> dict[str, object]:
    if limit < 1 or limit > 200:
        raise ValueError("검색 결과 개수는 1에서 200 사이여야 합니다")

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

    buckets: list[list[tuple[str, int]]] = [[] for _ in prepared]
    records: dict[tuple[str, int], dict[str, object]] = {}
    total_matches = 0
    roots = (
        ("pdf-document", config.documents),
        ("conversation", config.conversations),
    )
    for record_type, root in roots:
        for path in _markdown_files(root, config):
            with path.open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    display_line = line.strip()
                    folded = display_line.casefold()
                    hit_indices = [
                        index
                        for index, (_, normalized) in enumerate(prepared)
                        if normalized in folded
                    ]
                    if not hit_indices:
                        continue
                    total_matches += 1
                    if not any(len(buckets[index]) < limit for index in hit_indices):
                        continue
                    relative_path = path.relative_to(config.root).as_posix()
                    key = (relative_path, line_number)
                    positions = [
                        folded.find(prepared[index][1]) for index in hit_indices
                    ]
                    records[key] = {
                        "type": record_type,
                        "path": relative_path,
                        "line": line_number,
                        "matched_queries": [
                            prepared[index][0] for index in hit_indices
                        ],
                        "text": _excerpt(display_line, positions),
                    }
                    for index in hit_indices:
                        if len(buckets[index]) < limit:
                            buckets[index].append(key)

    selected: list[dict[str, object]] = []
    selected_keys: set[tuple[str, int]] = set()
    for position in range(limit):
        for bucket in buckets:
            if position >= len(bucket):
                continue
            key = bucket[position]
            if key in selected_keys:
                continue
            selected_keys.add(key)
            selected.append(records[key])
            if len(selected) >= limit:
                return {
                    "queries": [query for query, _ in prepared],
                    "matches": selected,
                    "truncated": total_matches > len(selected),
                }
    return {
        "queries": [query for query, _ in prepared],
        "matches": selected,
        "truncated": total_matches > len(selected),
    }
