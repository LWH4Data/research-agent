from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import time
from typing import Iterator

from .safety import (
    PROJECT_MARKER,
    ensure_owned_directory,
    reject_linked_file,
    require_project_root,
)


@contextmanager
def conversation_lock(root: Path, *, timeout: float = 30.0) -> Iterator[None]:
    """Serialize conversation reads, mutations, and crash recovery.

    The project marker already exists and is never replaced, so locking its file
    descriptor does not create or modify a file during a read-only operation.
    The operating system releases the advisory lock if the process exits.
    """

    project = require_project_root(root)
    marker = project / PROJECT_MARKER
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(marker, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("대화 작업 잠금 파일이 안전한 일반 파일이 아닙니다")

        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "다른 대화 저장 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


@contextmanager
def sync_lock(root: Path, *, timeout: float = 1.0) -> Iterator[None]:
    """Allow one long-running sync without blocking short project writes."""

    project = require_project_root(root)
    lock_directory = ensure_owned_directory(
        project / ".research-store",
        project,
        label="동기화 잠금 폴더",
    )
    lock_path = reject_linked_file(
        lock_directory / "sync.lock",
        project,
        label="동기화 잠금 파일",
    )
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("동기화 잠금 파일이 안전한 일반 파일이 아닙니다")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "문서 정리가 이미 진행 중입니다. 현재 작업이 끝난 뒤 다시 시도해 주세요"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
