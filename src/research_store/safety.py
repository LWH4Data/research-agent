from __future__ import annotations

import os
from pathlib import Path
import secrets
import stat


PROJECT_MARKER = ".research-agent-root"
PROJECT_MARKER_CONTENT = "research-agent-owned-root-v1"


def is_within(path: Path, parent: Path) -> bool:
    return path == parent or path.is_relative_to(parent)


def require_project_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    marker = root / PROJECT_MARKER
    if marker.is_symlink() or not marker.is_file():
        raise ValueError(
            f"research-agent 프로젝트 루트를 확인할 수 없습니다: {root}"
        )
    if marker.read_text(encoding="utf-8").strip() != PROJECT_MARKER_CONTENT:
        raise ValueError(f"잘못된 research-agent 루트 표시 파일입니다: {marker}")
    return root


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        marker = candidate / PROJECT_MARKER
        if marker.is_file() and not marker.is_symlink():
            return require_project_root(candidate)
    raise ValueError(
        "research-agent 프로젝트를 찾을 수 없습니다. "
        "research-agent 폴더 안에서 실행해 주세요."
    )


def require_owned_path(
    path: Path,
    root: Path,
    *,
    label: str = "쓰기 경로",
    allow_root: bool = False,
) -> Path:
    owned_root = require_project_root(root)
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded
    candidate = Path(os.path.abspath(expanded))
    resolved = candidate.resolve(strict=False)
    if (
        not is_within(candidate, owned_root)
        or not is_within(resolved, owned_root)
        or (candidate == owned_root and not allow_root)
    ):
        raise ValueError(
            f"{label}는 research-agent 프로젝트 내부여야 합니다: {resolved}"
        )

    relative = candidate.relative_to(owned_root)
    current = owned_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label}에 심볼릭 링크를 사용할 수 없습니다: {current}")
    return candidate


def ensure_owned_directory(path: Path, root: Path, *, label: str = "쓰기 폴더") -> Path:
    descriptor, directory = _open_owned_directory(
        path, root, label=label, create=True
    )
    os.close(descriptor)
    return directory


def _open_owned_directory(
    path: Path,
    root: Path,
    *,
    label: str,
    create: bool,
) -> tuple[int, Path]:
    """Open a project directory component-by-component without following links."""
    owned_root = require_project_root(root)
    directory = require_owned_path(
        path, owned_root, label=label, allow_root=True
    )
    relative = directory.relative_to(owned_root)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(owned_root, flags)
    try:
        for part in relative.parts:
            try:
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o755, dir_fd=descriptor)
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor, directory
    except BaseException:
        os.close(descriptor)
        raise


def reject_linked_file(path: Path, root: Path, *, label: str) -> Path:
    candidate = require_owned_path(path, root, label=label)
    if candidate.is_symlink():
        raise ValueError(f"{label}는 심볼릭 링크일 수 없습니다: {candidate}")
    if candidate.exists():
        info = candidate.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"{label}는 일반 파일이어야 합니다: {candidate}")
        if info.st_nlink != 1:
            raise ValueError(f"{label}는 하드 링크일 수 없습니다: {candidate}")
    return candidate


def atomic_text(path: Path, text: str, root: Path) -> None:
    target = require_owned_path(path, root, label="쓰기 대상")
    parent_descriptor, _ = _open_owned_directory(
        target.parent, root, label="쓰기 폴더", create=True
    )
    temporary_name: str | None = None
    try:
        try:
            target_info = os.stat(
                target.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            target_info = None
        if target_info is not None:
            if stat.S_ISLNK(target_info.st_mode):
                raise ValueError(f"쓰기 대상은 심볼릭 링크일 수 없습니다: {target}")
            if not stat.S_ISREG(target_info.st_mode):
                raise ValueError(f"쓰기 대상은 일반 파일이어야 합니다: {target}")
            if target_info.st_nlink != 1:
                raise ValueError(f"쓰기 대상은 하드 링크일 수 없습니다: {target}")

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        for _ in range(128):
            temporary_name = f".tmp-{secrets.token_hex(12)}"
            try:
                descriptor = os.open(
                    temporary_name,
                    flags,
                    0o600,
                    dir_fd=parent_descriptor,
                )
                break
            except FileExistsError:
                temporary_name = None
        else:
            raise RuntimeError("안전한 임시 파일 이름을 만들 수 없습니다")

        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(
            temporary_name,
            target.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        temporary_name = None
        os.fsync(parent_descriptor)
    except BaseException:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
        raise
    finally:
        os.close(parent_descriptor)


def safe_source_file(path: Path, source: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"심볼릭 링크 PDF는 읽지 않습니다: {path}")
    candidate = path.expanduser().resolve(strict=True)
    boundary = source.expanduser().resolve(strict=True)
    if boundary.is_file():
        if candidate != boundary:
            raise ValueError(f"등록된 PDF 경로를 벗어났습니다: {candidate}")
    elif not is_within(candidate, boundary):
        raise ValueError(f"등록된 원본 폴더를 벗어났습니다: {candidate}")
    if not candidate.is_file() or candidate.suffix.casefold() != ".pdf":
        raise ValueError(f"PDF 파일이 아닙니다: {candidate}")
    return candidate
