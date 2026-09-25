#!/bin/sh
# Fresh-install bootstrap. The requested release version is always explicit.
set -eu
umask 077
unset ENV BASH_ENV TAR_OPTIONS SSLKEYLOGFILE QLOGDIR
unset PERL5OPT PERL5LIB PERLLIB
export LC_ALL=C

VERSION=""
DESTINATION="${HOME:?Cannot determine the home directory}/research-agent"
STAGING=""

fail() {
    echo "오류: $*" >&2
    exit 1
}

cleanup() {
    if [ -n "$STAGING" ] && [ -d "$STAGING" ] && [ ! -L "$STAGING" ]; then
        rm -rf -- "$STAGING"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' HUP TERM

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            [ "$#" -ge 2 ] || fail "--version 뒤에 버전 번호가 필요합니다."
            VERSION=$2
            shift 2
            ;;
        --destination)
            [ "$#" -ge 2 ] || fail "--destination 뒤에 설치 경로가 필요합니다."
            DESTINATION=$2
            shift 2
            ;;
        --help)
            echo "Usage: bash install-release.sh --version X.Y.Z [--destination /absolute/path]"
            echo "새 설치만 지원합니다. 기존 설치 폴더나 저장 자료는 덮어쓰지 않습니다."
            exit 0
            ;;
        *) fail "알 수 없는 옵션입니다: $1" ;;
    esac
done
printf '%s\n' "$VERSION" | awk '
    !/^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/ { exit 1 }
    END { if (NR != 1) exit 1 }
' || fail "--version X.Y.Z 형식으로 설치할 버전을 지정하세요."

