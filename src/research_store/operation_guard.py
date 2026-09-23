from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import sys
from typing import Iterator


@contextmanager
def operation_guard(root: Path) -> Iterator[int]:
    """Keep the installation in place for an entire command, without a lock file."""

    project = root.expanduser().resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(project, flags)
    try:
        locked = os.fstat(descriptor)
        if not stat.S_ISDIR(locked.st_mode):
            raise ValueError("research-agent 프로젝트 경로가 폴더가 아닙니다")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Research Library 제거가 진행 중입니다. 작업이 끝난 뒤 다시 실행해 주세요"
            ) from None
        try:
            current = project.stat(follow_symlinks=False)
            if (
                not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (locked.st_dev, locked.st_ino)
                or project.resolve(strict=True) != project
            ):
                raise ValueError("작업을 시작하는 동안 research-agent 폴더가 이동되었습니다")
            yield descriptor
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _runtime_directory(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} 경로가 링크입니다: {path}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"{label} 경로가 폴더가 아닙니다: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if path.resolve(strict=True) != path:
        raise ValueError(f"{label} 경로가 프로젝트 밖을 가리킵니다: {path}")


def launch(root: Path, cli: Path, arguments: list[str]) -> None:
    """Acquire the lifecycle guard before any public-launcher runtime writes."""

    with operation_guard(root) as descriptor:
        runtime = root / ".research-store"
        directories = {
            "TMPDIR": runtime / "tmp",
            "HOME": runtime / "home",
            "XDG_CACHE_HOME": runtime / "xdg-cache",
            "XDG_CONFIG_HOME": runtime / "xdg-config",
            "XDG_DATA_HOME": runtime / "xdg-data",
            "XDG_STATE_HOME": runtime / "xdg-state",
        }
        _runtime_directory(runtime, "런타임")
        for name, path in directories.items():
            _runtime_directory(path, name)

        environment = dict(os.environ)
        for name in (
            "ENV", "BASH_ENV", "CODEX_HOME", "PYTHONPATH", "PYTHONHOME",
            "PYTHONPYCACHEPREFIX", "PYTHONINSPECT", "PYTHONSTARTUP",
            "PYTHON_HISTORY", "SSLKEYLOGFILE", "QLOGDIR",
        ):
            environment.pop(name, None)
        environment.update({name: str(path) for name, path in directories.items()})
        environment.update(
            TMP=str(directories["TMPDIR"]),
            TEMP=str(directories["TMPDIR"]),
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONNOUSERSITE="1",
        )
        # exec keeps the lock alive in the actual command even if its launcher
        # would otherwise be killed. The direct CLI guard may share this lock.
        os.set_inheritable(descriptor, True)
        os.execve(
            cli,
            [str(cli), "--config", str(runtime / "config.toml"), *arguments],
            environment,
        )


if __name__ == "__main__":
    try:
        launch(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
    except (OSError, RuntimeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1) from error
