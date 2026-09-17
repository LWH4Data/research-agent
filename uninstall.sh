#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
: "${HOME:?사용자 홈 경로를 확인할 수 없습니다}"

if [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON=$(command -v python3)
    "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || {
        echo "오류: 제거에는 Python 3.11 이상이 필요합니다. install.sh를 다시 실행하세요." >&2
        exit 1
    }
else
    echo "오류: 개인 등록을 안전하게 제거할 Python을 찾을 수 없습니다." >&2
    exit 1
fi

"$PYTHON" -I -B "$ROOT/scripts/personal_registration.py" \
    uninstall --root "$ROOT" --home "$HOME"

echo
echo "Research Library 개인 등록을 제거했습니다."
echo "원본 연구 파일과 research-agent 안의 저장 자료는 그대로 남아 있습니다."
echo "완전히 제거하려면 이제 이 폴더만 휴지통으로 옮기세요:"
echo "$ROOT"
