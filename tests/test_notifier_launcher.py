from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import TestCase


LAUNCHER = (Path(__file__).resolve().parents[1]
            / "resources/skills/research-library/scripts/research-review")


class NotifierLauncherTests(TestCase):
    def test_notifier_failure_does_not_turn_successful_review_start_into_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "research-agent"
            launcher = root / "resources/skills/research-library/scripts/research-review"
            launcher.parent.mkdir(parents=True)
            shutil.copy2(LAUNCHER, launcher)
            launcher.chmod(0o700)
            (root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
            runtime = root / ".venv/bin"
            runtime.mkdir(parents=True)
            fake_python = runtime / "python"
            fake_python.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" > \"$FAKE_PYTHON_ARGS\"\n"
                "echo '안내: 알림 감시기를 시작할 수 없습니다.' >&2\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o700)
            fake_python_args = base / "fake-python-args.txt"

            home = base / "home"
            sandbox = home / ".codex/research-library-sandbox"
            sandbox.mkdir(parents=True)
            owner = (
                "# research-agent-registration-v1\n"
                f"# research-agent-root: {root}\n"
            )
            (sandbox / "config.toml").write_text(owner)
            (sandbox / ".research-agent-owner").write_text(owner)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            codex = bin_dir / "codex"
            codex.write_text("#!/bin/sh\nprintf '{\"state\":\"running\"}\\n'\n",
                             encoding="utf-8")
            codex.chmod(0o700)

            result = subprocess.run(
                [str(launcher), "start"],
                env={**os.environ, "HOME": str(home),
                     "FAKE_PYTHON_ARGS": str(fake_python_args),
                     "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads(result.stdout), {"state": "running"})
            self.assertIn("알림", result.stderr.decode("utf-8"))
            self.assertIn("--launch-notifier", fake_python_args.read_text())
