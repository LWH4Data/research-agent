#!/usr/bin/env python3
"""Remove one owned installation, retaining its files and registrations in Trash."""

from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import tomllib
from typing import Iterator

# -I intentionally excludes the script directory from sys.path.
_spec = importlib.util.spec_from_file_location(
    "research_personal_registration", Path(__file__).with_name("personal_registration.py")
)
assert _spec is not None and _spec.loader is not None
registration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(registration)
RegistrationError = registration.RegistrationError

STAGING = ".research-agent-uninstall"
TARGETS = {
    "manager": Path(".codex/agents/research-library-manager.toml"),
    "converter": Path(".codex/agents/research-paper-converter.toml"),
    "skill": registration.SKILL_TARGET,
    "rule": registration.RULE_TARGET,
    "sandbox": registration.SANDBOX_CONFIG_TARGET.parent,
}


def _overlaps(left: Path, right: Path) -> bool:
    return left.is_relative_to(right) or right.is_relative_to(left)


def _sources(root: Path, home: Path) -> list[Path]:
    """Check current and legacy configs, including disabled original locations."""
    result = []
    for relative in (Path(".research-store/config.toml"), Path("config.toml")):
        registration._validate_parent_chain(root, relative.parent, create=False)
        path = root / relative
        if not registration._lexists(path):
            continue
        registration._require_regular_file(path, "자료원 설정")
        with path.open("rb") as handle:
            config = tomllib.load(handle)
        rows = config.get("sources", [])
        if not isinstance(rows, list):
            raise RegistrationError(f"자료원 설정 형식이 올바르지 않습니다: {path}")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not row["path"]:
                raise RegistrationError(f"자료원 경로를 확인할 수 없습니다: {path}")
            raw = row["path"]
            if raw == "~" or raw.startswith("~/"):
                # The launcher isolates HOME. Check both interpretations of hand-written ~.
                candidates = [home / raw[2:], root / ".research-store/home" / raw[2:]]
            else:
                candidates = [Path(raw).expanduser()]
            for candidate in candidates:
                result.append((candidate if candidate.is_absolute() else root / candidate).resolve())
    return result


def _boundaries(root: Path, home: Path, *, trash: bool) -> Path:
    trash_directory = home / ".Trash"
    if root == home or home.is_relative_to(root) or _overlaps(root, trash_directory):
        raise RegistrationError("홈 폴더나 휴지통을 설치 폴더로 제거할 수 없습니다")
    # A project may be a child of a research directory, but only its own subtree moves.
    changes = [root, *(home / value for value in TARGETS.values())]
    if trash:
        changes.append(trash_directory)
    for original in _sources(root, home):
        if any(_overlaps(original, changed) for changed in changes):
            raise RegistrationError(f"제거 범위와 원본 자료원이 겹칩니다. 아무것도 제거하지 않습니다: {original}")
    for target in TARGETS.values():
        if _overlaps(root, home / target):
            raise RegistrationError("설치 폴더와 개인 등록 경로가 겹칩니다")
    if trash:
        registration._validate_parent_chain(home, Path(".Trash"), create=False)
        parent = trash_directory if trash_directory.exists() else home
        if parent.stat().st_dev != root.stat().st_dev:
            raise RegistrationError("설치 폴더와 휴지통이 다른 볼륨에 있습니다. 자동 제거를 중단합니다")
    return trash_directory


@contextmanager
def _locked(path: Path, *, directory: bool = False) -> Iterator[None]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
            raise RegistrationError(f"작업 잠금 경로가 안전하지 않습니다: {path}")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RegistrationError("Research Agent 작업이 진행 중입니다. 작업을 끝낸 뒤 제거해 주세요") from error
        current = path.lstat()
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise RegistrationError("제거 도중 설치 경로가 변경되었습니다")
        yield
    finally:
        os.close(descriptor)


def _validate_backup(name: str, path: Path, root: Path, home: Path) -> None:
    if name == "skill":
        if not path.is_symlink():
            raise RegistrationError(f"복구할 개인 스킬이 링크가 아닙니다: {path}")
        raw = Path(os.readlink(path))
        # Relocation must not change the meaning of a relative installed link.
        target = raw if raw.is_absolute() else (home / registration.SKILL_TARGET).parent / raw
        if target.resolve() != root / registration.SKILL_SOURCE:
            raise RegistrationError(f"복구할 개인 스킬이 다른 설치를 가리킵니다: {path}")
    elif name == "sandbox":
        registration._preflight_owned_directory_tree(path, "제거 복구 자료")
        if not registration._owned_registration_file(path / ".research-agent-owner", root, "샌드박스 소유권 표시"):
            raise RegistrationError("제거 복구 자료에 소유권 표시가 없습니다")
        registration._owned_registration_file(path / "config.toml", root, "샌드박스 설정")
    else:
        registration._owned_registration_file(path, root, "제거 복구 자료")


