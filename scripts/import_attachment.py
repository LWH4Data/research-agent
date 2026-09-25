#!/usr/bin/env python3
"""Read one explicit attachment and send its bytes to the constrained importer.

This trusted launcher helper never writes files or executes a shell. The caller
has already validated the installed Codex binary, store, and permission profile.
Only the existing sandboxed research-store process can persist the PDF.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import subprocess
import sys


MAX_PDF_BYTES = 256 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024


def _absolute(value: str) -> str:
    if not value or "\0" in value or not os.path.isabs(value):
        raise argparse.ArgumentTypeError("절대 경로를 지정해야 합니다")
    return value


def _filename(path: str) -> str:
    name = Path(path).name
    if (not name or "\\" in name or "\0" in name
            or Path(name).suffix.casefold() != ".pdf"
            or len(name.encode("utf-8")) > 255):
        raise ValueError("첨부 파일은 올바른 이름의 PDF여야 합니다")
    return name


def _fingerprint(info: os.stat_result) -> tuple[int, ...]:
    # Access time may legitimately change during a read; never restore it by
    # writing to the original. All fields relevant to a stable snapshot remain.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def read_attachment(path: str) -> tuple[str, bytes]:
    """Read a bounded regular-file snapshot without following a final symlink."""
    if not path or "\0" in path or not os.path.isabs(path):
        raise ValueError("첨부 PDF의 절대 경로가 필요합니다")
    name = _filename(path)
    # O_NONBLOCK ensures that opening a FIFO cannot hang before fstat rejects it.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("첨부 PDF는 일반 파일이어야 합니다")
        if before.st_size > MAX_PDF_BYTES:
            raise ValueError("첨부 PDF는 256 MiB 이하여야 합니다")
        data = bytearray(os.read(fd, 5))
        if data != b"%PDF-":
            raise ValueError("PDF 파일 형식이 아닙니다")
        while True:
            chunk = os.read(fd, min(READ_CHUNK_BYTES, MAX_PDF_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_PDF_BYTES:
                raise ValueError("첨부 PDF는 256 MiB 이하여야 합니다")
        after = os.fstat(fd)
        current = os.stat(path, follow_symlinks=False)
        if (len(data) != before.st_size
                or _fingerprint(before) != _fingerprint(after)
                or _fingerprint(after) != _fingerprint(current)):
            raise ValueError("읽는 동안 첨부 PDF가 변경되었습니다. 다시 시도해 주세요")
        return name, bytes(data)
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--codex", required=True, type=_absolute)
    parser.add_argument("--root", required=True, type=_absolute)
    parser.add_argument("--sandbox-home", required=True, type=_absolute)
    parser.add_argument("--path", required=True, type=_absolute)
    args = parser.parse_args(argv)
    try:
        name, content = read_attachment(args.path)
    except (ValueError, UnicodeError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 2
    except OSError:
        print("오류: 첨부 PDF를 읽을 수 없습니다. 파일 경로와 읽기 권한을 확인해 주세요.",
              file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["CODEX_HOME"] = args.sandbox_home
    command = [args.codex, "sandbox", "-P", "research-store", "-C",
               args.sandbox_home, "--", str(Path(args.root) / "research-store"),
               "import-pdf", "--stdin", "--name", name]
    try:
        result = subprocess.run(command, input=content, env=env, check=False)
    except OSError:
        print("오류: Research Agent 제한 실행기를 시작할 수 없습니다.", file=sys.stderr)
        return 1
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
