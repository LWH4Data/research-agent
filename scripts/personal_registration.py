#!/usr/bin/env python3
"""Install and remove the personal Codex registrations owned by this project."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import tempfile
import tomllib


PROJECT_MARKER = "research-agent-owned-root-v1"
REGISTRATION_HEADER = "# research-agent-registration-v1"
ROOT_HEADER = "# research-agent-root: "
SKILL_SOURCE = Path("resources/skills/research-library")
SKILL_TARGET = Path(".agents/skills/research-library")
RULE_TARGET = Path(".codex/rules/research-library.rules")
SANDBOX_CONFIG_TARGET = Path(".codex/research-library-sandbox/config.toml")
SANDBOX_OWNER_TARGET = Path(
    ".codex/research-library-sandbox/.research-agent-owner"
)
AGENT_SOURCES = {
    "research-library-manager.toml": Path(
        "resources/agents/research-library-manager.toml"
    ),
    "research-paper-converter.toml": Path(
        "resources/agents/research-paper-converter.toml"
    ),
}


class RegistrationError(RuntimeError):
    pass


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _require_regular_file(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise RegistrationError(f"{label} 파일이 없습니다: {path}") from error
    if not stat.S_ISREG(info.st_mode):
        raise RegistrationError(f"{label} 파일이 일반 파일이 아닙니다: {path}")
    if info.st_nlink != 1:
        raise RegistrationError(f"{label} 파일이 하드 링크입니다: {path}")


def _reject_linked_components(root: Path, relative: Path, label: str) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError as error:
            raise RegistrationError(f"{label} 경로가 없습니다: {current}") from error
        if stat.S_ISLNK(info.st_mode):
            raise RegistrationError(f"{label} 경로가 링크를 통과합니다: {current}")
    return current


def _canonical_project_root(value: Path) -> Path:
    try:
        root = value.expanduser().resolve(strict=True)
    except FileNotFoundError as error:
        raise RegistrationError(f"research-agent 경로가 없습니다: {value}") from error
    if not root.is_dir():
        raise RegistrationError(f"research-agent 경로가 폴더가 아닙니다: {root}")
    marker = root / ".research-agent-root"
    _require_regular_file(marker, "프로젝트 표시")
    if marker.read_text(encoding="utf-8").strip() != PROJECT_MARKER:
        raise RegistrationError("research-agent 프로젝트 루트를 확인할 수 없습니다")
    skill_source = _reject_linked_components(root, SKILL_SOURCE, "개인 스킬 리소스")
    try:
        skill_info = skill_source.lstat()
    except FileNotFoundError as error:
        raise RegistrationError(f"개인 스킬 리소스가 없습니다: {skill_source}") from error
    if not stat.S_ISDIR(skill_info.st_mode) or stat.S_ISLNK(skill_info.st_mode):
        raise RegistrationError(f"개인 스킬 리소스가 안전한 폴더가 아닙니다: {skill_source}")
    for item in skill_source.rglob("*"):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise RegistrationError(f"개인 스킬 리소스 안에 링크가 있습니다: {item}")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise RegistrationError(f"개인 스킬 리소스가 하드 링크입니다: {item}")
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise RegistrationError(f"개인 스킬 리소스 형식이 안전하지 않습니다: {item}")
    for relative in AGENT_SOURCES.values():
        _require_regular_file(
            _reject_linked_components(root, relative, "배포 리소스"), "배포 리소스"
        )
    return root


def _canonical_home(value: Path) -> Path:
    expanded = value.expanduser().absolute()
    try:
        info = expanded.lstat()
    except FileNotFoundError as error:
        raise RegistrationError(f"사용자 홈 폴더가 없습니다: {expanded}") from error
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise RegistrationError(f"사용자 홈 경로가 안전한 폴더가 아닙니다: {expanded}")
    resolved = expanded.resolve(strict=True)
    return resolved


def _validate_parent_chain(home: Path, relative: Path, *, create: bool) -> Path:
    current = home
    for part in relative.parts:
        current = current / part
        if _lexists(current):
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise RegistrationError(f"등록 경로가 안전한 폴더가 아닙니다: {current}")
        elif create:
            current.mkdir(mode=0o700)
        else:
            break
    return home / relative


@contextmanager
def _registration_lock(home: Path) -> Iterator[None]:
    codex_dir = _validate_parent_chain(home, Path(".codex"), create=True)
    descriptor = os.open(codex_dir, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _owned_registration_file(path: Path, root: Path, label: str) -> bool:
    if not _lexists(path):
        return False
    _require_regular_file(path, label)
    lines = path.read_text(encoding="utf-8").splitlines()
    expected = [REGISTRATION_HEADER, ROOT_HEADER + str(root)]
    if lines[:2] != expected:
        raise RegistrationError(
            f"기존 {label}은 이 프로젝트 소유가 아니므로 덮어쓰지 않습니다: {path}"
        )
    return True


def _owned_skill_link(path: Path, source: Path) -> bool:
    if not _lexists(path):
        return False
    info = path.lstat()
    if not stat.S_ISLNK(info.st_mode):
        raise RegistrationError(
            f"기존 개인 스킬은 이 프로젝트 소유 링크가 아니므로 덮어쓰지 않습니다: {path}"
        )
    raw_target = Path(os.readlink(path))
    target = raw_target if raw_target.is_absolute() else path.parent / raw_target
    if target.resolve(strict=False) != source:
        raise RegistrationError(
            f"기존 개인 스킬 링크가 다른 위치를 가리킵니다: {path}"
        )
    return True


def _preflight_owned_directory_tree(path: Path, label: str) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise RegistrationError(f"{label} 경로가 안전한 폴더가 아닙니다: {path}")
    for item in path.rglob("*"):
        item_info = item.lstat()
        if stat.S_ISLNK(item_info.st_mode):
            continue
        if stat.S_ISREG(item_info.st_mode):
            if item_info.st_nlink != 1:
                raise RegistrationError(f"{label} 안에 하드 링크가 있습니다: {item}")
        elif not stat.S_ISDIR(item_info.st_mode):
            raise RegistrationError(f"{label} 안에 안전하지 않은 항목이 있습니다: {item}")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_agent(template: Path, root: Path, skill_link: Path) -> str:
    _require_regular_file(template, "에이전트 템플릿")
    data = tomllib.loads(template.read_text(encoding="utf-8"))
    launcher = skill_link / "scripts/research-store"
    launcher_command = shlex.quote(str(launcher))
    add_source_command = "bash " + shlex.quote(str(root / "add-source.sh"))
    instructions = str(data["developer_instructions"])
    instructions = instructions.replace("./research-store", launcher_command)
    instructions = instructions.replace("bash ./add-source.sh", add_source_command)
    instructions = instructions.replace(
        "Read AGENTS.md before acting.",
        f"Read {root / 'AGENTS.md'} before acting.",
    )
    prefix = (
        f"The research-agent store root is {root}. Use only the personal launcher "
        f"at {launcher} for library operations, regardless of the current working "
        f"directory. Read {root / 'AGENTS.md'} and {skill_link / 'SKILL.md'} before "
        "acting. This agent is read-only. Never write to the current project or any "
        "configured source; invoke the launcher directly for every permitted store "
        "change. A narrow Codex rule permits only that launcher, which immediately "
        "re-enters an isolated permission profile that can write only inside the "
        "research-agent store.\n\n"
    )
    instructions = prefix + instructions

    lines = [
        REGISTRATION_HEADER,
        ROOT_HEADER + str(root),
        f"name = {_toml_string(str(data['name']))}",
        f"description = {_toml_string(str(data['description']))}",
        f"model = {_toml_string(str(data['model']))}",
        f"model_reasoning_effort = {_toml_string(str(data['model_reasoning_effort']))}",
        'sandbox_mode = "read-only"',
        'approval_policy = "never"',
        "allow_login_shell = false",
        f"developer_instructions = {_toml_string(instructions)}",
        "",
    ]
    return "\n".join(lines)


def _render_rule(skill_link: Path, root: Path) -> str:
    root_launcher = skill_link / "scripts/research-root"
    store_launcher = skill_link / "scripts/research-store"
    return "\n".join(
        [
            REGISTRATION_HEADER,
            ROOT_HEADER + str(root),
            "# Only these project-owned launchers may run outside the sandbox.",
            "prefix_rule(",
            f"    pattern = [{_toml_string(str(root_launcher))}],",
            '    decision = "allow",',
            '    justification = "Locate the read-only Research Library store",',
            ")",
            "",
            "prefix_rule(",
            f"    pattern = [{_toml_string(str(store_launcher))}],",
            '    decision = "allow",',
            '    justification = "Use the constrained Research Library CLI",',
            ")",
            "",
        ]
    )


def _render_sandbox_config(root: Path) -> str:
    return "\n".join(
        [
            REGISTRATION_HEADER,
            ROOT_HEADER + str(root),
            "# Isolated config used only by the Research Library command launcher.",
            "[permissions.research-store]",
            'description = "Read files and write only Research Library data."',
            "",
            "[permissions.research-store.filesystem]",
            '":root" = "read"',
            '":minimal" = "read"',
            '":tmpdir" = "deny"',
            '":slash_tmp" = "deny"',
            f"{_toml_string(str(root / '.research-store'))} = \"write\"",
            f"{_toml_string(str(root / 'knowledge'))} = \"write\"",
            "",
            "[permissions.research-store.network]",
            "enabled = false",
            "",
        ]
    )


def _render_owner_marker(root: Path) -> str:
    return "\n".join(
        [
            REGISTRATION_HEADER,
            ROOT_HEADER + str(root),
            "# This whole directory is owned by research-agent.",
            "",
        ]
    )


def _atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if _lexists(temporary):
            temporary.unlink()


def _atomic_skill_link(path: Path, source: Path) -> None:
    try:
        path.symlink_to(source, target_is_directory=True)
    except FileExistsError as error:
        raise RegistrationError(f"개인 스킬 등록 경로가 이미 존재합니다: {path}") from error


def install(root_value: Path, home_value: Path) -> None:
    root = _canonical_project_root(root_value)
    home = _canonical_home(home_value)
    skill_source = (root / SKILL_SOURCE).resolve(strict=True)
    skill_target = home / SKILL_TARGET
    agents_parent = home / ".codex/agents"
    rule_target = home / RULE_TARGET
    sandbox_config_target = home / SANDBOX_CONFIG_TARGET
    sandbox_owner_target = home / SANDBOX_OWNER_TARGET
    sandbox_directory = sandbox_config_target.parent
    agent_targets = {
        filename: agents_parent / filename for filename in AGENT_SOURCES
    }

    _validate_parent_chain(home, SKILL_TARGET.parent, create=False)
    _validate_parent_chain(home, Path(".codex/agents"), create=False)
    _validate_parent_chain(home, RULE_TARGET.parent, create=False)
    _validate_parent_chain(home, SANDBOX_CONFIG_TARGET.parent, create=False)
    sandbox_directory_existed = _lexists(sandbox_directory)
    sandbox_owner_existed = _owned_registration_file(
        sandbox_owner_target, root, "저장 명령 샌드박스 소유권 표시"
    )
    if sandbox_directory_existed and not sandbox_owner_existed:
        raise RegistrationError(
            "기존 저장 명령 샌드박스 폴더는 이 프로젝트 소유가 아니므로 "
            f"사용하지 않습니다: {sandbox_directory}"
        )
    skill_existed = _owned_skill_link(skill_target, skill_source)
    agent_existed = {
        filename: _owned_registration_file(path, root, "개인 에이전트 등록")
        for filename, path in agent_targets.items()
    }
    rule_existed = _owned_registration_file(rule_target, root, "명령 허용 규칙")
    sandbox_config_existed = _owned_registration_file(
        sandbox_config_target, root, "저장 명령 샌드박스 설정"
    )

    skill_parent = _validate_parent_chain(home, SKILL_TARGET.parent, create=True)
    _validate_parent_chain(home, Path(".codex/agents"), create=True)
    _validate_parent_chain(home, RULE_TARGET.parent, create=True)
    _validate_parent_chain(home, SANDBOX_CONFIG_TARGET.parent, create=True)
    skill_link = skill_parent / "research-library"
    rendered_agents = {
        filename: _render_agent(root / source, root, skill_link)
        for filename, source in AGENT_SOURCES.items()
    }
    rendered_files = {
        **{agent_targets[name]: content for name, content in rendered_agents.items()},
        rule_target: _render_rule(skill_link, root),
        sandbox_config_target: _render_sandbox_config(root),
        sandbox_owner_target: _render_owner_marker(root),
    }
    existed = {
        **{agent_targets[name]: value for name, value in agent_existed.items()},
        rule_target: rule_existed,
        sandbox_config_target: sandbox_config_existed,
        sandbox_owner_target: sandbox_owner_existed,
    }
    previous = {
        path: path.read_text(encoding="utf-8") if existed[path] else None
        for path in rendered_files
    }

    written: list[Path] = []
    try:
        for path, content in rendered_files.items():
            _atomic_write(path, content)
            written.append(path)
        if not skill_existed:
            _atomic_skill_link(skill_target, skill_source)
    except Exception:
        for path in reversed(written):
            old = previous[path]
            if old is None:
                if _lexists(path):
                    path.unlink()
            else:
                _atomic_write(path, old)
        if not skill_existed and _lexists(skill_target):
            if skill_target.is_symlink():
                skill_target.unlink()
        if not sandbox_directory_existed and sandbox_directory.exists():
            try:
                sandbox_directory.rmdir()
            except OSError:
                pass
        raise

    print(f"개인 스킬 등록: {skill_target}")
    for path in agent_targets.values():
        print(f"개인 에이전트 등록: {path}")
    print(f"제한 명령 규칙 등록: {rule_target}")
    print(f"저장 명령 샌드박스 등록: {sandbox_config_target}")


def uninstall(root_value: Path, home_value: Path) -> None:
    root = _canonical_project_root(root_value)
    home = _canonical_home(home_value)
    skill_source = (root / SKILL_SOURCE).resolve(strict=True)
    skill_target = home / SKILL_TARGET
    agents_parent = home / ".codex/agents"
    agent_targets = [agents_parent / filename for filename in AGENT_SOURCES]
    rule_target = home / RULE_TARGET
    sandbox_config_target = home / SANDBOX_CONFIG_TARGET
    sandbox_owner_target = home / SANDBOX_OWNER_TARGET
    sandbox_directory = sandbox_config_target.parent

    _validate_parent_chain(home, SKILL_TARGET.parent, create=False)
    _validate_parent_chain(home, Path(".codex/agents"), create=False)
    _validate_parent_chain(home, RULE_TARGET.parent, create=False)
    _validate_parent_chain(home, SANDBOX_CONFIG_TARGET.parent, create=False)
    skill_owned = _owned_skill_link(skill_target, skill_source)
    owned_agents = [
        (path, _owned_registration_file(path, root, "개인 에이전트 등록"))
        for path in agent_targets
    ]
    rule_owned = _owned_registration_file(rule_target, root, "명령 허용 규칙")
    sandbox_config_owned = _owned_registration_file(
        sandbox_config_target, root, "저장 명령 샌드박스 설정"
    )
    sandbox_directory_exists = _lexists(sandbox_directory)
    sandbox_owner_owned = _owned_registration_file(
        sandbox_owner_target, root, "저장 명령 샌드박스 소유권 표시"
    )
    if sandbox_directory_exists and not sandbox_owner_owned:
        raise RegistrationError(
            "기존 저장 명령 샌드박스 폴더는 이 프로젝트 소유가 아니므로 "
            f"삭제하지 않습니다: {sandbox_directory}"
        )
    if sandbox_owner_owned:
        _preflight_owned_directory_tree(
            sandbox_directory, "저장 명령 샌드박스"
        )

    for path, owned in owned_agents:
        if owned:
            path.unlink()
            print(f"개인 에이전트 등록 제거: {path}")
    if skill_owned:
        skill_target.unlink()
        print(f"개인 스킬 등록 제거: {skill_target}")
    if rule_owned:
        rule_target.unlink()
        print(f"제한 명령 규칙 제거: {rule_target}")
    if sandbox_owner_owned:
        shutil.rmtree(sandbox_directory)
        print(f"저장 명령 샌드박스 제거: {sandbox_directory}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        home = _canonical_home(args.home)
        with _registration_lock(home):
            if args.action == "install":
                install(args.root, home)
            else:
                uninstall(args.root, home)
    except RegistrationError as error:
        raise SystemExit(f"오류: {error}") from error


if __name__ == "__main__":
    main()
