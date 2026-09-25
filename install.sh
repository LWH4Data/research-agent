#!/bin/sh
set -eu

umask 077
unset ENV BASH_ENV PYTHONPATH PYTHONHOME PYTHONPYCACHEPREFIX
unset PYTHONINSPECT PYTHONSTARTUP PYTHON_HISTORY
unset SSLKEYLOGFILE QLOGDIR TAR_OPTIONS
unset PERL5OPT PERL5LIB PERLLIB
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
: "${HOME:?사용자 홈 경로를 확인할 수 없습니다}"
MARKER="$ROOT/.research-agent-root"
UV_VERSION="0.12.15"
TOOLS="$ROOT/.tools"
PYTHON_DIR="$ROOT/.python"
VENV="$ROOT/.venv"
RUNTIME_ROOT="$ROOT/.research-store"
CONFIG="$RUNTIME_ROOT/config.toml"
LEGACY_CONFIG="$ROOT/config.toml"
BOOTSTRAP=""
FIRST_SETUP=0

fail() {
    echo "오류: $*" >&2
    exit 1
}

cleanup() {
    if [ -n "$BOOTSTRAP" ] && [ -d "$BOOTSTRAP" ] && [ ! -L "$BOOTSTRAP" ]; then
        rm -rf -- "$BOOTSTRAP"
    fi
}
trap cleanup EXIT HUP INT TERM

if [ ! -f "$MARKER" ] || [ -L "$MARKER" ] || \
   [ "$(cat "$MARKER")" != "research-agent-owned-root-v1" ]; then
    fail "research-agent 프로젝트 루트를 확인할 수 없습니다."
fi

if [ ! -e "$CONFIG" ] && [ ! -e "$LEGACY_CONFIG" ]; then
    FIRST_SETUP=1
fi

command -v realpath >/dev/null 2>&1 || fail "설치 경로 검사에 필요한 realpath가 없습니다."

safe_directory() {
    managed_path=$1
    managed_label=$2
    [ ! -L "$managed_path" ] || fail "$managed_label 경로가 링크입니다: $managed_path"
    if [ -e "$managed_path" ] && [ ! -d "$managed_path" ]; then
        fail "$managed_label 경로가 폴더가 아닙니다: $managed_path"
    fi
    mkdir -p -- "$managed_path"
    physical_path=$(CDPATH= cd -- "$managed_path" && pwd -P)
    [ "$physical_path" = "$managed_path" ] || \
        fail "$managed_label 경로가 프로젝트 밖을 가리킵니다: $managed_path"
}

