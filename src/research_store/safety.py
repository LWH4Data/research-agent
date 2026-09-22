from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
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


def _entry_exists(directory_descriptor: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _unlink_generated_file(
    directory_descriptor: int,
    name: str,
    *,
    tolerate_completed: bool = False,
) -> None:
    """Unlink a generated file, optionally accepting a completed-then-raised call."""
    try:
        os.unlink(name, dir_fd=directory_descriptor)
    except FileNotFoundError:
        return
    except BaseException:
        if not tolerate_completed or _entry_exists(directory_descriptor, name):
            raise


def _replace_generated_file(
    directory_descriptor: int,
    source_name: str,
    target_name: str,
    *,
    tolerate_completed: bool = False,
) -> None:
    """Replace entries, optionally accepting a completed-then-raised call."""
    try:
        os.replace(
            source_name,
            target_name,
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
    except BaseException:
        if not tolerate_completed:
            raise
        if _entry_exists(directory_descriptor, source_name):
            raise
        if not _entry_exists(directory_descriptor, target_name):
            raise


def _new_generated_file(
    directory_descriptor: int, prefix: str
) -> tuple[str, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    for _ in range(128):
        name = f"{prefix}{secrets.token_hex(12)}"
        try:
            descriptor = os.open(
                name,
                flags,
                0o600,
                dir_fd=directory_descriptor,
            )
        except FileExistsError:
            continue
        return name, descriptor
    raise RuntimeError("안전한 임시 파일 이름을 만들 수 없습니다")


def _restore_from_descriptor(
    directory_descriptor: int,
    source_descriptor: int,
    target_name: str,
) -> None:
    """Recreate a target from an open descriptor after its name was removed."""
    temporary_name, descriptor = _new_generated_file(
        directory_descriptor, ".restore-"
    )
    try:
        os.fchmod(descriptor, stat.S_IMODE(os.fstat(source_descriptor).st_mode))
        os.lseek(source_descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(source_descriptor, 1024 * 1024)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        try:
            _unlink_generated_file(
                directory_descriptor,
                temporary_name,
                tolerate_completed=True,
            )
        except BaseException:
            pass
        raise
    else:
        os.close(descriptor)

    try:
        _replace_generated_file(
            directory_descriptor,
            temporary_name,
            target_name,
            tolerate_completed=True,
        )
    except BaseException:
        try:
            _unlink_generated_file(
                directory_descriptor,
                temporary_name,
                tolerate_completed=True,
            )
        except BaseException:
            pass
        raise
    os.fsync(directory_descriptor)


def _copy_entry_to_generated_file(
    directory_descriptor: int,
    source_name: str,
    prefix: str,
) -> str:
    """Create and fsync a private same-directory copy of a regular file."""
    generated_name, output_descriptor = _new_generated_file(
        directory_descriptor, prefix
    )
    source_descriptor: int | None = None
    try:
        source_descriptor = os.open(
            source_name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        source_info = os.fstat(source_descriptor)
        if not stat.S_ISREG(source_info.st_mode) or source_info.st_nlink != 1:
            raise ValueError(f"백업 대상이 안전한 일반 파일이 아닙니다: {source_name}")
        os.fchmod(output_descriptor, stat.S_IMODE(source_info.st_mode))
        while True:
            chunk = os.read(source_descriptor, 1024 * 1024)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                written = os.write(output_descriptor, view)
                view = view[written:]
        os.fsync(output_descriptor)
    except BaseException:
        try:
            _unlink_generated_file(
                directory_descriptor,
                generated_name,
                tolerate_completed=True,
            )
        except BaseException:
            pass
        raise
    finally:
        if source_descriptor is not None:
            os.close(source_descriptor)
        os.close(output_descriptor)
    return generated_name


def _restore_staged_file(
    directory_descriptor: int,
    staged_name: str,
    target_name: str,
    recovery_descriptor: int | None,
) -> None:
    """Restore staged content by name, or by its still-open descriptor."""
    if _entry_exists(directory_descriptor, staged_name):
        _replace_generated_file(
            directory_descriptor,
            staged_name,
            target_name,
            tolerate_completed=True,
        )
        os.fsync(directory_descriptor)
        return
    if recovery_descriptor is None:
        raise RuntimeError(
            f"복구할 파일을 찾을 수 없습니다: {staged_name}"
        )
    _restore_from_descriptor(
        directory_descriptor, recovery_descriptor, target_name
    )


def atomic_text(path: Path, text: str, root: Path) -> None:
    target = require_owned_path(path, root, label="쓰기 대상")
    parent_descriptor, _ = _open_owned_directory(
        target.parent, root, label="쓰기 폴더", create=True
    )
    temporary_name: str | None = None
    backup_name: str | None = None
    backup_descriptor: int | None = None
    backup_ready = False
    original_existed = False
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
            original_existed = True

        temporary_name, descriptor = _new_generated_file(
            parent_descriptor, ".tmp-"
        )

        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())

        if original_existed:
            backup_name = _copy_entry_to_generated_file(
                parent_descriptor, target.name, ".backup-"
            )
            backup_ready = True
            backup_descriptor = os.open(
                backup_name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_descriptor,
            )
            os.fsync(parent_descriptor)

        _replace_generated_file(
            parent_descriptor, temporary_name, target.name
        )
        temporary_name = None
        os.fsync(parent_descriptor)

        if backup_name is not None:
            _unlink_generated_file(parent_descriptor, backup_name)
            os.fsync(parent_descriptor)
            backup_name = None
            backup_ready = False
    except BaseException:
        recovery_error: BaseException | None = None
        try:
            if backup_ready and backup_name is not None:
                _restore_staged_file(
                    parent_descriptor,
                    backup_name,
                    target.name,
                    backup_descriptor,
                )
                backup_name = None
                backup_ready = False
            elif not original_existed and _entry_exists(
                parent_descriptor, target.name
            ):
                _unlink_generated_file(parent_descriptor, target.name)
                os.fsync(parent_descriptor)
        except BaseException as error:
            recovery_error = error

        if temporary_name is not None:
            try:
                _unlink_generated_file(
                    parent_descriptor,
                    temporary_name,
                    tolerate_completed=True,
                )
            except FileNotFoundError:
                pass
            except BaseException:
                if recovery_error is None:
                    recovery_error = RuntimeError(
                        f"임시 파일을 정리하지 못했습니다: {temporary_name}"
                    )
        if (
            backup_name is not None
            and not backup_ready
            and _entry_exists(parent_descriptor, backup_name)
        ):
            try:
                _unlink_generated_file(
                    parent_descriptor,
                    backup_name,
                    tolerate_completed=True,
                )
            except BaseException:
                if recovery_error is None:
                    recovery_error = RuntimeError(
                        f"백업 준비 파일을 정리하지 못했습니다: {backup_name}"
                    )
        if recovery_error is not None:
            raise RuntimeError(
                "원자적 쓰기 실패 후 이전 내용을 완전히 복구하지 못했습니다: "
                f"{target}; recovery={recovery_error}"
            ) from recovery_error
        raise
    finally:
        if backup_descriptor is not None:
            os.close(backup_descriptor)
        os.close(parent_descriptor)


def unlink_owned_file(
    path: Path,
    root: Path,
    *,
    label: str,
    missing_ok: bool = False,
) -> bool:
    """Durably unlink one project-owned regular file.

    Unlike :func:`staged_owned_file_removal`, this helper deliberately does
    not try to undo a completed unlink. It is used only after the caller has
    durably journaled the delete intent, so an interruption is recovered by
    finishing the same deletion.
    """
    target = require_owned_path(path, root, label=label)
    try:
        parent_descriptor, _ = _open_owned_directory(
            target.parent, root, label=f"{label} 폴더", create=False
        )
    except FileNotFoundError:
        if missing_ok:
            return False
        raise ValueError(f"{label} 파일이 없습니다: {target}") from None
    try:
        try:
            target_info = os.stat(
                target.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if missing_ok:
                return False
            raise ValueError(f"{label} 파일이 없습니다: {target}") from None
        if stat.S_ISLNK(target_info.st_mode):
            raise ValueError(f"{label}는 심볼릭 링크일 수 없습니다: {target}")
        if not stat.S_ISREG(target_info.st_mode):
            raise ValueError(f"{label}는 일반 파일이어야 합니다: {target}")
        if target_info.st_nlink != 1:
            raise ValueError(f"{label}는 하드 링크일 수 없습니다: {target}")

        os.unlink(target.name, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
        return True
    finally:
        os.close(parent_descriptor)


@contextmanager
def staged_owned_file_removal(
    path: Path, root: Path, *, label: str
) -> Iterator[Path]:
    """Hide an owned file, restore it on error, and unlink it after success."""
    target = require_owned_path(path, root, label=label)
    parent_descriptor, _ = _open_owned_directory(
        target.parent, root, label=f"{label} 폴더", create=False
    )
    staged_name: str | None = None
    staged_is_placeholder = False
    recovery_descriptor: int | None = None
    try:
        try:
            target_info = os.stat(
                target.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError as error:
            raise ValueError(f"{label} 파일이 없습니다: {target}") from error
        if stat.S_ISLNK(target_info.st_mode):
            raise ValueError(f"{label}는 심볼릭 링크일 수 없습니다: {target}")
        if not stat.S_ISREG(target_info.st_mode):
            raise ValueError(f"{label}는 일반 파일이어야 합니다: {target}")
        if target_info.st_nlink != 1:
            raise ValueError(f"{label}는 하드 링크일 수 없습니다: {target}")

        staged_name, descriptor = _new_generated_file(
            parent_descriptor, ".delete-"
        )
        os.close(descriptor)
        staged_is_placeholder = True

        try:
            _replace_generated_file(
                parent_descriptor, target.name, staged_name
            )
        except BaseException:
            if (
                not _entry_exists(parent_descriptor, target.name)
                and _entry_exists(parent_descriptor, staged_name)
            ):
                staged_is_placeholder = False
                _restore_staged_file(
                    parent_descriptor,
                    staged_name,
                    target.name,
                    None,
                )
                staged_name = None
            else:
                _unlink_generated_file(
                    parent_descriptor,
                    staged_name,
                    tolerate_completed=True,
                )
                staged_name = None
                staged_is_placeholder = False
            raise
        staged_is_placeholder = False
        try:
            recovery_descriptor = os.open(
                staged_name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_descriptor,
            )
        except BaseException:
            _restore_staged_file(
                parent_descriptor,
                staged_name,
                target.name,
                None,
            )
            staged_name = None
            raise
        try:
            os.fsync(parent_descriptor)
        except BaseException:
            _restore_staged_file(
                parent_descriptor,
                staged_name,
                target.name,
                recovery_descriptor,
            )
            staged_name = None
            raise

        try:
            yield target
        except BaseException:
            _restore_staged_file(
                parent_descriptor,
                staged_name,
                target.name,
                recovery_descriptor,
            )
            staged_name = None
            raise
        else:
            try:
                _unlink_generated_file(parent_descriptor, staged_name)
                os.fsync(parent_descriptor)
            except BaseException:
                _restore_staged_file(
                    parent_descriptor,
                    staged_name,
                    target.name,
                    recovery_descriptor,
                )
                staged_name = None
                raise
            else:
                staged_name = None
    finally:
        if staged_name is not None and staged_is_placeholder:
            try:
                _unlink_generated_file(
                    parent_descriptor,
                    staged_name,
                    tolerate_completed=True,
                )
            except FileNotFoundError:
                pass
        if recovery_descriptor is not None:
            os.close(recovery_descriptor)
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
