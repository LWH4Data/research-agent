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
        self.run = self.enterContext(mock.patch.object(onboarding.subprocess, "run"))

    def response(self, added=None, cancelled=False) -> None:
        self.run.return_value = subprocess.CompletedProcess(
            [], 0, json.dumps({"added": added or [], "cancelled": cancelled}), ""
        )

    def test_multiple_folders_connect_in_one_call_without_reprompt(self) -> None:
        self.response(added=[{"id": "one"}, {"id": "two"}, {"id": "three"}])
        onboarding.run_onboarding(self.root)
        self.offer.assert_called_once_with()
        self.run.assert_called_once_with(
            [str(self.root / "research-store"), "source-add"],
            check=False, capture_output=True, text=True,
        )
        self.assertIn("폴더 3개를 연결했습니다", self.output.getvalue())

    def test_later_does_not_open_picker_or_register_sources(self) -> None:
        self.offer.return_value = False
        onboarding.run_onboarding(self.root)
        self.run.assert_not_called()
        self.assertIn("bash '/tmp/research agent-test/add-source.sh'", self.output.getvalue())

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
        self.assertIn("add-source.sh", self.output.getvalue())

    def test_source_add_error_keeps_install_success(self) -> None:
        self.run.return_value = subprocess.CompletedProcess([], 1, "", "원본 위치가 겹칩니다.")
        onboarding.run_onboarding(self.root)
        self.assertIn("설치는 완료되었습니다", self.output.getvalue())
        self.assertIn("add-source.sh", self.output.getvalue())
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

    def test_keyboard_interrupt_still_exits_successfully(self) -> None:
        with mock.patch.object(onboarding, "run_onboarding", side_effect=KeyboardInterrupt), \
             mock.patch.object(sys, "argv", [str(SCRIPT), "--root", str(self.root)]):
            self.assertEqual(onboarding.main(), 0)
        self.assertIn("설치는 완료되었습니다", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
