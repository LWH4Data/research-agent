"""Optional, interactive folder connection after installation has succeeded."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from research_store.picker import offer_source_selection


def show_later_instruction(root: Path) -> None:
    print("폴더는 나중에 연결해도 됩니다. Codex를 열고 Research Agent에 요청하세요.")
    print("  @Research Agent PDF 폴더 연결창 다시 열어줘.")


def run_onboarding(root: Path) -> None:
    # Piped installs and automated runs must never wait for a desktop dialog.
    if not sys.stdin.isatty() or sys.platform != "darwin":
        show_later_instruction(root)
        return
    try:
        selected = offer_source_selection()
    except RuntimeError:
        print("안내창을 열지 못했지만 설치는 완료되었습니다.")
        show_later_instruction(root)
        return
    if not selected:
        show_later_instruction(root)
        return

    print("폴더를 추가하고 목록을 확인하면 PDF 저장과 시각 검토를 시작합니다.")
    if shutil.which("codex"):
        command = [str(root / "resources/skills/research-library/scripts/research-store"), "source-add"]
    else:
        # Installation already registered the owned profile. Without the CLI,
        # retain the former install-time registration capability, never sync or
        # call a model outside that profile. The shared helper reports deferred.
        command = [str(root / ".venv/bin/python"), "-I", "-S", "-B",
                   str(root / "scripts/select_sources.py"), "--root", str(root),
                   "--sandbox-home", str(Path.home() / ".codex/research-library-sandbox"),
                   "--installation"]
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
        print("폴더를 연결하지 못했지만 설치는 완료되었습니다.")
        show_later_instruction(root)
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
        print("폴더 연결 결과를 확인하지 못했습니다. 설치는 완료되었습니다.")
        if result.stderr and result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        show_later_instruction(root)
        return
    if response["cancelled"]:
        show_later_instruction(root)
        return
    if response.get("registration") != "registered":
        print("폴더 연결 결과를 확인하지 못했습니다. 설치는 완료되었습니다.")
        if response.get("error"):
            print(response["error"], file=sys.stderr)
        show_later_instruction(root)
        return
    if response["added"]:
        print(f"PDF를 찾아볼 폴더 {len(response['selected'])}개를 연결했습니다.")
    else:
        print("선택한 폴더는 이미 연결되어 있습니다.")
    processing = response["processing"]
    if processing.get("state") == "submitted":
        request = processing.get("request", {})
        if request.get("state") in {"held", "paused", "stopping"}:
            print("PDF 저장 처리를 마쳤습니다. 시각 검토는 사용자가 중지한 상태를 유지합니다.")
        elif request.get("state") == "evidence_ready":
            print("선택한 폴더의 PDF 저장·검토 처리를 마쳤습니다.")
        else:
            print("PDF 저장 처리를 마쳤고 시각 검토를 접수했습니다. 저장된 상태에서 진행을 확인할 수 있습니다.")
    elif processing.get("reason") == "codex_unavailable":
        print("폴더 연결은 유지됩니다. Codex 실행 파일을 찾지 못해 PDF 저장과 검토는 아직 시작하지 않았습니다.")
        print("Codex에서 Research Agent에 연결한 폴더의 PDF 저장을 요청하세요.")
    else:
        print("폴더 연결은 유지됩니다. PDF 저장·검토 처리를 마치지 못했습니다. 설치는 완료되었습니다.")
        print("Codex에서 Research Agent에 저장된 접수 상태 확인과 재시도를 요청하세요.")
        if processing.get("error"):
            print(processing["error"], file=sys.stderr)
    if processing.get("request", {}).get("request_id"):
        print(f"저장 접수: {processing['request']['request_id']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    try:
        run_onboarding(args.root)
    except KeyboardInterrupt:
        print("\n안내를 중단했습니다. 설치는 완료되었습니다.")
        print("폴더 목록을 확인했다면 PDF 저장이나 검토가 시작되었을 수 있습니다.")
        print("Codex에서 Research Agent에 저장된 접수 상태 확인을 요청하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
