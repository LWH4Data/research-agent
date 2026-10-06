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
        with mock.patch.object(transport, "choose_confirmed_sources", return_value=paths) as choose, \
             mock.patch.object(transport, "connect_sources", return_value=(receipt, 0)) as connect, \
             redirect_stdout(io.StringIO()) as output:
            self.assertEqual(transport.main(self.args), 0)
        choose.assert_called_once_with(self.root, language="auto")
        connect.assert_called_once_with(self.root, paths, codex=str(self.base / "codex"),
            sandbox_home=str(self.base / "profile"), registration_only=False, installation=False)
        self.assertEqual(json.loads(output.getvalue()), receipt)
        self.assertFalse(self.root.exists())
        self.assertTrue(all(not path.exists() for path in paths))

    def test_explicit_paths_skip_picker_and_share_registration_only_control(self):
        with mock.patch.object(transport, "choose_confirmed_sources") as choose, \
             mock.patch.object(transport, "connect_sources", return_value=({}, 0)) as connect, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(transport.main(self.args + ["--language", "en", "--registration-only", "--", "/source"]), 0)
        choose.assert_not_called()
        self.assertEqual(connect.call_args.args[1], [Path("/source")])
        self.assertTrue(connect.call_args.kwargs["registration_only"])
        self.assertNotIn("language", connect.call_args.kwargs)

    def test_dialog_language_reaches_picker_without_entering_storage_options(self):
        paths = [Path("/fixture")]
        for language in ("auto", "ko", "en"):
            with self.subTest(language=language), \
                 mock.patch.object(transport, "choose_confirmed_sources", return_value=paths) as choose, \
                 mock.patch.object(transport, "connect_sources", return_value=({}, 0)) as connect, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(transport.main(self.args + ["--language", language]), 0)
            choose.assert_called_once_with(self.root, language=language)
            connect.assert_called_once_with(self.root, paths, codex=str(self.base / "codex"),
                sandbox_home=str(self.base / "profile"), registration_only=False, installation=False)

    def test_invalid_dialog_language_is_rejected_before_picker_and_storage(self):
        for options in (["--language", "fr"], ["--language=EN"], ["--language="],
                        ["--language", "en;touch unexpected"], ["--language"]):
            with self.subTest(options=options), \
                 mock.patch.object(transport, "choose_confirmed_sources") as choose, \
                 mock.patch.object(transport, "connect_sources") as connect, \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                transport.main(self.args + options)
            self.assertEqual(caught.exception.code, 2)
            choose.assert_not_called()
            connect.assert_not_called()

    def test_cancel_or_interrupt_never_runs_storage(self):
        for result, error in (([], None), (None, KeyboardInterrupt())):
            output = io.StringIO()
            with mock.patch.object(transport, "choose_confirmed_sources", return_value=result,
                                   side_effect=error), \
                 mock.patch.object(transport, "connect_sources") as connect, redirect_stdout(output):
                self.assertEqual(transport.main(self.args + ["--language", "en"]), 0)
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

    def test_isolated_helper_loads_canonical_modules_and_preserves_language_and_failure(self):
        picker = self.root / "src/research_store/picker.py"
        picker.parent.mkdir(parents=True)
        picker.write_text("from pathlib import Path\ndef choose_sources(language='auto'):\n"
                          "    return [Path('/fixture/first'), Path('/fixture/한글'), "
                          "Path('/fixture/language') / language]\n")
        helper = self.root / "scripts/source_intake.py"
        helper.parent.mkdir()
        helper.write_text("def connect_sources(root, paths, **options):\n"
                          "    return {'paths': [str(p) for p in paths], 'options': options}, 19\n")
        for language, extra in (("auto", []), ("ko", ["--language=ko"]),
                                ("en", ["--language", "en"])):
            with self.subTest(language=language):
                result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HELPER),
                                         *self.args, *extra], cwd=self.base, capture_output=True, text=True)
                self.assertEqual(result.returncode, 19, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["paths"], ["/fixture/first", "/fixture/한글",
                                                 f"/fixture/language/{language}"])
                self.assertNotIn("language", data["options"])
        self.assertFalse((self.root / ".research-store").exists())
        self.assertFalse((picker.parent / "__pycache__").exists())
        self.assertFalse((helper.parent / "__pycache__").exists())

    def installed_launcher_fixture(self):
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
        return launcher, env, codex, profile

    def test_installed_launcher_only_forwards_allowlisted_host_options(self):
        launcher, env, codex, profile = self.installed_launcher_fixture()
        prefix = ["--codex", str(codex), "--root", str(self.root), "--sandbox-home", str(profile)]
        cases = ((["source-add"], prefix + ["--language", "auto", "--"]),
                 (["source-add", "/fixture"], prefix + ["--language", "auto", "--", "/fixture"]),
                 (["source-add", "--language", "en"], prefix + ["--language", "en", "--"]),
                 (["source-add", "--language=ko"], prefix + ["--language", "ko", "--"]),
                 (["source-add", "--language=auto"], prefix + ["--language", "auto", "--"]),
                 (["source-add", "--registration-only", "/fixture"],
                  prefix + ["--language", "auto", "--registration-only", "--", "/fixture"]),
                 (["source-add", "--registration-only", "--language", "en", "/fixture"],
                  prefix + ["--language", "en", "--registration-only", "--", "/fixture"]),
                 (["source-add", "/first", "--language=ko", "/last"],
                  prefix + ["--language", "ko", "--", "/first", "/last"]),
                 (["source-add", "--help"], ["--help"]),
                 (["source-add", "-h"], ["--help"]))
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(launcher), *arguments], env=env, cwd=self.base,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {"host": expected})

    def test_installed_launcher_rejects_invalid_duplicate_or_trusted_options(self):
        launcher, env, _, _ = self.installed_launcher_fixture()
        options = (["--language", "fr"], ["--language=EN"], ["--language="], ["--language"],
                   ["--language", "en;touch unexpected"],
                   ["--language=en", "--language", "ko"],
                   ["--registration-only", "--registration-only", "/fixture"],
                   ["--root", "/outside"], ["--codex", "/outside"],
                   ["--sandbox-home", "/outside"], ["--installation"],
                   ["--config", "/outside"], ["--unknown"],
                   ["/fixture", "--root", "/outside"], ["--help", "/fixture"])
        for arguments in options:
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(launcher), "source-add", *arguments], env=env, cwd=self.base,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
        self.assertFalse((self.base / "unexpected").exists())
        self.assertFalse((self.root / ".research-store").exists())

    def test_installed_launcher_double_dash_preserves_literal_paths_and_options(self):
        launcher, env, codex, profile = self.installed_launcher_fixture()
        paths = ["/fixture/한글", "/fixture/--language=en", "/fixture/quote'\"$(touch unexpected)\nline",
                 "--root", "/outside", "--language=en"]
        for options in ([], ["--registration-only", "--language=ko"]):
            with self.subTest(options=options):
                result = subprocess.run([str(launcher), "source-add", *options, "--", *paths],
                                        env=env, cwd=self.base, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = ["--codex", str(codex), "--root", str(self.root),
                            "--sandbox-home", str(profile), "--language", "ko" if options else "auto"]
                if options:
                    expected.append("--registration-only")
                self.assertEqual(json.loads(result.stdout), {"host": [*expected, "--", *paths]})
        self.assertFalse((self.base / "unexpected").exists())

    def test_non_picker_operations_still_use_the_constrained_launcher(self):
        launcher, env, _, profile = self.installed_launcher_fixture()
        for arguments in (["--config", "/fixture/config", "source-add"], ["source-list"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(launcher), *arguments], env=env, cwd=self.base,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {"sandbox": [
                    "sandbox", "-P", "research-store", "-C", str(profile), "--",
                    str(self.root / "research-store"), *arguments]})
