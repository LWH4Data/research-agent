#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
PYTHON="$ROOT/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "설치가 필요합니다: bash \"$ROOT/install.sh\"" >&2
    exit 1
fi

export PYTHONDONTWRITEBYTECODE=1
exec "$PYTHON" "$ROOT/scripts/demo_progress.py" "$@"