validate_tree() {
    managed_path=$1
    managed_label=$2
    [ -e "$managed_path" ] || return 0
    safe_directory "$managed_path" "$managed_label"

    linked_file=$(find "$managed_path" -type f -links +1 -print -quit)
    [ -z "$linked_file" ] || \
        fail "$managed_label 안에 하드 링크가 있습니다: $linked_file"

    if ! find "$managed_path" -type l -exec sh -c '
        tools_root=$1
        python_root=$2
        venv_root=$3
        shift 3
        for link_path do
            resolved_path=$(realpath "$link_path") || exit 1
            case "$resolved_path" in
                "$tools_root"|"$tools_root"/*|"$python_root"|"$python_root"/*|"$venv_root"|"$venv_root"/*) ;;
                *) exit 1 ;;
            esac
        done
    ' sh "$TOOLS" "$PYTHON_DIR" "$VENV" {} +; then
        fail "$managed_label 안의 링크가 관리 경로 밖을 가리킵니다."
    fi
}

validate_regular_target() {
    managed_file=$1
    managed_label=$2
    [ ! -L "$managed_file" ] || fail "$managed_label 파일이 링크입니다: $managed_file"
    if [ -e "$managed_file" ]; then
        [ -f "$managed_file" ] || fail "$managed_label 경로가 일반 파일이 아닙니다."
        if stat -f '%l' "$managed_file" >/dev/null 2>&1; then
            link_count=$(stat -f '%l' "$managed_file")
        else
            link_count=$(stat -c '%h' "$managed_file")
        fi
        [ "$link_count" = "1" ] || fail "$managed_label 파일이 하드 링크입니다."
    fi
}

safe_directory "$RUNTIME_ROOT" "저장소 데이터"
if [ -e "$LEGACY_CONFIG" ] || [ -L "$LEGACY_CONFIG" ]; then
    validate_regular_target "$LEGACY_CONFIG" "이전 설정"
fi
validate_regular_target "$CONFIG" "설정"
if [ -e "$LEGACY_CONFIG" ] && [ -e "$CONFIG" ]; then
    fail "설정 파일이 이전 위치와 새 위치에 모두 있습니다: $LEGACY_CONFIG, $CONFIG"
fi
if [ -e "$LEGACY_CONFIG" ]; then
    mv -- "$LEGACY_CONFIG" "$CONFIG"
    echo "기존 설정을 안전한 데이터 폴더로 옮겼습니다: $CONFIG"
fi

safe_directory "$TOOLS" "도구"
safe_directory "$PYTHON_DIR" "Python"
validate_tree "$TOOLS" "도구"
validate_tree "$PYTHON_DIR" "Python"
if [ -L "$VENV" ]; then
    fail "가상 환경 경로가 링크입니다: $VENV"
fi
if [ -e "$VENV" ]; then
    validate_tree "$VENV" "가상 환경"
fi

system_name=$(uname -s)
machine_name=$(uname -m)
case "$system_name:$machine_name" in
    Darwin:arm64|Darwin:aarch64)
        target="aarch64-apple-darwin"
        checksum="dc304b9ed1b24174572290fba60ac3f6fe63c73a671f0439e62a91375841964d"
        ;;
    Darwin:x86_64)
        target="x86_64-apple-darwin"
        checksum="e9ca61775532368fe518ab03e7a354c7ecab8ccb3c7d941c775fcc4a362b801b"
        ;;
    Linux:aarch64|Linux:arm64)
        if ldd --version 2>&1 | grep -qi musl; then
            target="aarch64-unknown-linux-musl"
            checksum="93b801abb146e6431fb0434346a0162e65d3f0d1cd7360144d04c43488fd7f7d"
        else
            target="aarch64-unknown-linux-gnu"
            checksum="0e9a3499b0587d449c9ff684c0160da607826e4af1cee220bc87f378702d3e08"
        fi
        ;;
    Linux:x86_64|Linux:amd64)
        if ldd --version 2>&1 | grep -qi musl; then
            target="x86_64-unknown-linux-musl"
            checksum="999c0c3da986953e508985c3932d283d2c62eb167b4f8d81e79f565e34104959"
        else
            target="x86_64-unknown-linux-gnu"
            checksum="f97935763c04be3e692460a7aaeaaab8fc3b78fcf8b389da820b38ae7423a638"
        fi
        ;;
    *) fail "지원하지 않는 운영체제 또는 CPU입니다: $system_name $machine_name" ;;
esac

command -v curl >/dev/null 2>&1 || fail "다운로드에 필요한 curl을 찾을 수 없습니다."
command -v tar >/dev/null 2>&1 || fail "압축 해제에 필요한 tar를 찾을 수 없습니다."
BOOTSTRAP=$(mktemp -d "$ROOT/.research-install.XXXXXXXX")
[ "$(CDPATH= cd -- "$BOOTSTRAP" && pwd -P)" = "$BOOTSTRAP" ] || \
    fail "임시 설치 폴더가 프로젝트 밖을 가리킵니다."
INSTALL_TMP="$BOOTSTRAP/tmp"
INSTALL_HOME="$BOOTSTRAP/home"
mkdir -p -- "$INSTALL_TMP" "$INSTALL_HOME"
export TMPDIR="$INSTALL_TMP"
export TMP="$INSTALL_TMP"
export TEMP="$INSTALL_TMP"

archive_name="uv-$target.tar.gz"
archive="$BOOTSTRAP/$archive_name"
curl -q --proto '=https' --tlsv1.2 -LsSf \
    "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$archive_name" \
    -o "$archive"
if checksum_tool=$(command -v shasum 2>/dev/null); then
    checksum_output=$(env -i \
        HOME="$INSTALL_HOME" \
        PATH="$PATH" \
        TMPDIR="$INSTALL_TMP" \
        TMP="$INSTALL_TMP" \
        TEMP="$INSTALL_TMP" \
        "$checksum_tool" -a 256 "$archive")
elif checksum_tool=$(command -v sha256sum 2>/dev/null); then
    checksum_output=$(env -i \
        HOME="$INSTALL_HOME" \
        PATH="$PATH" \
        TMPDIR="$INSTALL_TMP" \
        TMP="$INSTALL_TMP" \
        TEMP="$INSTALL_TMP" \
        "$checksum_tool" "$archive")
else
    fail "uv 무결성 검사에 필요한 SHA-256 도구가 없습니다."
fi
actual_checksum=${checksum_output%% *}
[ "$actual_checksum" = "$checksum" ] || fail "다운로드한 uv의 SHA-256이 일치하지 않습니다."

tar -xzf "$archive" -C "$BOOTSTRAP"
downloaded_uv="$BOOTSTRAP/uv-$target/uv"
[ -f "$downloaded_uv" ] && [ ! -L "$downloaded_uv" ] || \
    fail "검증된 uv 실행 파일을 찾을 수 없습니다."

UV="$TOOLS/uv"
validate_regular_target "$UV" "uv"
temporary_uv=$(mktemp "$TOOLS/.uv.XXXXXXXX")
cat "$downloaded_uv" > "$temporary_uv"
chmod 700 "$temporary_uv"
mv -f -- "$temporary_uv" "$UV"
validate_regular_target "$UV" "uv"

env -i \
    HOME="$INSTALL_HOME" \
    PATH="$PATH" \
    LANG="${LANG-}" \
    LC_ALL="${LC_ALL-}" \
    HTTP_PROXY="${HTTP_PROXY-}" \
    HTTPS_PROXY="${HTTPS_PROXY-}" \
    ALL_PROXY="${ALL_PROXY-}" \
    NO_PROXY="${NO_PROXY-}" \
    http_proxy="${http_proxy-}" \
    https_proxy="${https_proxy-}" \
    all_proxy="${all_proxy-}" \
    no_proxy="${no_proxy-}" \
    SSL_CERT_FILE="${SSL_CERT_FILE-}" \
    SSL_CERT_DIR="${SSL_CERT_DIR-}" \
    TMPDIR="$INSTALL_TMP" \
    TMP="$INSTALL_TMP" \
    TEMP="$INSTALL_TMP" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    UV_CACHE_DIR="$BOOTSTRAP/cache" \
    UV_PYTHON_INSTALL_DIR="$PYTHON_DIR" \
    UV_PYTHON_CACHE_DIR="$BOOTSTRAP/python-cache" \
    UV_PROJECT_ENVIRONMENT="$VENV" \
    UV_LINK_MODE="copy" \
    UV_NO_CONFIG=1 \
    "$UV" sync --project "$ROOT" --locked --managed-python --python 3.12

validate_tree "$TOOLS" "도구"
validate_tree "$PYTHON_DIR" "Python"
validate_tree "$VENV" "가상 환경"
interpreter=$(env -i \
    HOME="$INSTALL_HOME" \
    PATH="$PATH" \
    TMPDIR="$INSTALL_TMP" \
    TMP="$INSTALL_TMP" \
    TEMP="$INSTALL_TMP" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONNOUSERSITE=1 \
    "$VENV/bin/python" -I -B -c \
    'from pathlib import Path; import sys; print(Path(sys.executable).resolve())')
case "$interpreter" in
    "$ROOT"/*) ;;
    *) fail "가상 환경이 프로젝트 밖의 Python을 사용합니다: $interpreter" ;;
esac

"$ROOT/research-store" init >/dev/null
"$VENV/bin/python" -I -B "$ROOT/scripts/personal_registration.py" \
    install --root "$ROOT" --home "$HOME"

echo
echo "research-agent 설치가 완료되었습니다."
echo "원본에는 파일을 만들거나 수정하지 않습니다."
echo "개인 스킬과 전용 에이전트 등록을 완료했습니다."

if [ "$FIRST_SETUP" = "1" ]; then
    if ! "$VENV/bin/python" -I -B "$ROOT/scripts/install_onboarding.py" --root "$ROOT"; then
        echo "폴더 연결을 마치지 못했지만 설치는 완료되었습니다."
        echo "나중에 아래의 위치 추가 명령으로 폴더를 연결할 수 있습니다."
    fi
fi

echo
"$ROOT/research-store" source-list --plain
echo
echo "열려 있던 Codex 앱·CLI·IDE를 완전히 종료한 뒤 다시 여세요."
echo "그다음 @ 메뉴에서 Research Agent를 선택하세요."
echo "CLI·IDE에서는 /skills 또는 \$research-library를 사용하세요."
echo "위치 추가: bash $ROOT/add-source.sh"
