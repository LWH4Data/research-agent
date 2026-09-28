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

    def test_only_confirmed_paths_reach_shared_intake_as_literal_arguments(self):
        paths = [self.base / "한글 자료", self.base / "quote'\"$(touch unexpected)\nline"]
        receipt = {"registration": "registered", "processing": {"state": "submitted"}}
        with mock.patch.object(transport, "choose_confirmed_sources", return_value=paths), \
             mock.patch.object(transport, "connect_sources", return_value=(receipt, 0)) as connect, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(transport.main(self.args), 0)
        connect.assert_called_once_with(self.root, paths, codex=str(self.base / "codex"),
            sandbox_home=str(self.base / "profile"), registration_only=False, installation=False)
        self.assertEqual(json.loads(output.getvalue()), receipt)
        self.assertFalse(self.root.exists())
        self.assertTrue(all(not path.exists() for path in paths))

    def test_explicit_paths_skip_picker_and_share_registration_only_control(self):
        with mock.patch.object(transport, "choose_confirmed_sources") as choose, \
             mock.patch.object(transport, "connect_sources", return_value=({}, 0)) as connect, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(transport.main(self.args + ["--registration-only", "--", "/source"]), 0)
        choose.assert_not_called()
        self.assertEqual(connect.call_args.args[1], [Path("/source")])
        self.assertTrue(connect.call_args.kwargs["registration_only"])

    def test_cancel_or_interrupt_never_runs_storage(self):
        for result, error in (([], None), (None, KeyboardInterrupt())):
            output = io.StringIO()
            with mock.patch.object(transport, "choose_confirmed_sources", return_value=result,
                                   side_effect=error), \
                 mock.patch.object(transport, "connect_sources") as connect, redirect_stdout(output):
                self.assertEqual(transport.main(self.args), 0)
            self.assertTrue(json.loads(output.getvalue())["cancelled"])
            self.assertEqual(json.loads(output.getvalue())["selected"], [])
            connect.assert_not_called()
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
                 mock.patch.object(transport, "connect_sources") as connect, \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(transport.main(self.args), 2)
                connect.assert_not_called()

    def test_child_failure_has_no_unrestricted_retry(self):
        for code in (17, 143):
            with mock.patch.object(transport, "choose_confirmed_sources", return_value=[Path("/source")]), \
                 mock.patch.object(transport, "connect_sources", return_value=({}, code)) as connect, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(transport.main(self.args), code)
                self.assertEqual(connect.call_count, 1)

    def test_extra_options_and_relative_trusted_paths_are_rejected(self):
        for args in (self.args + ["--config", "/outside"],
                     self.args + ["--", "sh"], ["--codex", "relative", *self.args[2:]],
                     self.args + ["--registration-only"]):
            with mock.patch.object(transport, "choose_confirmed_sources") as choose, \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                transport.main(args)
            self.assertEqual(caught.exception.code, 2)
            choose.assert_not_called()

    def test_isolated_helper_loads_canonical_modules_and_preserves_failure(self):
        picker = self.root / "src/research_store/picker.py"
        picker.parent.mkdir(parents=True)
        picker.write_text("from pathlib import Path\ndef choose_sources():\n"
                          "    return [Path('/fixture/first'), Path('/fixture/한글')]\n")
        helper = self.root / "scripts/source_intake.py"
        helper.parent.mkdir()
        helper.write_text("def connect_sources(root, paths, **options):\n"
                          "    return {'paths': [str(p) for p in paths]}, 19\n")
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HELPER), *self.args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 19)
        self.assertEqual(json.loads(result.stdout)["paths"], ["/fixture/first", "/fixture/한글"])
        self.assertFalse((self.root / ".research-store").exists())
        self.assertFalse((picker.parent / "__pycache__").exists())
        self.assertFalse((helper.parent / "__pycache__").exists())

    def test_installed_launcher_routes_source_add_paths_as_data_not_host_options(self):
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
                                    (["source-add", "/fixture"], "host"),
                                    (["source-add", "--root", "/outside"], "host"),
                                    (["source-add", "--installation"], "host"),
                                    (["source-add", "--registration-only", "/fixture"], "host"),
                                    (["source-add", "--help"], "host"),
                                    (["--config", "/fixture/config", "source-add"], "sandbox"),
                                    (["source-list"], "sandbox")):
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(launcher), *arguments], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(set(data), {expected})
                if expected == "host":
                    if arguments[1:] == ["--help"]:
                        self.assertEqual(data[expected], ["--help"])
                    else:
                        options = arguments[1:]
                        extra = []
                        if options[:1] == ["--registration-only"]:
                            extra, options = options[:1], options[1:]
                        self.assertEqual(data[expected], ["--codex", str(codex), "--root", str(self.root),
                            "--sandbox-home", str(profile), *extra, "--", *options])
                else:
                    self.assertEqual(data[expected], ["sandbox", "-P", "research-store", "-C",
                        str(profile), "--", str(self.root / "research-store"), *arguments])
