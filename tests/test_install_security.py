from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


PROJECT_MARKER_CONTENT = "research-agent-owned-root-v1"


def source_snapshot(root: Path) -> dict[str, tuple[object, ...]]:
    snapshot: dict[str, tuple[object, ...]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        info = path.lstat()
        snapshot[path.relative_to(root).as_posix()] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            stat.S_IMODE(info.st_mode),
            info.st_uid,
            info.st_gid,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
            info.st_nlink,
        )
    return snapshot


class InstallerSecurityTests(unittest.TestCase):
    def test_rejects_managed_symlink_through_internal_bridge(self) -> None:
        if not hasattr(os, "link") or not hasattr(os, "symlink"):
            self.skipTest("links are not supported")
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "agent"
            source = root / "source"
            project.mkdir()
            source.mkdir()
            (project / ".research-agent-root").write_text(
                PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
            )
            shutil.copy2(repository / "install.sh", project / "install.sh")

            victim = source / "original.pdf"
            victim.write_bytes(b"keep")
            bridge = project / "bridge/lib/site-packages"
            bridge.mkdir(parents=True)
            os.link(victim, bridge / "victim.py")
            (project / ".venv").mkdir()
            (project / ".venv/lib").symlink_to(
                project / "bridge/lib", target_is_directory=True
            )
            before = source_snapshot(source)

            result = subprocess.run(
                ["sh", str(project / "install.sh")],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("관리 경로 밖", result.stderr)
            self.assertEqual(source_snapshot(source), before)
            self.assertFalse(any(project.glob(".research-install.*")))


if __name__ == "__main__":
    unittest.main()
