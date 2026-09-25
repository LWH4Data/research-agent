from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys


PICKER_PROMPT = (
    "PDF를 찾아볼 폴더를 선택하세요. Command(⌘) 키를 누른 채 클릭하면 "
    "여러 폴더를 선택할 수 있습니다. 원본에는 아무것도 기록하지 않습니다."
)


def macos_onboarding_script() -> str:
    return """
(() => {
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;
  try {
    const choice = app.displayDialog(
      "Research Agent 설치가 완료됐어요.\\n\\n지금 PDF가 있는 폴더를 연결할까요?\\n원본 파일은 수정하지 않습니다.",
      {
        withTitle: "Research Agent",
        buttons: ["나중에 하기", "폴더 선택하기"],
        defaultButton: "폴더 선택하기",
        cancelButton: "나중에 하기"
      }
    );
    return JSON.stringify(choice.buttonReturned === "폴더 선택하기");
  } catch (error) {
    if (error.number === -128) return JSON.stringify(false);
    throw error;
  }
})()
""".strip()


def offer_source_selection() -> bool:
    """Ask once after installation; the caller decides whether GUI is appropriate."""
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", macos_onboarding_script()],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("폴더 연결 안내창을 열 수 없습니다.") from error
    try:
        selected = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("폴더 연결 안내창의 응답을 확인할 수 없습니다.") from error
    if not isinstance(selected, bool):
        raise RuntimeError("폴더 연결 안내창의 응답을 확인할 수 없습니다.")
    return selected


def macos_picker_script() -> str:
    prompt = json.dumps(PICKER_PROMPT, ensure_ascii=False)
    return f"""
(() => {{
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;
  try {{
    const folders = app.chooseFolder({{
      withPrompt: {prompt},
      multipleSelectionsAllowed: true
    }});
    return JSON.stringify(folders.map(folder => folder.toString()));
  }} catch (error) {{
    if (error.number === -128) return JSON.stringify([]);
    throw error;
  }}
}})()
""".strip()


def _parse_macos_selection(stdout: str) -> list[Path]:
    try:
        values = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("macOS 폴더 선택창이 올바른 선택 결과를 반환하지 않았습니다.") from error
    if not isinstance(values, list) or any(
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or not Path(value).is_absolute()
        for value in values
    ):
        raise RuntimeError("macOS 폴더 선택창이 올바른 폴더 경로 목록을 반환하지 않았습니다.")
    return [Path(value) for value in values]


def choose_sources() -> list[Path]:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", macos_picker_script()],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            detail = getattr(error, "stderr", "") or str(error)
            raise RuntimeError(
                f"macOS 폴더 선택창을 열 수 없습니다: {detail.strip()}"
            ) from error
        return _parse_macos_selection(result.stdout)

    if sys.platform.startswith("linux") and shutil.which("zenity"):
        try:
            result = subprocess.run(
                [
                    "zenity",
                    "--file-selection",
                    "--directory",
                    "--title=PDF를 찾아볼 폴더를 선택하세요",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise RuntimeError(f"폴더 선택창을 열 수 없습니다: {error}") from error
        value = result.stdout.removesuffix("\n")
        return [Path(value)] if result.returncode == 0 and value else []

    raise RuntimeError(
        "이 운영체제에서는 폴더 선택창을 자동으로 열 수 없습니다. "
        "source-add 명령 뒤에 폴더 경로를 지정해 주세요."
    )