def _recover(root: Path, home: Path) -> None:
    """Restore interrupted staging using only fixed, ownership-checked paths."""
    staging = root / STAGING
    if not registration._lexists(staging):
        return
    registration._validate_parent_chain(root, Path(STAGING), create=False)
    entries = {path.name for path in staging.iterdir()}
    if not entries:
        staging.rmdir()
        return
    journal = staging / "journal.json"
    if not registration._lexists(journal) and all(name.startswith(".journal.json.") for name in entries):
        # The journal is published before the first registration move. A process
        # killed during that publication can leave only its temporary file.
        for name in entries:
            registration._require_regular_file(staging / name, "제거 준비 기록")
        for name in entries:
            (staging / name).unlink()
        staging.rmdir()
        return
    registration._require_regular_file(journal, "제거 복구 기록")
    record = json.loads(journal.read_text(encoding="utf-8"))
    names = record.get("targets") if isinstance(record, dict) else None
    if (
        not isinstance(record, dict)
        or record.get("version") != 1 or record.get("root") != str(root)
        or record.get("home") != str(home) or not isinstance(names, list)
        or any(not isinstance(name, str) or name not in TARGETS for name in names)
        or len(set(names)) != len(names)
        or entries - {"journal.json", *names}
    ):
        raise RegistrationError("제거 복구 기록의 소유권이나 경로를 확인할 수 없습니다")
    # Validate every destination and backup before restoring even the first entry.
    for name in names:
        backup, target = staging / name, home / TARGETS[name]
        registration._validate_parent_chain(home, TARGETS[name].parent, create=False)
        if registration._lexists(backup):
            if registration._lexists(target):
                raise RegistrationError(f"복구할 등록 경로가 이미 사용 중입니다: {target}")
            _validate_backup(name, backup, root, home)
        elif registration._lexists(target):
            _validate_backup(name, target, root, home)
        else:
            raise RegistrationError(f"제거 복구 자료가 누락되었습니다: {name}")
    for name in names:
        backup = staging / name
        if registration._lexists(backup):
            os.rename(backup, home / TARGETS[name])
    journal.unlink()
    staging.rmdir()


def _trash(root: Path, home: Path, trash_directory: Path, targets: list[Path]) -> Path:
    # No copy/delete fallback: all moves must be same-volume atomic renames.
    device = root.stat().st_dev
    if any(path.lstat().st_dev != device for path in targets):
        raise RegistrationError("개인 등록과 설치 폴더가 다른 볼륨에 있습니다. 자동 제거를 중단합니다")
    trash_directory.mkdir(mode=0o700, exist_ok=True)
    bundle = Path(tempfile.mkdtemp(prefix="research-agent-removed-", dir=trash_directory))
    destination = bundle / root.name
    staging = root / STAGING
    names = [name for name, relative in TARGETS.items() if home / relative in targets]
    original_inode = root.stat().st_ino
    try:
        staging.mkdir(mode=0o700)
        registration._atomic_write(staging / "journal.json", json.dumps({
            "version": 1, "root": str(root), "home": str(home), "targets": names,
        }) + "\n")
        for name in names:
            os.rename(home / TARGETS[name], staging / name)
        os.rename(root, destination)
    except BaseException:
        # An interrupt just after the final rename has already committed removal.
        committed = not root.exists() and destination.exists() and destination.stat().st_ino == original_inode
        if not committed:
            try:
                _recover(root, home)
            except Exception as recovery_error:
                raise RegistrationError(
                    f"제거를 끝내지 못했습니다. 복구 자료는 {staging}에 보존했습니다. "
                    "같은 제거 명령을 다시 실행해 복구하세요"
                ) from recovery_error
            finally:
                if not any(bundle.iterdir()):
                    bundle.rmdir()
            raise
    return destination


def remove_project(root_value: Path, home_value: Path, *, yes: bool = False, keep_files: bool = False) -> Path | None:
    root = registration._canonical_project_root(root_value)
    if root_value.expanduser().absolute() != root:
        raise RegistrationError("링크나 별칭 대신 실제 설치 폴더의 제거 명령을 실행해 주세요")
    home = registration._canonical_home(home_value)
    with ExitStack() as stack:
        stack.enter_context(_locked(root, directory=True))
        trash_directory = _boundaries(root, home, trash=not keep_files)
        for relative in (Path(".research-store/sync.lock"), Path(".research-agent-root")):
            registration._validate_parent_chain(root, relative.parent, create=False)
            if registration._lexists(root / relative):
                stack.enter_context(_locked(root / relative))
        print(f"제거 대상 설치 폴더: {root}")
        print("Codex 등록만 해제하고 설치 폴더와 자료는 보관합니다." if keep_files else
              "이 폴더 전체(변환 문서·저장 대화·설정 포함)와 전용 Codex 등록을 휴지통으로 옮깁니다.")
        print("등록했던 원본 PDF와 연구 폴더는 이동하거나 삭제하지 않습니다.")
        if not yes:
            try:
                accepted = input("진행할까요? [y/N] ").strip().lower() in {"y", "yes"}
            except EOFError:
                accepted = False
            if not accepted:
                print("제거를 취소했습니다. 변경한 파일은 없습니다.")
                return None
        stack.enter_context(registration._registration_lock(home))
        _recover(root, home)
        targets = registration.owned_uninstall_targets(root, home)
        if keep_files:
            registration.uninstall(root, home)
            print(f"Codex 등록 해제를 마쳤습니다. 설치 폴더와 저장 자료는 남아 있습니다: {root}")
            return None
        destination = _trash(root, home, trash_directory, targets)
        print(f"Research Agent 제거를 마쳤습니다. 휴지통 위치: {destination}")
        return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--keep-files", action="store_true", help="등록만 해제하고 설치 폴더와 자료는 보관")
    parser.add_argument("--yes", action="store_true", help="제거 확인 생략")
    args = parser.parse_args()
    try:
        remove_project(args.root, args.home, yes=args.yes, keep_files=args.keep_files)
    except (RegistrationError, OSError, ValueError) as error:
        raise SystemExit(f"오류: {error}") from error


if __name__ == "__main__":
    main()