case "$DESTINATION" in /*) ;; *) fail "설치 경로는 절대 경로여야 합니다." ;; esac
while [ "${DESTINATION%/}" != "$DESTINATION" ]; do DESTINATION=${DESTINATION%/}; done
[ -n "$DESTINATION" ] || fail "루트 폴더에는 설치할 수 없습니다."
[ ! -e "$DESTINATION" ] && [ ! -L "$DESTINATION" ] || \
    fail "설치 경로가 이미 있습니다. 기존 자료를 보호하기 위해 중단합니다: $DESTINATION"
PARENT=$(dirname -- "$DESTINATION")
NAME=$(basename -- "$DESTINATION")
case "$NAME" in .|..) fail "이 설치 경로는 사용할 수 없습니다." ;; esac
[ -d "$PARENT" ] || fail "설치할 상위 폴더가 없습니다: $PARENT"
PARENT=$(CDPATH= cd -- "$PARENT" && pwd -P)
DESTINATION="$PARENT/$NAME"
[ ! -e "$DESTINATION" ] && [ ! -L "$DESTINATION" ] || \
    fail "설치 경로가 이미 있습니다: $DESTINATION"

for required_command in curl tar awk mktemp; do
    command -v "$required_command" >/dev/null 2>&1 || \
        fail "설치에 필요한 도구가 없습니다: $required_command"
done
if command -v shasum >/dev/null 2>&1; then
    CHECKSUM_TOOL=shasum
elif command -v sha256sum >/dev/null 2>&1; then
    CHECKSUM_TOOL=sha256sum
else
    fail "다운로드 검사에 필요한 SHA-256 도구가 없습니다."
fi

STAGING=$(mktemp -d "${TMPDIR:-/tmp}/research-agent-release.XXXXXXXX")
STAGING=$(CDPATH= cd -- "$STAGING" && pwd -P)
ARCHIVE_NAME="research-agent-$VERSION.tar.gz"
ARCHIVE="$STAGING/$ARCHIVE_NAME"
RELEASE_URL="https://github.com/LWH4Data/research-agent/releases/download/v$VERSION"
echo "Research Agent $VERSION 설치 파일을 내려받고 있습니다."
curl -q --proto '=https' --proto-redir '=https' --tlsv1.2 -fLsS \
    "$RELEASE_URL/$ARCHIVE_NAME" -o "$ARCHIVE" || fail "설치 파일을 다운로드하지 못했습니다."
curl -q --proto '=https' --proto-redir '=https' --tlsv1.2 -fLsS \
    "$RELEASE_URL/SHA256SUMS" -o "$STAGING/SHA256SUMS" || fail "설치 파일의 검사 정보를 다운로드하지 못했습니다."

EXPECTED=$(awk -v filename="$ARCHIVE_NAME" '
    $2 == filename {
        count++
        if (NF != 2 || length($1) != 64 || $1 !~ /^[0-9a-f]+$/) invalid = 1
        checksum = $1
    }
    END {
        if (count != 1 || invalid) exit 1
        print checksum
    }
' "$STAGING/SHA256SUMS") || fail "배포본의 SHA-256 정보를 확인할 수 없습니다."
if [ "$CHECKSUM_TOOL" = shasum ]; then
    ACTUAL=$(shasum -a 256 "$ARCHIVE")
else
    ACTUAL=$(sha256sum "$ARCHIVE")
fi
ACTUAL=${ACTUAL%% *}
[ "$ACTUAL" = "$EXPECTED" ] || fail "다운로드한 설치 파일의 SHA-256이 일치하지 않습니다."

# No Python is assumed on a new Mac. Only the release's conservative path
# alphabet and ordinary files/directories are allowed before tar extracts.
tar -tzf "$ARCHIVE" > "$STAGING/members" || fail "설치 파일 목록을 읽을 수 없습니다."
tar -tvzf "$ARCHIVE" > "$STAGING/types" || fail "설치 파일 형식을 읽을 수 없습니다."
awk '
    {
        name = $0
        if (name !~ /^[A-Za-z0-9_.\/-]+$/) exit 1
        sub(/\/$/, "", name)
        if (name != "research-agent" && name !~ /^research-agent\//) exit 1
        parts = split(name, part, "/")
        for (i = 1; i <= parts; i++)
            if (part[i] == "" || part[i] == "." || part[i] == "..") exit 1
        if (seen[name]++) exit 1
    }
    END { if (NR == 0) exit 1 }
' "$STAGING/members" || fail "설치 파일에 허용되지 않는 경로나 중복 파일이 있습니다."
awk '
    !/^[d-][r-][w-][x-][r-][w-][x-][r-][w-][x-] / { exit 1 }
    END { if (NR == 0) exit 1 }
' "$STAGING/types" || fail "설치 파일에 링크 또는 허용되지 않는 파일 형식이 있습니다."
[ "$(awk 'END { print NR }' "$STAGING/members")" = "$(awk 'END { print NR }' "$STAGING/types")" ] || \
    fail "설치 파일 목록이 일치하지 않습니다."
mkdir "$STAGING/unpacked"
tar -xzf "$ARCHIVE" --no-same-owner --no-same-permissions -C "$STAGING/unpacked" || \
    fail "설치 파일의 압축을 풀지 못했습니다."
PAYLOAD="$STAGING/unpacked/research-agent"
[ -d "$PAYLOAD" ] && [ ! -L "$PAYLOAD" ] || fail "배포 폴더를 확인할 수 없습니다."
[ -f "$PAYLOAD/.research-agent-root" ] && \
    [ "$(cat "$PAYLOAD/.research-agent-root")" = research-agent-owned-root-v1 ] || \
    fail "Research Agent 배포본 표시를 확인할 수 없습니다."
[ -f "$PAYLOAD/install.sh" ] || fail "배포본에 설치 실행 파일이 없습니다."

# mkdir is the final exclusive reservation: never merge into an existing tree,
# even if it appeared while downloading. Keep an incomplete installation for
# diagnosis rather than deleting files after native setup has started.
mkdir "$DESTINATION" || fail "설치 경로가 생겼거나 만들 수 없습니다: $DESTINATION"
cp -R "$PAYLOAD/." "$DESTINATION/" || \
    fail "설치 파일을 복사하지 못했습니다. 확인을 위해 폴더를 보존했습니다: $DESTINATION"
echo "검증을 마쳤습니다. 다음 위치에 설치합니다: $DESTINATION"
if ! bash "$DESTINATION/install.sh"; then
    fail "설치를 완료하지 못했습니다. 확인을 위해 설치 폴더를 보존했습니다: $DESTINATION"
fi
