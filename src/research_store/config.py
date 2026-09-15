from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class Source:
    id: str
    path: Path


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
    return path.resolve()


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or path.is_relative_to(parent)


def load_config(path: Path) -> Config:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"설정 파일을 찾을 수 없습니다: {path}")

    with path.open("rb") as file:
        raw = tomllib.load(file)

    base = path.parent
    store = raw.get("store", {})
    required_store = ("documents", "conversations", "state", "temporary")
    missing_store = [key for key in required_store if not store.get(key)]
    if missing_store:
        raise ValueError(f"[store]에 필요한 값이 없습니다: {', '.join(missing_store)}")

    sources_raw = raw.get("sources", [])
    if not sources_raw:
        raise ValueError("최소 하나의 [[sources]] 설정이 필요합니다")

    sources: list[Source] = []
    seen_ids: set[str] = set()
    for item in sources_raw:
        source_id = str(item.get("id", ""))
        source_path = str(item.get("path", ""))
        if not SOURCE_ID.fullmatch(source_id):
            raise ValueError(f"잘못된 source id입니다: {source_id!r}")
        if source_id in seen_ids:
            raise ValueError(f"중복된 source id입니다: {source_id}")
        if not source_path:
            raise ValueError(f"source {source_id!r}에 path가 없습니다")
        seen_ids.add(source_id)
        sources.append(Source(source_id, _resolve(base, source_path)))

    config = Config(
        root=base,
        documents=_resolve(base, store["documents"]),
        conversations=_resolve(base, store["conversations"]),
        assets=_resolve(base, store.get("assets", "knowledge/assets")),
        state=_resolve(base, store["state"]),
        temporary=_resolve(base, store["temporary"]),
        sources=tuple(sources),
    )
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    writable_paths = (
        config.documents,
        config.conversations,
        config.assets,
        config.state,
        config.temporary,
    )
    for source in config.sources:
        if not source.path.is_dir():
            raise ValueError(f"원본 디렉터리를 찾을 수 없습니다: {source.path}")
        for output in writable_paths:
            if _inside(output, source.path):
                raise ValueError(
                    "쓰기 경로가 원본 디렉터리 안에 있습니다: "
                    f"source={source.path}, output={output}"
                )
