"""Optional, interactive folder connection after installation has succeeded."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from research_store.picker import offer_source_selection, resolve_ui_language


MESSAGES = {
    "ko": {
        "later": "폴더는 나중에 연결해도 됩니다. Codex를 열고 Research Agent에 요청하세요.",
        "later_prompt": "  @Research Agent PDF 폴더 연결창 다시 열어줘.",
        "dialog_error": "안내창을 열지 못했지만 설치는 완료되었습니다.",
        "confirm": "폴더를 추가하고 목록을 확인하면 PDF 저장과 시각 검토를 시작합니다.",
        "connection_error": "폴더를 연결하지 못했지만 설치는 완료되었습니다.",
        "response_error": "폴더 연결 결과를 확인하지 못했습니다. 설치는 완료되었습니다.",
        "connected": "PDF를 찾아볼 폴더 {count}개를 연결했습니다.",
        "already_connected": "선택한 폴더는 이미 연결되어 있습니다.",
        "held": "PDF 저장 처리를 마쳤습니다. 시각 검토는 사용자가 중지한 상태를 유지합니다.",
        "ready": "선택한 폴더의 PDF 저장·검토 처리를 마쳤습니다.",
        "submitted": "PDF 저장 처리를 마쳤고 시각 검토를 접수했습니다. 저장된 상태에서 진행을 확인할 수 있습니다.",
        "codex_unavailable": "폴더 연결은 유지됩니다. Codex 실행 파일을 찾지 못해 PDF 저장과 검토는 아직 시작하지 않았습니다.",
        "request_storage": "Codex에서 Research Agent에 연결한 폴더의 PDF 저장을 요청하세요.",
        "processing_error": "폴더 연결은 유지됩니다. PDF 저장·검토 처리를 마치지 못했습니다. 설치는 완료되었습니다.",
        "request_retry": "Codex에서 Research Agent에 저장된 접수 상태 확인과 재시도를 요청하세요.",
        "receipt": "저장 접수: {request_id}",
        "interrupted": "\n안내를 중단했습니다. 설치는 완료되었습니다.",
        "may_have_started": "폴더 목록을 확인했다면 PDF 저장이나 검토가 시작되었을 수 있습니다.",
        "request_status": "Codex에서 Research Agent에 저장된 접수 상태 확인을 요청하세요.",
    },
    "en": {
        "later": "You can connect folders later. Open Codex and ask Research Agent.",
        "later_prompt": "  @Research Agent Reopen the PDF folder connection window.",
        "dialog_error": "The setup dialog could not open, but installation is complete.",
        "confirm": "Add folders and confirm the list to start saving PDFs and visual review.",
        "connection_error": "Folders could not be connected, but installation is complete.",
        "response_error": "The folder connection result could not be verified. Installation is complete.",
        "connected_one": "Connected 1 folder to look for PDFs.",
        "connected": "Connected {count} folders to look for PDFs.",
        "already_connected": "The selected folders are already connected.",
        "held": "PDF storage processing is complete. Visual review remains stopped as requested.",
        "ready": "PDF storage and review processing for the selected folders is complete.",
        "submitted": "PDF storage processing is complete and visual review has been submitted. Check progress in the saved status.",
        "codex_unavailable": "Folders remain connected. PDF storage and review have not started because the Codex executable was not found.",
        "request_storage": "Ask Research Agent in Codex to save PDFs from the connected folders.",
        "processing_error": "Folders remain connected. PDF storage and review processing did not finish. Installation is complete.",
        "request_retry": "Ask Research Agent in Codex to check the saved request status and retry.",
        "receipt": "Storage request: {request_id}",
        "interrupted": "\nSetup was interrupted. Installation is complete.",
        "may_have_started": "If you confirmed the folder list, PDF storage or review may have started.",
        "request_status": "Ask Research Agent in Codex to check the saved request status.",
    },
}


def show_later_instruction(root: Path, language: str = "auto") -> None:
    ui_language = language if language in MESSAGES else resolve_ui_language(language)
    print(MESSAGES[ui_language]["later"])
    print(MESSAGES[ui_language]["later_prompt"])


def run_onboarding(root: Path, language: str = "auto") -> None:
    # Resolve once so setup, folder selection, and terminal reporting agree.
    ui_language = language if language in MESSAGES else resolve_ui_language(language)
    messages = MESSAGES[ui_language]
    # Piped installs and automated runs must never wait for a desktop dialog.
    if not sys.stdin.isatty() or sys.platform != "darwin":
        show_later_instruction(root, ui_language)
        return
    try:
        selected = offer_source_selection(language=ui_language)
    except RuntimeError:
        print(messages["dialog_error"])
        show_later_instruction(root, ui_language)
        return
    if not selected:
        show_later_instruction(root, ui_language)
        return

    print(messages["confirm"])
    if shutil.which("codex"):
        command = [str(root / "resources/skills/research-library/scripts/research-store"),
                   "source-add", "--language", ui_language]
    else:
        # Installation already registered the owned profile. Without the CLI,
        # retain the former install-time registration capability, never sync or
        # call a model outside that profile. The shared helper reports deferred.
        command = [str(root / ".venv/bin/python"), "-I", "-S", "-B",
                   str(root / "scripts/select_sources.py"), "--root", str(root),
                   "--sandbox-home", str(Path.home() / ".codex/research-library-sandbox"),
                   "--installation", "--language", ui_language]
    try:
        result = subprocess.run(
            command,
            check=False,
            # Keep the early retry envelope visible before text storage starts,
            # including if this onboarding process is interrupted afterwards.
            stdout=subprocess.PIPE,
            text=True,
        )
    except OSError:
        print(messages["connection_error"])
        show_later_instruction(root, ui_language)
        return
    try:
        response = json.loads(result.stdout)
        if (
            not isinstance(response, dict)
            or not isinstance(response.get("added"), list)
            or not isinstance(response.get("selected"), list)
            or not isinstance(response.get("cancelled"), bool)
            or not isinstance(response.get("processing"), dict)
        ):
            raise ValueError("Unexpected source-add response")
    except (json.JSONDecodeError, ValueError):
        print(messages["response_error"])
        if result.stderr and result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        show_later_instruction(root, ui_language)
        return
    if response["cancelled"]:
        show_later_instruction(root, ui_language)
        return
    if response.get("registration") != "registered":
        print(messages["response_error"])
        if response.get("error"):
            print(response["error"], file=sys.stderr)
        show_later_instruction(root, ui_language)
        return
    if response["added"]:
        count = len(response["selected"])
        key = "connected_one" if ui_language == "en" and count == 1 else "connected"
        print(messages[key].format(count=count))
    else:
        print(messages["already_connected"])
    processing = response["processing"]
    if processing.get("state") == "submitted":
        request = processing.get("request", {})
        if request.get("state") in {"held", "paused", "stopping"}:
            print(messages["held"])
        elif request.get("state") == "evidence_ready":
            print(messages["ready"])
        else:
            print(messages["submitted"])
    elif processing.get("reason") == "codex_unavailable":
        print(messages["codex_unavailable"])
        print(messages["request_storage"])
    else:
        print(messages["processing_error"])
        print(messages["request_retry"])
        if processing.get("error"):
            print(processing["error"], file=sys.stderr)
    if processing.get("request", {}).get("request_id"):
        print(messages["receipt"].format(request_id=processing["request"]["request_id"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--language", choices=("auto", "ko", "en"), default="auto")
    args = parser.parse_args()
    # Installation already succeeded. Even interruption during language
    # detection must retain that success and avoid entering the folder flow.
    language = args.language if args.language in MESSAGES else "en"
    try:
        language = resolve_ui_language(args.language)
        run_onboarding(args.root, language=language)
    except KeyboardInterrupt:
        messages = MESSAGES[language]
        print(messages["interrupted"])
        print(messages["may_have_started"])
        print(messages["request_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
