from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/personal_registration.py"
SKILL_SOURCE = ROOT / "resources/skills/research-library"
SKILL_RELATIVE = Path(".agents/skills/research-library")
AGENT_NAMES = (
    "research-library-manager.toml",
    "research-paper-converter.toml",
)


def run_registration(
    action: str, home: Path, root: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(SCRIPT),
            action,
            "--root",
            str(root),
            "--home",
            str(home),
        ],
        capture_output=True,
        text=True,
    )


def snapshot(root: Path) -> dict[str, tuple[str | None, int, int]]:
    result: dict[str, tuple[str | None, int, int]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        info = path.lstat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        result[path.relative_to(root).as_posix()] = (
            digest,
            stat.S_IMODE(info.st_mode),
            info.st_nlink,
        )
    return result


class PersonalRegistrationTests(unittest.TestCase):
    def test_install_update_and_uninstall_only_owned_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            source = home / "original-research"
            source.mkdir()
            (source / "paper.pdf").write_bytes(b"untouched")
            other_skill = home / ".agents/skills/other"
            other_skill.mkdir(parents=True)
            (other_skill / "SKILL.md").write_text("other\n", encoding="utf-8")
            other_agent = home / ".codex/agents/other.toml"
            other_agent.parent.mkdir(parents=True)
            other_agent.write_text("name = 'other'\n", encoding="utf-8")
            before = snapshot(source)

            installed = run_registration("install", home)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            skill_link = home / SKILL_RELATIVE
            self.assertTrue(skill_link.is_symlink())
            self.assertEqual(skill_link.resolve(), SKILL_SOURCE.resolve())

            for filename in AGENT_NAMES:
                path = home / ".codex/agents" / filename
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# research-agent-registration-v1\n"))
                parsed = tomllib.loads(text)
                self.assertEqual(parsed["sandbox_mode"], "read-only")
                self.assertNotIn("sandbox_workspace_write", parsed)
                self.assertIn(str(skill_link / "scripts/research-store"), text)
                self.assertIn(
                    str(ROOT / "resources/AGENTS.runtime.md"),
                    parsed["developer_instructions"],
                )
                self.assertNotIn(
                    str(ROOT / "AGENTS.md"), parsed["developer_instructions"],
                )
                self.assertIn(
                    "untrusted research data",
                    parsed["developer_instructions"],
                )
                self.assertIn(
                    "higher-priority instructions",
                    parsed["developer_instructions"],
                )
            manager_text = (
                home / ".codex/agents/research-library-manager.toml"
            ).read_text(encoding="utf-8")
            self.assertIn("conversation-get", manager_text)
            self.assertIn("--confirm-legacy-promotion", manager_text)
            self.assertIn("legacy deletion fallback", manager_text)
            self.assertIn("primary Codex session, not this manager", manager_text)
            self.assertIn("Do not try to\\ncreate a nested agent", manager_text)
            rule = home / ".codex/rules/research-library.rules"
            rule_text = rule.read_text(encoding="utf-8")
            self.assertTrue(rule_text.startswith("# research-agent-registration-v1\n"))
            self.assertIn(str(skill_link / "scripts/research-root"), rule_text)
            self.assertIn(str(skill_link / "scripts/research-store"), rule_text)
            self.assertIn(str(SKILL_SOURCE / "scripts/research-store"), rule_text)
            self.assertIn(str(skill_link / "scripts/research-review"), rule_text)
            self.assertIn(str(SKILL_SOURCE / "scripts/research-review"), rule_text)
            sandbox_config = home / ".codex/research-library-sandbox/config.toml"
            sandbox_owner = (
                home / ".codex/research-library-sandbox/.research-agent-owner"
            )
            sandbox_text = sandbox_config.read_text(encoding="utf-8")
            self.assertTrue(
                sandbox_owner.read_text(encoding="utf-8").startswith(
                    "# research-agent-registration-v1\n"
                )
            )
            sandbox = tomllib.loads(sandbox_text)
            self.assertEqual(sandbox["default_permissions"], "research-store")
            profile = sandbox["permissions"]["research-store"]
            self.assertEqual(profile["filesystem"][":root"], "read")
            self.assertNotIn(str(ROOT), profile["filesystem"])
            self.assertEqual(
                profile["filesystem"][str(ROOT / ".research-store")], "write"
            )
            self.assertEqual(
                profile["filesystem"][str(ROOT / "knowledge")], "write"
            )
            self.assertFalse(profile["network"]["enabled"])
            review_profile = sandbox["permissions"]["research-review-worker"]
            self.assertEqual(review_profile["filesystem"][":root"], "read")
            self.assertEqual(
                review_profile["filesystem"][str(ROOT / ".research-store")],
                "write",
            )
            self.assertEqual(
                review_profile["filesystem"][str(ROOT / "knowledge")],
                "write",
            )
            self.assertTrue(review_profile["network"]["enabled"])
            self.assertNotIn(str(source), review_profile["filesystem"])
            self.assertEqual(
                review_profile["filesystem"][str(home / ".codex/state_5.sqlite")],
                "write",
            )
            self.assertEqual(
                review_profile["filesystem"][str(home / ".codex/tmp/arg0")],
                "write",
            )
            self.assertEqual(
                review_profile["filesystem"][str(home / ".codex/installation_id")],
                "write",
            )
            self.assertNotIn(str(home / ".codex/auth.json"),
                             review_profile["filesystem"])

            manager = home / ".codex/agents/research-library-manager.toml"
            manager.write_text(manager.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            updated = run_registration("install", home)
            self.assertEqual(updated.returncode, 0, updated.stderr)

            removed = run_registration("uninstall", home)
            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertFalse(os.path.lexists(skill_link))
            for filename in AGENT_NAMES:
                self.assertFalse(os.path.lexists(home / ".codex/agents" / filename))
            self.assertFalse(os.path.lexists(rule))
            self.assertFalse(os.path.lexists(sandbox_config))
            self.assertFalse(sandbox_config.parent.exists())
            self.assertEqual((other_skill / "SKILL.md").read_text(), "other\n")
            self.assertEqual(other_agent.read_text(), "name = 'other'\n")
            self.assertEqual(snapshot(source), before)

    def test_missing_or_linked_runtime_rules_are_rejected_before_registration(self) -> None:
        for kind in ("missing", "symlink", "hardlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                fixture = Path(directory).resolve()
                project = fixture / "store"
                project.mkdir()
                home = fixture / "home"
                home.mkdir()
                # Registration locks the existing Codex directory before its
                # source preflight; assert no registration content is written.
                (home / ".codex").mkdir(mode=0o700)
                shutil.copy2(ROOT / ".research-agent-root", project / ".research-agent-root")
                shutil.copytree(ROOT / "resources", project / "resources")
                runtime_rules = project / "resources/AGENTS.runtime.md"
                runtime_rules.unlink()
                external = fixture / "external-instructions.md"
                external.write_text("External instructions must not be loaded.\n")
                if kind == "symlink":
                    runtime_rules.symlink_to(external)
                elif kind == "hardlink":
                    os.link(external, runtime_rules)
                before = snapshot(home)

                result = run_registration("install", home, project)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("제품 실행 지침", result.stderr)
                self.assertEqual(snapshot(home), before)
                self.assertEqual(
                    external.read_text(), "External instructions must not be loaded.\n",
                )

    def test_unmanaged_skill_collision_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            collision = home / SKILL_RELATIVE
            collision.mkdir(parents=True)
            (collision / "SKILL.md").write_text("mine\n", encoding="utf-8")

            result = run_registration("install", home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("덮어쓰지 않습니다", result.stderr)
            self.assertEqual((collision / "SKILL.md").read_text(), "mine\n")
            for filename in AGENT_NAMES:
                self.assertFalse(os.path.lexists(home / ".codex/agents" / filename))

    def test_unmanaged_agent_collision_is_preflighted_before_skill_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            collision = home / ".codex/agents/research-library-manager.toml"
            collision.parent.mkdir(parents=True)
            collision.write_text("name = 'mine'\n", encoding="utf-8")

            result = run_registration("install", home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("덮어쓰지 않습니다", result.stderr)
            self.assertEqual(collision.read_text(), "name = 'mine'\n")
            self.assertFalse(os.path.lexists(home / SKILL_RELATIVE))
            self.assertFalse(
                os.path.lexists(home / ".codex/agents/research-paper-converter.toml")
            )

    def test_unmanaged_rule_collision_is_preflighted_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            collision = home / ".codex/rules/research-library.rules"
            collision.parent.mkdir(parents=True)
            collision.write_text("# my rule\n", encoding="utf-8")

            result = run_registration("install", home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("덮어쓰지 않습니다", result.stderr)
            self.assertEqual(collision.read_text(), "# my rule\n")
            self.assertFalse(os.path.lexists(home / SKILL_RELATIVE))
            for filename in AGENT_NAMES:
                self.assertFalse(os.path.lexists(home / ".codex/agents" / filename))

    def test_unmanaged_sandbox_collision_is_preflighted_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            collision = home / ".codex/research-library-sandbox/config.toml"
            collision.parent.mkdir(parents=True)
            collision.write_text("# my config\n", encoding="utf-8")

            result = run_registration("install", home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("이 프로젝트 소유가 아니므로", result.stderr)
            self.assertEqual(collision.read_text(), "# my config\n")
            self.assertFalse(os.path.lexists(home / SKILL_RELATIVE))
            for filename in AGENT_NAMES:
                self.assertFalse(os.path.lexists(home / ".codex/agents" / filename))
            self.assertFalse(
                os.path.lexists(home / ".codex/rules/research-library.rules")
            )

    def test_unmanaged_sandbox_directory_is_never_claimed_or_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            sandbox = home / ".codex/research-library-sandbox"
            sandbox.mkdir(parents=True)
            foreign = sandbox / "foreign.txt"
            foreign.write_text("keep\n", encoding="utf-8")

            installed = run_registration("install", home)

            self.assertNotEqual(installed.returncode, 0)
            self.assertIn("이 프로젝트 소유가 아니므로", installed.stderr)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((sandbox / "config.toml").exists())
            self.assertFalse((sandbox / ".research-agent-owner").exists())
            self.assertFalse(os.path.lexists(home / SKILL_RELATIVE))

            removed = run_registration("uninstall", home)

            self.assertNotEqual(removed.returncode, 0)
            self.assertIn("삭제하지 않습니다", removed.stderr)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "keep\n")

    def test_symlinked_registration_parent_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are not supported")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            home = root / "home"
            external = root / "external"
            home.mkdir()
            external.mkdir()
            (home / ".agents").symlink_to(external, target_is_directory=True)

            result = run_registration("install", home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("안전한 폴더가 아닙니다", result.stderr)
            self.assertEqual(list(external.iterdir()), [])

    def test_uninstall_preflights_every_entry_before_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            installed = run_registration("install", home)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            collision = home / ".codex/agents/research-paper-converter.toml"
            collision.write_text("name = 'changed'\n", encoding="utf-8")

            result = run_registration("uninstall", home)

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((home / SKILL_RELATIVE).is_symlink())
            self.assertTrue(
                (home / ".codex/agents/research-library-manager.toml").is_file()
            )
            self.assertEqual(collision.read_text(), "name = 'changed'\n")

    def test_uninstall_rejects_hard_link_in_sandbox_tree_before_removal(self) -> None:
        if not hasattr(os, "link"):
            self.skipTest("hard links are not supported")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            installed = run_registration("install", home)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            external = home / "original.txt"
            external.write_text("keep\n", encoding="utf-8")
            linked = home / ".codex/research-library-sandbox/tmp/linked"
            linked.parent.mkdir()
            os.link(external, linked)

            result = run_registration("uninstall", home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("하드 링크", result.stderr)
            self.assertEqual(external.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue((home / SKILL_RELATIVE).is_symlink())
            self.assertTrue(linked.exists())

    def test_uninstall_unlinks_internal_symlink_without_touching_target(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are not supported")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            installed = run_registration("install", home)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            external = home / "original"
            external.mkdir()
            (external / "keep.txt").write_text("keep\n", encoding="utf-8")
            linked = home / ".codex/research-library-sandbox/tmp/link"
            linked.parent.mkdir()
            linked.symlink_to(external, target_is_directory=True)

            result = run_registration("uninstall", home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (external / "keep.txt").read_text(encoding="utf-8"), "keep\n"
            )
            self.assertFalse(
                (home / ".codex/research-library-sandbox").exists()
            )

    def test_skill_launchers_find_repository_from_unrelated_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            cwd = base / "unrelated-project"
            home.mkdir()
            cwd.mkdir()
            installed = run_registration("install", home)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            skill_link = home / SKILL_RELATIVE
            root_launcher = skill_link / "scripts/research-root"
            store_launcher = skill_link / "scripts/research-store"
            located = subprocess.run(
                [str(root_launcher)], cwd=cwd, capture_output=True, text=True
            )
            self.assertEqual(located.returncode, 0, located.stderr)
            self.assertEqual(Path(located.stdout.strip()), ROOT)

            fake_bin = base / "bin"
            fake_bin.mkdir()
            fake_codex = fake_bin / "codex"
            invocation = base / "codex-invocation.txt"
            fake_codex.write_text(
                """#!/bin/sh
set -eu
printf '%s\n' "$@" > "$FAKE_CODEX_INVOCATION"
[ "$1" = "sandbox" ]
shift
while [ "$1" != "--" ]; do shift; done
shift
exec "$@"
""",
                encoding="utf-8",
            )
            fake_codex.chmod(0o700)
            environment = dict(os.environ)
            environment["PATH"] = str(fake_bin) + os.pathsep + environment["PATH"]
            environment["HOME"] = str(home)
            environment["FAKE_CODEX_INVOCATION"] = str(invocation)
            help_result = subprocess.run(
                [str(store_launcher), "--help"],
                cwd=cwd,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("research-store", help_result.stdout)
            arguments = invocation.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                arguments[:5],
                [
                    "sandbox",
                    "-P",
                    "research-store",
                    "-C",
                    str(home / ".codex/research-library-sandbox"),
                ],
            )
            self.assertEqual(arguments[5], "--")
            self.assertEqual(arguments[6], str(ROOT / "research-store"))
            self.assertEqual(arguments[7:], ["--help"])
            removed = run_registration("uninstall", home)
            self.assertEqual(removed.returncode, 0, removed.stderr)

    def test_generated_rule_allows_only_the_exact_launcher_prefix(self) -> None:
        codex = shutil.which("codex")
        if codex is None:
            self.skipTest("Codex CLI is not available")
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            installed = run_registration("install", home)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            rule = home / ".codex/rules/research-library.rules"
            launcher = home / SKILL_RELATIVE / "scripts/research-store"

            allowed = subprocess.run(
                [
                    codex,
                    "execpolicy",
                    "check",
                    "--rules",
                    str(rule),
                    "--",
                    str(launcher),
                    "status",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(json.loads(allowed.stdout)["decision"], "allow")

            physical_launcher = SKILL_SOURCE / "scripts/research-store"
            physical = subprocess.run(
                [codex, "execpolicy", "check", "--rules", str(rule), "--",
                 str(physical_launcher), "import-pdf", "--attachment", "/tmp/paper.pdf"],
                capture_output=True, text=True,
            )
            self.assertEqual(physical.returncode, 0, physical.stderr)
            self.assertEqual(json.loads(physical.stdout)["decision"], "allow")

            lookalike = subprocess.run(
                [
                    codex,
                    "execpolicy",
                    "check",
                    "--rules",
                    str(rule),
                    "--",
                    str(launcher) + "-other",
                    "status",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(lookalike.returncode, 0, lookalike.stderr)
            self.assertNotEqual(
                json.loads(lookalike.stdout).get("decision"), "allow"
            )
            physical_lookalike = subprocess.run(
                [codex, "execpolicy", "check", "--rules", str(rule), "--",
                 str(physical_launcher) + "-other", "status"],
                capture_output=True, text=True,
            )
            self.assertEqual(physical_lookalike.returncode, 0,
                             physical_lookalike.stderr)
            self.assertNotEqual(json.loads(physical_lookalike.stdout).get("decision"),
                                "allow")


if __name__ == "__main__":
    unittest.main()
