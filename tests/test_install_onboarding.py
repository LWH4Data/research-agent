from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install_onboarding.py"
spec = importlib.util.spec_from_file_location("install_onboarding", SCRIPT)
assert spec and spec.loader
onboarding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(onboarding)


class InstallOnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("/tmp/research agent-test")
        self.output = io.StringIO()
        self.errors = io.StringIO()
        self.enterContext(redirect_stdout(self.output))
        self.enterContext(redirect_stderr(self.errors))
        self.enterContext(mock.patch.object(onboarding.sys, "platform", "darwin"))
        self.terminal = self.enterContext(
            mock.patch.object(onboarding.sys.stdin, "isatty", return_value=True)
        )
        self.offer = self.enterContext(
            mock.patch.object(onboarding, "offer_source_selection", return_value=True)
        )
        self.language = self.enterContext(
            mock.patch.object(onboarding, "resolve_ui_language", return_value="ko")
        )
        self.run = self.enterContext(mock.patch.object(onboarding.subprocess, "run"))
        self.which = self.enterContext(mock.patch.object(onboarding.shutil, "which", return_value="/fixture/codex"))

    def response(self, added=None, cancelled=False, processing=None, code=0) -> None:
        rows = added or []
        self.run.return_value = subprocess.CompletedProcess(
            [], code, json.dumps({"added": rows, "selected": rows or [{"id": "existing"}],
                "cancelled": cancelled, "registration": "registered",
                "processing": processing or {"state": "submitted", "request": {"state": "queued"}}}), ""
        )

    def test_multiple_folders_connect_in_one_call_without_reprompt(self) -> None:
        self.response(added=[{"id": "one"}, {"id": "two"}, {"id": "three"}])
        onboarding.run_onboarding(self.root)
        self.offer.assert_called_once_with(language="ko")
        self.run.assert_called_once_with(
            [str(self.root / "resources/skills/research-library/scripts/research-store"),
             "source-add", "--language", "ko"],
            check=False, stdout=subprocess.PIPE, text=True,
        )
        self.assertIn("폴더 3개를 연결했습니다", self.output.getvalue())
        self.assertIn("시각 검토를 접수했습니다", self.output.getvalue())

    def test_auto_uses_one_resolved_language_for_both_dialogs(self) -> None:
        self.language.side_effect = ["en", "ko"]
        self.response(added=[{"id": "one"}])
        onboarding.run_onboarding(self.root)
        self.language.assert_called_once_with("auto")
        self.offer.assert_called_once_with(language="en")
        command = self.run.call_args.args[0]
        self.assertEqual(command[-2:], ["--language", "en"])
        self.assertIn("Connected 1 folder", self.output.getvalue())
        self.assertIn("visual review has been submitted", self.output.getvalue())
        self.assertNotIn("폴더", self.output.getvalue())

    def test_explicit_language_overrides_detection_for_both_dialogs(self) -> None:
        for language, expected in (("en", "Connected 3 folder"), ("ko", "폴더 3개를 연결했습니다")):
            with self.subTest(language=language):
                self.output.truncate(0)
                self.output.seek(0)
                self.offer.reset_mock()
                self.run.reset_mock()
                self.language.reset_mock()
                self.response(added=[{"id": "one"}, {"id": "two"}, {"id": "three"}])
                onboarding.run_onboarding(self.root, language=language)
                self.language.assert_not_called()
                self.offer.assert_called_once_with(language=language)
                self.assertEqual(self.run.call_args.args[0][-2:], ["--language", language])
                self.assertIn(expected, self.output.getvalue())

    def test_english_connected_count_uses_singular_and_plural(self) -> None:
        for count, expected in (
            (1, "Connected 1 folder to look for PDFs."),
            (2, "Connected 2 folders to look for PDFs."),
        ):
            with self.subTest(count=count):
                self.output.truncate(0)
                self.output.seek(0)
                self.response(added=[{"id": str(index)} for index in range(count)])
                onboarding.run_onboarding(self.root, language="en")
                self.assertIn(expected, self.output.getvalue().splitlines())
                self.assertNotIn("folder(s)", self.output.getvalue())

    def test_main_resolves_auto_once_then_retains_that_language(self) -> None:
        self.language.side_effect = ["en", "ko"]
        self.response()
        with mock.patch.object(sys, "argv", [str(SCRIPT), "--root", str(self.root)]):
            self.assertEqual(onboarding.main(), 0)
        self.language.assert_called_once_with("auto")
        self.offer.assert_called_once_with(language="en")
        self.assertEqual(self.run.call_args.args[0][-2:], ["--language", "en"])

    def test_later_does_not_open_picker_or_register_sources(self) -> None:
        self.offer.return_value = False
        onboarding.run_onboarding(self.root)
        self.run.assert_not_called()
        self.assertIn("@Research Agent PDF 폴더 연결창 다시 열어줘.", self.output.getvalue())
        self.assertNotIn("bash", self.output.getvalue())

    def test_picker_cancel_is_successful_skip(self) -> None:
        self.response(cancelled=True)
        onboarding.run_onboarding(self.root)
        self.run.assert_called_once()
        self.assertIn("나중에 연결해도 됩니다", self.output.getvalue())
        self.assertNotIn("실패", self.output.getvalue())

    def test_duplicate_folders_report_already_connected(self) -> None:
        self.response()
        onboarding.run_onboarding(self.root)
        self.assertIn("이미 연결되어 있습니다", self.output.getvalue())
        self.assertIn("시각 검토를 접수했습니다", self.output.getvalue())

    def test_missing_codex_install_registers_only_and_truthfully_defers(self) -> None:
        self.which.return_value = None
        self.response(processing={"state": "deferred", "reason": "codex_unavailable"})
        onboarding.run_onboarding(self.root)
        command = self.run.call_args.args[0]
        self.assertIn(str(self.root / "scripts/select_sources.py"), command)
        self.assertIn("--installation", command)
        self.assertNotIn("--codex", command)
        self.assertIn("저장과 검토는 아직 시작하지 않았습니다", self.output.getvalue())

    def test_intake_failure_preserves_registration_and_reports_request(self) -> None:
        self.response(added=[{"id": "one"}], code=1, processing={"state": "deferred",
            "request": {"request_id": "a" * 32, "state": "intake"}, "error": "접수 실패"})
        onboarding.run_onboarding(self.root)
        self.assertIn("폴더 연결은 유지됩니다", self.output.getvalue())
        self.assertIn("a" * 32, self.output.getvalue())
        self.assertNotIn("시각 검토를 접수했습니다", self.output.getvalue())

    def test_existing_hold_is_reported_without_claiming_review_running(self) -> None:
        self.response(processing={"state": "submitted", "request": {"state": "held"}})
        onboarding.run_onboarding(self.root)
        self.assertIn("사용자가 중지한 상태를 유지", self.output.getvalue())
        self.assertNotIn("시각 검토를 접수했습니다", self.output.getvalue())

    def test_noninteractive_install_never_opens_ui_or_reads_input(self) -> None:
        self.terminal.return_value = False
        onboarding.run_onboarding(self.root)
        self.offer.assert_not_called()
        self.run.assert_not_called()

    def test_non_macos_install_never_opens_ui(self) -> None:
        with mock.patch.object(onboarding.sys, "platform", "linux"):
            onboarding.run_onboarding(self.root)
        self.offer.assert_not_called()
        self.run.assert_not_called()

    def test_gui_unavailable_keeps_install_success_and_later_instruction(self) -> None:
        self.offer.side_effect = RuntimeError("UI unavailable")
        onboarding.run_onboarding(self.root)
        self.run.assert_not_called()
        self.assertIn("설치는 완료되었습니다", self.output.getvalue())
        self.assertIn("연결창 다시 열어줘", self.output.getvalue())

    def test_source_add_error_keeps_install_success(self) -> None:
        self.run.return_value = subprocess.CompletedProcess([], 1, "", "원본 위치가 겹칩니다.")
        onboarding.run_onboarding(self.root)
        self.assertIn("설치는 완료되었습니다", self.output.getvalue())
        self.assertIn("연결창 다시 열어줘", self.output.getvalue())
        self.assertIn("원본 위치가 겹칩니다", self.errors.getvalue())

    def test_source_add_launch_error_keeps_install_success(self) -> None:
        self.run.side_effect = OSError("unavailable")
        onboarding.run_onboarding(self.root)
        self.assertIn("설치는 완료되었습니다", self.output.getvalue())

    def test_unrecognized_command_response_does_not_claim_registration(self) -> None:
        for value in ("", "[]", "null", "{}", '{"added": 3, "cancelled": false}'):
            with self.subTest(value=value):
                self.run.return_value = subprocess.CompletedProcess([], 0, value, "")
                onboarding.run_onboarding(self.root)
        self.assertNotIn("개를 연결했습니다", self.output.getvalue())
        self.assertIn("결과를 확인하지 못했습니다", self.output.getvalue())

    def test_english_skip_and_cancel_keep_the_later_instruction(self) -> None:
        self.offer.return_value = False
        onboarding.run_onboarding(self.root, language="en")
        self.run.assert_not_called()
        self.assertIn("@Research Agent Reopen the PDF folder connection window.", self.output.getvalue())
        self.offer.return_value = True
        self.response(cancelled=True)
        onboarding.run_onboarding(self.root, language="en")
        self.assertIn("You can connect folders later", self.output.getvalue())
        self.assertNotIn("could not", self.output.getvalue())

    def test_english_noninteractive_install_does_not_open_ui(self) -> None:
        self.terminal.return_value = False
        onboarding.run_onboarding(self.root, language="en")
        self.offer.assert_not_called()
        self.run.assert_not_called()
        self.assertIn("You can connect folders later", self.output.getvalue())
        self.assertNotIn("폴더", self.output.getvalue())

    def test_english_codex_unavailable_passes_language_to_registration_only_helper(self) -> None:
        self.which.return_value = None
        self.response(processing={"state": "deferred", "reason": "codex_unavailable"})
        onboarding.run_onboarding(self.root, language="en")
        self.offer.assert_called_once_with(language="en")
        command = self.run.call_args.args[0]
        self.assertIn("--installation", command)
        self.assertEqual(command[-2:], ["--language", "en"])
        self.assertIn("PDF storage and review have not started", self.output.getvalue())
        self.assertNotIn("visual review has been submitted", self.output.getvalue())

    def test_english_review_hold_readiness_and_failure_remain_distinct(self) -> None:
        scenarios = (
            ({"state": "submitted", "request": {"state": "held"}}, "remains stopped"),
            ({"state": "submitted", "request": {"state": "paused"}}, "remains stopped"),
            ({"state": "submitted", "request": {"state": "stopping"}}, "remains stopped"),
            ({"state": "submitted", "request": {"state": "evidence_ready"}}, "review processing for the selected folders is complete"),
            ({"state": "deferred", "error": "fixture failure", "request": {"request_id": "a" * 32}}, "processing did not finish"),
        )
        for processing, expected in scenarios:
            with self.subTest(processing=processing):
                self.output.truncate(0)
                self.output.seek(0)
                self.response(processing=processing)
                onboarding.run_onboarding(self.root, language="en")
                output = self.output.getvalue()
                self.assertIn(expected, output)
                self.assertNotIn("visual review has been submitted", output)
                self.assertNotIn("폴더", output)
                if processing.get("error"):
                    self.assertIn("Storage request: " + "a" * 32, output)
                    self.assertIn("fixture failure", self.errors.getvalue())

    def test_english_dialog_and_launch_errors_preserve_install_success(self) -> None:
        self.offer.side_effect = RuntimeError("UI unavailable")
        onboarding.run_onboarding(self.root, language="en")
        self.run.assert_not_called()
        self.assertIn("setup dialog could not open", self.output.getvalue())
        self.assertIn("installation is complete", self.output.getvalue())
        self.offer.side_effect = None
        self.run.side_effect = OSError("unavailable")
        onboarding.run_onboarding(self.root, language="en")
        self.assertIn("Folders could not be connected", self.output.getvalue())
        self.assertIn("Reopen the PDF folder connection window", self.output.getvalue())

    def test_english_invalid_response_and_registration_failure_do_not_claim_storage(self) -> None:
        responses = (
            [],
            {"added": [], "selected": [], "cancelled": False, "registration": "failed", "processing": {}, "error": "fixture failure"},
        )
        for response in responses:
            with self.subTest(response=response):
                self.output.truncate(0)
                self.output.seek(0)
                self.run.return_value = subprocess.CompletedProcess([], 1, json.dumps(response), "")
                onboarding.run_onboarding(self.root, language="en")
                self.assertIn("result could not be verified", self.output.getvalue())
                self.assertIn("Installation is complete", self.output.getvalue())
                self.assertNotIn("PDF storage processing is complete", self.output.getvalue())
        self.assertIn("fixture failure", self.errors.getvalue())

    def test_english_keyboard_interrupt_keeps_language_and_install_success(self) -> None:
        self.language.return_value = "en"
        with mock.patch.object(onboarding, "run_onboarding", side_effect=KeyboardInterrupt) as run, \
             mock.patch.object(sys, "argv", [str(SCRIPT), "--root", str(self.root), "--language", "en"]):
            self.assertEqual(onboarding.main(), 0)
        self.language.assert_called_once_with("en")
        run.assert_called_once_with(self.root, language="en")
        self.assertIn("Setup was interrupted. Installation is complete.", self.output.getvalue())
        self.assertIn("PDF storage or review may have started", self.output.getvalue())
        self.assertNotIn("설치", self.output.getvalue())

    def test_locale_detection_interrupt_keeps_install_success_without_ui_or_intake(self) -> None:
        for language, expected in (
            ("auto", "Setup was interrupted. Installation is complete."),
            ("en", "Setup was interrupted. Installation is complete."),
            ("ko", "안내를 중단했습니다. 설치는 완료되었습니다."),
        ):
            with self.subTest(language=language):
                self.output.truncate(0)
                self.output.seek(0)
                self.language.reset_mock()
                self.language.side_effect = KeyboardInterrupt
                with mock.patch.object(sys, "argv", [str(SCRIPT), "--root", str(self.root), "--language", language]):
                    self.assertEqual(onboarding.main(), 0)
                self.language.assert_called_once_with(language)
                self.assertIn(expected, self.output.getvalue())
                self.offer.assert_not_called()
                self.run.assert_not_called()

    def test_cli_rejects_unsupported_language_before_opening_ui(self) -> None:
        with mock.patch.object(sys, "argv", [str(SCRIPT), "--root", str(self.root), "--language", "fr"]):
            with self.assertRaises(SystemExit) as raised:
                onboarding.main()
        self.assertEqual(raised.exception.code, 2)
        self.offer.assert_not_called()
        self.run.assert_not_called()

    def test_keyboard_interrupt_still_exits_successfully(self) -> None:
        with mock.patch.object(onboarding, "run_onboarding", side_effect=KeyboardInterrupt), \
             mock.patch.object(sys, "argv", [str(SCRIPT), "--root", str(self.root)]):
            self.assertEqual(onboarding.main(), 0)
        self.assertIn("설치는 완료되었습니다", self.output.getvalue())
        self.assertIn("저장이나 검토가 시작되었을 수 있습니다", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
