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
    for query in queries:
        value = query.strip()
        if not value:
            continue
        if len(value) > 500:
            raise ValueError("검색어는 500자 이하여야 합니다")
        prepared.append((value, value.casefold()))
    if not prepared:
        raise ValueError("하나 이상의 검색어가 필요합니다")

    matches: list[dict[str, object]] = []
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
                    hits = [
                        (original, folded.find(normalized))
                        for original, normalized in prepared
                        if normalized in folded
                    ]
                    if not hits:
                        continue
                    matches.append(
                        {
                            "type": record_type,
                            "path": path.relative_to(config.root).as_posix(),
                            "line": line_number,
                            "matched_queries": [query for query, _ in hits],
                            "text": _excerpt(
                                display_line, [position for _, position in hits]
                            ),
                        }
                    )
                    if len(matches) >= limit:
                        return {
                            "queries": [query for query, _ in prepared],
                            "matches": matches,
                            "truncated": True,
                        }
    return {
        "queries": [query for query, _ in prepared],
        "matches": matches,
        "truncated": False,
    }
