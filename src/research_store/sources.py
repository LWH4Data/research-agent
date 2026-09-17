from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .config import Config, Source, load_config
from .safety import atomic_text, find_project_root, is_within, require_owned_path


DEFAULT_CONFIG = """[store]
documents = "knowledge/documents"
conversations = "knowledge/conversations"
assets = "knowledge/assets"
state = ".research-store/library.sqlite"
temporary = ".research-store/tmp"
"""


def default_config_path(start: Path | None = None) -> Path:
    return find_project_root(start) / ".research-store/config.toml"


def initialize_config(path: Path) -> Path:
    root = find_project_root(path.parent)
    target = require_owned_path(path, root, label="설정 파일")
    if target.exists():
        load_config(target)
        return target
    atomic_text(target, DEFAULT_CONFIG, root)
    return target


def _source_id(path: Path, existing: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem.casefold()).strip("-_")
    if not base or not base[0].isalnum():
        base = "source"
    base = base[:40]
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8]
    candidate = f"{base}-{digest}"
    counter = 2
    while candidate in existing:
        candidate = f"{base}-{digest}-{counter}"
        counter += 1
    return candidate


def _display_store_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        raise ValueError(f"쓰기 경로가 프로젝트 밖에 있습니다: {path}") from None


def _render(config: Config, sources: list[Source]) -> str:
    values = {
        "documents": _display_store_path(config.documents, config.root),
        "conversations": _display_store_path(config.conversations, config.root),
        "assets": _display_store_path(config.assets, config.root),
        "state": _display_store_path(config.state, config.root),
        "temporary": _display_store_path(config.temporary, config.root),
    }
    lines = ["[store]"]
    for key in ("documents", "conversations", "assets", "state", "temporary"):
        lines.append(f"{key} = {json.dumps(values[key], ensure_ascii=False)}")
    for source in sources:
        lines.extend(
            [
                "",
                "[[sources]]",
                f"id = {json.dumps(source.id, ensure_ascii=False)}",
                f"path = {json.dumps(str(source.path), ensure_ascii=False)}",
                f"kind = {json.dumps(source.kind, ensure_ascii=False)}",
                f"enabled = {'true' if source.enabled else 'false'}",
            ]
        )
    return "\n".join(lines) + "\n"


def add_sources(config_path: Path, paths: list[Path]) -> list[Source]:
    initialize_config(config_path)
    config = load_config(config_path)
    sources = list(config.sources)
    existing_ids = {source.id for source in sources}
    added: list[Source] = []

    for raw_path in paths:
        requested = raw_path.expanduser()
        if not requested.exists():
            raise ValueError(f"원본 경로를 찾을 수 없습니다: {requested}")
        if requested.is_symlink():
            raise ValueError(f"심볼릭 링크는 등록할 수 없습니다: {requested}")
        path = requested.resolve(strict=True)
        if not path.is_dir() and not (
            path.is_file() and path.suffix.casefold() == ".pdf"
        ):
            raise ValueError(f"폴더 또는 PDF 파일만 등록할 수 있습니다: {path}")
        if is_within(path, config.root) or is_within(config.root, path):
            raise ValueError(
                "원본 경로와 research-agent 프로젝트는 서로 포함될 수 없습니다: "
                f"source={path}, project={config.root}"
            )
        duplicate = next((source for source in sources if source.path == path), None)
        if duplicate:
            if not duplicate.enabled:
                for source in sources:
                    if not source.enabled or source.path == path:
                        continue
                    overlaps = (
                        duplicate.kind == "directory"
                        and is_within(source.path, duplicate.path)
                    ) or (
                        source.kind == "directory"
                        and is_within(duplicate.path, source.path)
                    )
                    if overlaps:
                        raise ValueError(
                            "다시 활성화할 위치가 현재 등록 위치와 겹칩니다: "
                            f"registered={source.path}, requested={path}"
                        )
                reenabled = Source(
                    duplicate.id, duplicate.path, duplicate.kind, True
                )
                sources[sources.index(duplicate)] = reenabled
                added.append(reenabled)
            continue
        for source in sources:
            if not source.enabled:
                continue
            source_is_directory = source.kind == "directory"
            path_is_directory = path.is_dir()
            overlaps = (
                path_is_directory and is_within(source.path, path)
            ) or (
                source_is_directory and is_within(path, source.path)
            )
            if overlaps:
                raise ValueError(
                    "이미 등록된 위치와 겹칩니다: "
                    f"registered={source.path}, requested={path}"
                )
        source = Source(
            _source_id(path, existing_ids),
            path,
            "directory" if path.is_dir() else "file",
            True,
        )
        existing_ids.add(source.id)
        sources.append(source)
        added.append(source)

    if added:
        atomic_text(config_path, _render(config, sources), config.root)
        load_config(config_path)
    return added


def remove_sources(config_path: Path, source_ids: list[str]) -> list[Source]:
    config = load_config(config_path)
    requested = set(source_ids)
    removed = [source for source in config.sources if source.id in requested]
    unknown = requested - {source.id for source in removed}
    if unknown:
        raise ValueError(f"등록되지 않은 source id입니다: {', '.join(sorted(unknown))}")
    updated = [
        Source(source.id, source.path, source.kind, False)
        if source.id in requested
        else source
        for source in config.sources
    ]
    atomic_text(config_path, _render(config, updated), config.root)
    load_config(config_path)
    return removed


def source_rows(config_path: Path) -> list[dict[str, str | bool]]:
    config = load_config(config_path)
    return [
        {
            "id": source.id,
            "path": str(source.path),
            "kind": source.kind,
            "access": "read-only",
            "available": source.available,
            "enabled": source.enabled,
        }
        for source in config.sources
    ]
