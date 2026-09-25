from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from research_store.picker import (
    choose_sources,
    macos_onboarding_script,
    macos_picker_script,
    offer_source_selection,
)


class InstallDialogTests(unittest.TestCase):
    def test_macos_accepts_explicit_choice_and_cancellation(self) -> None:
        for selected in (True, False):
            with self.subTest(selected=selected), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch(
                "research_store.picker.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, json.dumps(selected), ""),
            ):
                self.assertIs(offer_source_selection(), selected)

    def test_malformed_dialog_result_is_not_a_choice(self) -> None:
        for value in ("", "null", "1", '"true"', "[]", "{}"):
            with self.subTest(value=value), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch(
                "research_store.picker.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, value, ""),
            ):
                with self.assertRaisesRegex(RuntimeError, "응답"):
                    offer_source_selection()

    def test_launch_failures_are_optional_onboarding_errors(self) -> None:
        for error in (OSError("no UI"), subprocess.CalledProcessError(1, ["osascript"])):
            with self.subTest(error=error), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch("research_store.picker.subprocess.run", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "안내창을 열 수 없습니다"):
                    offer_source_selection()

    def test_non_macos_never_opens_dialog(self) -> None:
        with mock.patch("research_store.picker.sys.platform", "linux"), mock.patch(
            "research_store.picker.subprocess.run"
        ) as run:
            self.assertFalse(offer_source_selection())
            run.assert_not_called()

    @unittest.skipUnless(sys.platform == "darwin", "macOS-only dialog compiler")
    def test_macos_onboarding_script_compiles_without_opening_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["osacompile", "-l", "JavaScript", "-e", macos_onboarding_script(),
                 "-o", str(Path(directory) / "Onboarding.scpt")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class FolderPickerTests(unittest.TestCase):
    def macos_selection(self, stdout: str) -> list[Path]:
        with mock.patch("research_store.picker.sys.platform", "darwin"), mock.patch(
            "research_store.picker.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, stdout, ""),
        ) as run:
            selected = choose_sources()
        self.assertEqual(run.call_args.args[0][:3], ["osascript", "-l", "JavaScript"])
        self.assertTrue(run.call_args.kwargs["check"])
        return selected

    def test_macos_accepts_three_folders(self) -> None:
        paths = [f"/tmp/research-agent-test{number}" for number in (1, 2, 3)]
        self.assertEqual(
            self.macos_selection(json.dumps(paths) + "\n"),
            [Path(path) for path in paths],
        )

    def test_macos_preserves_unicode_spaces_and_newlines_inside_paths(self) -> None:
        paths = ["/tmp/한글 자료", "/tmp/ leading and trailing ", "/tmp/line\nbreak\n"]
        self.assertEqual(
            self.macos_selection(json.dumps(paths, ensure_ascii=False) + "\n"),
            [Path(path) for path in paths],
        )

    def test_macos_accepts_one_folder(self) -> None:
        self.assertEqual(self.macos_selection('["/tmp/Papers"]\n'), [Path("/tmp/Papers")])

    def test_macos_cancellation_is_an_empty_list(self) -> None:
        self.assertEqual(self.macos_selection("[]\n"), [])

    def test_macos_rejects_malformed_json(self) -> None:
        for stdout in ("", "\n", "/tmp/Papers\n", '["/tmp/One"]\n["/tmp/Two"]', "["):
            with self.subTest(stdout=stdout), self.assertRaisesRegex(
                RuntimeError, "올바른 선택 결과"
            ):
                self.macos_selection(stdout)

    def test_macos_rejects_invalid_path_list_before_returning_any_selection(self) -> None:
        for values in (
            None,
            "/tmp/Papers",
            {"path": "/tmp/Papers"},
            ["/tmp/Valid", None],
            [False],
            [1],
            [["/tmp/Papers"]],
            [""],
            ["relative/path"],
            ["~/Papers"],
            [" "],
            ["/tmp/null\x00byte"],
        ):
            with self.subTest(values=values), self.assertRaisesRegex(
                RuntimeError, "올바른 폴더 경로 목록"
            ):
                self.macos_selection(json.dumps(values))

    def test_macos_launch_and_script_failures_are_reported(self) -> None:
        for error in (
            OSError("osascript unavailable"),
            subprocess.CalledProcessError(1, ["osascript"], stderr="picker failed"),
        ):
            with self.subTest(error=error), mock.patch(
                "research_store.picker.sys.platform", "darwin"
            ), mock.patch("research_store.picker.subprocess.run", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "macOS 폴더 선택창을 열 수 없습니다"):
                    choose_sources()

    def test_linux_keeps_single_selection_and_path_whitespace(self) -> None:
        path = "/tmp/ folder\nwith newline \n"
        with mock.patch("research_store.picker.sys.platform", "linux"), mock.patch(
            "research_store.picker.shutil.which", return_value="/usr/bin/zenity"
        ), mock.patch(
            "research_store.picker.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, path + "\n", ""),
        ):
            self.assertEqual(choose_sources(), [Path(path)])

    def test_linux_cancel_is_an_empty_list(self) -> None:
        with mock.patch("research_store.picker.sys.platform", "linux"), mock.patch(
            "research_store.picker.shutil.which", return_value="/usr/bin/zenity"
        ), mock.patch(
            "research_store.picker.subprocess.run",
            return_value=subprocess.CompletedProcess([], 1, "", ""),
        ):
            self.assertEqual(choose_sources(), [])

    @unittest.skipUnless(sys.platform == "darwin", "macOS-only picker compiler")
    def test_macos_picker_script_compiles_without_opening_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Picker.scpt"
            result = subprocess.run(
                [
                    "osacompile", "-l", "JavaScript", "-e", macos_picker_script(),
                    "-o", str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
