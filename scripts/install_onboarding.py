"""Optional, interactive folder connection after installation has succeeded."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

from research_store.picker import offer_source_selection


def show_later_instruction(root: Path) -> None:
    print("폴더는 나중에 연결해도 됩니다. 다음 명령으로 선택창을 열 수 있습니다.")
    print(f"  bash {shlex.quote(str(root / 'add-source.sh'))}")


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

    print("선택창에서 Command(⌘) 키를 누른 채 여러 폴더를 선택할 수 있습니다.")
    try:
        result = subprocess.run(
            [str(root / "research-store"), "source-add"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        print("폴더를 연결하지 못했지만 설치는 완료되었습니다.")
        show_later_instruction(root)
        return
    if result.returncode != 0:
        print("폴더를 연결하지 못했지만 설치는 완료되었습니다.")
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        show_later_instruction(root)
        return
    try:
        response = json.loads(result.stdout)
        if (
            not isinstance(response, dict)
            or not isinstance(response.get("added"), list)
            or not isinstance(response.get("cancelled"), bool)
        ):
            raise ValueError("Unexpected source-add response")
    except (json.JSONDecodeError, ValueError):
        print("폴더 연결 결과를 확인하지 못했습니다. 설치는 완료되었습니다.")
        show_later_instruction(root)
        return
    if response["cancelled"]:
        show_later_instruction(root)
    elif response["added"]:
        print(f"PDF를 찾아볼 폴더 {len(response['added'])}개를 연결했습니다.")
    else:
        print("선택한 폴더는 이미 연결되어 있습니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    try:
        run_onboarding(args.root)
    except KeyboardInterrupt:
        print("\n폴더 연결을 건너뛰었습니다. 설치는 완료되었습니다.")
        show_later_instruction(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
