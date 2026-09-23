#!/bin/sh
set -eu

case " $* " in
    *" --help "*|*" -h "*)
        echo '사용법: bash uninstall.sh [--keep-files] [--yes]'
        echo '기본값: Codex 등록 해제 및 설치 폴더 전체를 휴지통으로 이동'
        echo '--keep-files: Codex 등록만 해제하고 설치 폴더와 자료 보관'
        echo '--yes: 제거 확인 생략'
        exit 0
        ;;
esac
for argument in "$@"; do
    case "$argument" in
        --keep-files|--yes) ;;
        *) echo "알 수 없는 옵션: $argument" >&2; exit 2 ;;
    esac
done
[ ! -L "$0" ] || { echo '오류: 실제 설치 폴더의 uninstall.sh를 실행하세요.' >&2; exit 1; }
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

exec "$PYTHON" -I -B "$ROOT/scripts/uninstall_project.py" \
    --root "$ROOT" --home "$HOME" "$@"
