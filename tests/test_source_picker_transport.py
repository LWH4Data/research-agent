from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT = Path(__file__).resolve().parents[1]
HELPER = PROJECT / "scripts/select_sources.py"
spec = importlib.util.spec_from_file_location("source_picker_transport", HELPER)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class SourcePickerTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "store"
        self.args = ["--codex", str(self.base / "codex"), "--root", str(self.root),
                     "--sandbox-home", str(self.base / "profile")]

    def test_only_confirmed_paths_reach_fixed_sandbox_as_literal_arguments(self):
        paths = [self.base / "한글 자료", self.base / "quote'\"$(touch unexpected)\nline"]
        with mock.patch.object(transport, "choose_confirmed_sources", return_value=paths), \
             mock.patch.object(transport.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(transport.main(self.args), 0)
        self.assertEqual(run.call_args.args[0], [str(self.base / "codex"), "sandbox",
            "-P", "research-store", "-C", str(self.base / "profile"), "--",
            str(self.root / "research-store"), "source-add", "--", *map(str, paths)])
        self.assertEqual(run.call_args.kwargs["env"]["CODEX_HOME"], str(self.base / "profile"))
        self.assertEqual(set(run.call_args.kwargs), {"env", "check"})
        self.assertFalse(self.root.exists())
        self.assertTrue(all(not path.exists() for path in paths))

    def test_cancel_or_interrupt_never_runs_storage(self):
        for result, error in (([], None), (None, KeyboardInterrupt())):
            output = io.StringIO()
            with mock.patch.object(transport, "choose_confirmed_sources", return_value=result,
                                   side_effect=error), \
                 mock.patch.object(transport.subprocess, "run") as run, redirect_stdout(output):
                self.assertEqual(transport.main(self.args), 0)
            self.assertEqual(json.loads(output.getvalue()), {"added": [], "cancelled": True})
            run.assert_not_called()
            self.assertFalse(self.root.exists())

    def test_invalid_result_or_picker_error_never_registers(self):
        for value, error in ((None, None), ([Path("relative")], None),
                             ([Path("/valid"), "/string"], None),
                             ([Path("/bad\0path")], None),
                             (None, RuntimeError("GUI unavailable")),
                             (None, PermissionError("not permitted"))):
            with self.subTest(value=value, error=error), \
                 mock.patch.object(transport, "choose_confirmed_sources", return_value=value,
                                   side_effect=error), \
                 mock.patch.object(transport.subprocess, "run") as run, \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(transport.main(self.args), 2)
                run.assert_not_called()

    def test_child_failure_has_no_unrestricted_retry(self):
        for code, expected in ((17, 17), (-15, 143)):
            with mock.patch.object(transport, "choose_confirmed_sources", return_value=[Path("/source")]), \
                 mock.patch.object(transport.subprocess, "run") as run:
                run.return_value.returncode = code
                self.assertEqual(transport.main(self.args), expected)
                self.assertEqual(run.call_count, 1)
        with mock.patch.object(transport, "choose_confirmed_sources", return_value=[Path("/source")]), \
             mock.patch.object(transport.subprocess, "run", side_effect=PermissionError) as run, \
             redirect_stderr(io.StringIO()):
            self.assertEqual(transport.main(self.args), 1)
            self.assertEqual(run.call_count, 1)

    def test_extra_options_and_relative_trusted_paths_are_rejected(self):
        for args in (self.args + ["--config", "/outside"],
                     self.args + ["--", "sh"], ["--codex", "relative", *self.args[2:]]):
            with mock.patch.object(transport, "choose_confirmed_sources") as choose, \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                transport.main(args)
            self.assertEqual(caught.exception.code, 2)
            choose.assert_not_called()

    def test_isolated_helper_loads_canonical_picker_and_preserves_child_output(self):
        # Disposable fixture replaces only the UI, never shows a real picker.
        picker = self.root / "src/research_store/picker.py"
        picker.parent.mkdir(parents=True)
        picker.write_text("from pathlib import Path\ndef choose_sources():\n"
                          "    return [Path('/fixture/first'), Path('/fixture/한글')]\n")
        child = self.base / "codex"
        child.write_text("#!" + sys.executable + "\nimport json, sys\n"
                         "print(json.dumps(sys.argv[1:]))\n"
                         "print('storage failure', file=sys.stderr)\nsys.exit(19)\n")
        child.chmod(0o700)
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HELPER), *self.args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 19)
        self.assertEqual(result.stderr, "storage failure\n")
        self.assertEqual(json.loads(result.stdout)[-4:],
                         ["source-add", "--", "/fixture/first", "/fixture/한글"])
        self.assertFalse((self.root / ".research-store").exists())
        self.assertFalse((picker.parent / "__pycache__").exists())

    def test_installed_launcher_only_routes_exact_no_argument_source_add_to_host(self):
        self.root.mkdir()
        (self.root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
        launcher = self.root / "resources/skills/research-library/scripts/research-store"
        launcher.parent.mkdir(parents=True)
        shutil.copy2(PROJECT / "resources/skills/research-library/scripts/research-store", launcher)
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "select_sources.py").write_text("import json, sys\n"
                                                 "print(json.dumps({'host': sys.argv[1:]}))\n")
        venv = self.root / ".venv/bin"
        venv.mkdir(parents=True)
        (venv / "python").symlink_to(sys.executable)
        home = self.base / "home"
        profile = home / ".codex/research-library-sandbox"
        profile.mkdir(parents=True)
        owner = f"# research-agent-registration-v1\n# research-agent-root: {self.root}\n"
        (profile / "config.toml").write_text(owner)
        (profile / ".research-agent-owner").write_text(owner)
        binary = self.base / "bin"
        binary.mkdir()
        codex = binary / "codex"
        codex.write_text("#!" + sys.executable + "\nimport json, sys\n"
                         "print(json.dumps({'sandbox': sys.argv[1:]}))\n")
        codex.chmod(0o700)
        env = dict(os.environ, HOME=str(home), PATH=str(binary) + os.pathsep + os.environ["PATH"])
        for arguments, expected in ((["source-add"], "host"),
                                    (["source-add", "/fixture"], "sandbox"),
                                    (["source-add", "--help"], "sandbox"),
                                    (["--config", "/fixture/config", "source-add"], "sandbox"),
                                    (["source-list"], "sandbox")):
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(launcher), *arguments], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(set(data), {expected})
                if expected == "host":
                    self.assertEqual(data[expected], ["--codex", str(codex), "--root", str(self.root),
                                                     "--sandbox-home", str(profile)])
                else:
                    self.assertEqual(data[expected], ["sandbox", "-P", "research-store", "-C",
                        str(profile), "--", str(self.root / "research-store"), *arguments])
