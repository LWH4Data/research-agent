"""Actual Codex worker profile, disposable data, and fake model responses only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    sys.platform == "darwin" and os.environ.get("RESEARCH_AGENT_RUN_SANDBOX_TEST") == "1",
    "set RESEARCH_AGENT_RUN_SANDBOX_TEST=1 on macOS outside an existing sandbox",
)
class ProcessIdentityIntegrationTests(unittest.TestCase):
    def test_worker_profile_runs_supervision_without_source_write_permission(self):
        codex = shutil.which("codex")
        if codex is None:
            self.skipTest("Codex CLI is not available")
        with tempfile.TemporaryDirectory(prefix="research-process-profile-") as directory:
            base = Path(directory).resolve()
            home, runtime = base / "home", base / "runtime"
            home.mkdir()
            for line in (ROOT / "packaging/runtime-files.txt").read_text().splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                fields = line.split()
                target = runtime / fields[-1]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / fields[0], target)
            temporary = runtime / ".research-store/test-temp"
            temporary.mkdir(parents=True)
            original = base / "original.txt"
            original.write_bytes(b"untouched original\n")
            before = original.stat()
            registration = subprocess.run(
                [sys.executable, "-I", "-B", str(runtime / "scripts/personal_registration.py"),
                 "install", "--root", str(runtime), "--home", str(home)],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(registration.returncode, 0, registration.stderr)
            profile = home / ".codex/research-library-sandbox"
            env = dict(os.environ, HOME=str(home), CODEX_HOME=str(profile),
                       TMPDIR=str(temporary), TMP=str(temporary), TEMP=str(temporary),
                       PYTHONDONTWRITEBYTECODE="1", RESEARCH_AGENT_NOTIFICATIONS="0")
            # The real profile is applied by the real CLI. All model children in
            # the supervision suite are local fixtures; no account is contacted.
            probe = '''
import importlib.util,json,os,subprocess,sys,unittest
from pathlib import Path
runtime,repository,original=map(Path,sys.argv[1:])
sys.path[:0]=[str(repository/'src'),str(repository/'tests')]
spec=importlib.util.spec_from_file_location('profile_identity',runtime/'scripts/background_lifecycle.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
identity=runner.process_identity(os.getpid())
assert identity and identity['pid']==os.getpid(), identity
try:
    ps=subprocess.run(['/bin/ps','-p',str(os.getpid()),'-o','pgid=,lstart='],capture_output=True,text=True)
    ps_result={'returncode':ps.returncode,'stderr':ps.stderr}
except OSError as error:
    ps_result={'errno':error.errno}
try:
    original.write_bytes(b'must be denied')
except PermissionError:
    pass
else:
    raise AssertionError('Original write was not denied')
import test_lifecycle_supervision as supervision
supervision.runner=runner
suite=unittest.defaultTestLoader.loadTestsFromModule(supervision)
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'identity':identity,'ps':ps_result,'tests':result.testsRun,'skipped':len(result.skipped)}))
sys.exit(0 if result.wasSuccessful() and result.testsRun>=8 and not result.skipped else 1)
'''
            result = subprocess.run(
                [codex, "sandbox", "-P", "research-review-worker", "-C", str(profile), "--",
                 sys.executable, "-I", "-B", "-c", probe, str(runtime), str(ROOT), str(original)],
                env=env, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout.splitlines()[-1])
            self.assertEqual(report["skipped"], 0, report)
            self.assertGreaterEqual(report["tests"], 8)
            self.assertEqual(original.read_bytes(), b"untouched original\n")
            after = original.stat()
            self.assertEqual((before.st_ino, before.st_mtime_ns, before.st_mode),
                             (after.st_ino, after.st_mtime_ns, after.st_mode))


if __name__ == "__main__":
    unittest.main()
