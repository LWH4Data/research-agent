from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys


PICKER_PROMPT = "PDF를 찾아볼 폴더를 선택하세요. 원본에는 아무것도 기록하지 않습니다."


def macos_picker_script() -> str:
    prompt = json.dumps(PICKER_PROMPT, ensure_ascii=False)
    return f"""
(() => {{
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;
  try {{
    return app.chooseFolder({{withPrompt: {prompt}}}).toString();
  }} catch (error) {{
    if (error.number === -128) return "";
    throw error;
  }}
}})()
""".strip()


def choose_source() -> Path | None:
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
        value = result.stdout.strip()
        return Path(value) if value else None

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
        value = result.stdout.strip()
        return Path(value) if result.returncode == 0 and value else None

    raise RuntimeError(
        "이 운영체제에서는 폴더 선택창을 자동으로 열 수 없습니다. "
        "source-add 명령 뒤에 폴더 경로를 지정해 주세요."
    )
