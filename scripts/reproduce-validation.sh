#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
PYTHON="$ROOT/.venv/bin/python"
MODE=${1:-core}

if [ ! -x "$PYTHON" ]; then
    echo "오류: 먼저 프로젝트 설치를 완료해 주세요: bash \"$ROOT/install.sh\"" >&2
    exit 1
fi

cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1

run_core() {
    echo "Research Agent 핵심 안전성 검증을 시작합니다."
    echo "- 줄바꿈 보존"
    echo "- 대화 저장·수정·삭제 중단 복구"
    echo "- PDF 저장·시각 검토 강제 종료 복구"
    echo "- 진행률 이벤트와 영구 체크포인트"
    echo "- 실제 프로세스 동시 실행"
    echo "- 파일 작업 장애 주입"
    echo "- SQLite 작업 저널"
    echo "- 설치 등록 경계"
    echo

    "$PYTHON" -m unittest -v \
        tests.test_conversation_management.ConversationManagementTests.test_crlf_and_lone_cr_round_trip_in_all_editable_fields_and_transcript \
        tests.test_conversation_recovery \
        tests.test_document_recovery \
        tests.test_safety_failures \
        tests.test_state_journal \
        tests.test_sync_concurrency \
        tests.test_personal_registration

    # test_progress imports the shared PDF fixture as a discovery-time module.
    "$PYTHON" -m unittest discover -s tests -p 'test_progress.py' -v
}

run_full() {
    echo "Research Agent 전체 자동 테스트를 시작합니다."
    echo "실제 권한 프로필 테스트는 별도 permission 모드에서 실행합니다."
    echo
    "$PYTHON" -m unittest discover -s tests -v
}

run_permission() {
    if command -v codex >/dev/null 2>&1; then
        :
    elif [ -x /Applications/ChatGPT.app/Contents/Resources/codex ]; then
        PATH="/Applications/ChatGPT.app/Contents/Resources:$PATH"
        export PATH
    else
        echo "오류: Codex CLI를 찾을 수 없습니다." >&2
        exit 1
    fi

    echo "실제 Research Agent 권한 프로필을 검증합니다."
    echo "프로젝트 저장 영역 쓰기는 허용하고, 원본과 실행 코드 쓰기는 차단해야 합니다."
    echo "이 모드는 Codex 내부 터미널이 아닌 일반 macOS 터미널에서 실행해 주세요."
    echo
    RESEARCH_AGENT_RUN_SANDBOX_TEST=1 \
        "$PYTHON" -m unittest -v tests.test_permission_profile_integration
}

case "$MODE" in
    core)
        run_core
        ;;
    full)
        run_full
        ;;
    permission)
        run_permission
        ;;
    *)
        echo "사용법: $0 [core|full|permission]" >&2
        exit 2
        ;;
esac

echo
echo "검증이 완료되었습니다."
