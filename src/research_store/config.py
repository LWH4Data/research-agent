from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

from .safety import find_project_root, is_within, require_owned_path


SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class Source:
    id: str
    path: Path
    kind: str
    enabled: bool = True

    @property
    def available(self) -> bool:
        return self.path.exists() and not self.path.is_symlink()

    def relative_path(self, pdf: Path) -> Path:
        if self.kind == "file":
            return Path(self.path.name)
        return pdf.relative_to(self.path)

    def document_path(self, relative: Path) -> Path:
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"안전하지 않은 원본 상대 경로입니다: {relative}")
        if self.kind == "file":
            if relative != Path(self.path.name):
                raise ValueError(f"등록된 PDF 경로와 일치하지 않습니다: {relative}")
            return self.path
        return self.path / relative


@dataclass(frozen=True)
class Config:
    root: Path
    documents: Path
    conversations: Path
    assets: Path
    state: Path
    temporary: Path
    sources: tuple[Source, ...]


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path


def _source_candidate(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    if path.is_symlink():
        raise ValueError(f"심볼릭 링크는 원본 경로로 등록할 수 없습니다: {path}")
    return path


def _load_source(
    source_id: str,
    source_path: Path,
    root: Path,
    declared_kind: str | None,
) -> Source:
    if source_path.is_symlink():
        raise ValueError(f"심볼릭 링크는 원본 경로로 등록할 수 없습니다: {source_path}")
    exists = source_path.exists()
    resolved = source_path.resolve(strict=exists)
    if is_within(resolved, root) or is_within(root, resolved):
        raise ValueError(
            "원본 경로와 research-agent 프로젝트는 서로 포함될 수 없습니다: "
            f"source={resolved}, project={root}"
        )
    if declared_kind is None:
        declared_kind = "file" if resolved.suffix.casefold() == ".pdf" else "directory"
    if declared_kind not in {"directory", "file"}:
        raise ValueError(f"잘못된 source kind입니다: {declared_kind!r}")

    if not exists:
        kind = declared_kind
    elif resolved.is_dir() and declared_kind == "directory":
        kind = declared_kind
    elif (
        resolved.is_file()
        and resolved.suffix.casefold() == ".pdf"
        and declared_kind == "file"
    ):
        kind = declared_kind
    else:
        raise ValueError(
            f"원본 경로 종류가 설정과 다릅니다: {resolved} ({declared_kind})"
        )
    return Source(source_id, resolved, kind)


def load_config(path: Path) -> Config:
    requested = path.expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    root = find_project_root(requested.parent)
    config_path = require_owned_path(requested, root, label="설정 파일")
    if not config_path.is_file():
        raise ValueError(f"설정 파일을 찾을 수 없습니다: {config_path}")
    if config_path.is_symlink():
        raise ValueError(f"설정 파일은 심볼릭 링크일 수 없습니다: {config_path}")

    with config_path.open("rb") as file:
        raw = tomllib.load(file)

    store = raw.get("store", {})
    required_store = ("documents", "conversations", "state", "temporary")
    missing_store = [key for key in required_store if not store.get(key)]
    if missing_store:
        raise ValueError(f"[store]에 필요한 값이 없습니다: {', '.join(missing_store)}")

    documents = require_owned_path(
        _resolve(root, str(store["documents"])), root, label="문서 저장 경로"
    )
    conversations = require_owned_path(
        _resolve(root, str(store["conversations"])), root, label="대화 저장 경로"
    )
    assets = require_owned_path(
        _resolve(root, str(store.get("assets", "knowledge/assets"))),
        root,
        label="에셋 저장 경로",
    )
    state = require_owned_path(
        _resolve(root, str(store["state"])), root, label="SQLite 저장 경로"
    )
    temporary = require_owned_path(
        _resolve(root, str(store["temporary"])), root, label="임시 저장 경로"
    )

    sources: list[Source] = []
    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    for item in raw.get("sources", []):
        source_id = str(item.get("id", ""))
        source_value = str(item.get("path", ""))
        if not SOURCE_ID.fullmatch(source_id):
            raise ValueError(f"잘못된 source id입니다: {source_id!r}")
        if source_id in seen_ids:
            raise ValueError(f"중복된 source id입니다: {source_id}")
        if not source_value:
            raise ValueError(f"source {source_id!r}에 path가 없습니다")
        raw_kind = item.get("kind")
        raw_enabled = item.get("enabled", True)
        if not isinstance(raw_enabled, bool):
            raise ValueError(f"source {source_id!r}의 enabled는 true/false여야 합니다")
        loaded = _load_source(
            source_id,
            _source_candidate(root, source_value),
            root,
            None if raw_kind is None else str(raw_kind),
        )
        source = Source(loaded.id, loaded.path, loaded.kind, raw_enabled)
        if source.path in seen_paths:
            raise ValueError(f"중복된 원본 경로입니다: {source.path}")
        for existing in sources:
            if not source.enabled or not existing.enabled:
                continue
            overlaps = (
                source.kind == "directory" and is_within(existing.path, source.path)
            ) or (
                existing.kind == "directory" and is_within(source.path, existing.path)
            )
            if overlaps:
                raise ValueError(
                    "서로 겹치는 원본 경로는 등록할 수 없습니다: "
                    f"{existing.path}, {source.path}"
                )
        seen_ids.add(source_id)
        seen_paths.add(source.path)
        sources.append(source)

    return Config(
        root=root,
        documents=documents,
        conversations=conversations,
        assets=assets,
        state=state,
        temporary=temporary,
        sources=tuple(sources),
    )
