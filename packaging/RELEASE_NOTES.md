Research Agent v0.4.0은 폴더 선택과 PDF 저장을 하나의 흐름으로 연결합니다.
Codex에서 연결창을 열거나 다시 열고, 여러 위치의 폴더를 목록에 모아 확인하면
선택한 폴더의 텍스트 저장과 필요한 페이지의 시각 검토가 이어집니다.

## 설치

[v0.4.0 README의 설치 안내](https://github.com/LWH4Data/research-agent/tree/v0.4.0#readme)를
따라 터미널에서 설치 명령을 실행하세요. 설치 뒤에는 Codex에 연결창 열기를
요청할 수 있으며, 다시 설치하거나 터미널 명령을 재입력할 필요가 없습니다.

기존 설치 폴더가 있으면 덮어쓰지 않고 중단합니다. 이 버전은 새 설치만
지원하며, 자동 업데이트와 기존 자료를 보존하는 업데이트 절차는 아직
제공하지 않습니다. 새 버전을 설치하려고 기존 설치본이나 연구 자료를
삭제하지 마세요.

## 이번 버전의 변경

- **연결할 폴더** 창에서 **폴더 추가하기**, ⌘ 다중 선택, **목록에 추가**,
  체크 확인과 **폴더 더 추가하기**, **연결하고 PDF 저장하기** 순서로 연결합니다.
- 최종 확인한 폴더나 직접 지정한 경로만 연결하고 PDF 텍스트를 저장합니다.
  이미 연결된 위치를 다시 선택해도 이번 범위에 포함하며, 관련 없는 위치는
  함께 처리하지 않습니다.
- 텍스트 저장 후 필요한 페이지의 시각 검토를 접수합니다. 본문은 검토 중에도
  검색할 수 있으며, 저장·검토 진행·실패 결과를 구분해 안내합니다.
- PDF별 또는 자료실 전체 시각 검토를 일시 정지하고 재개할 수 있습니다.
  전체 일시 정지는 이후 저장과 재실행에도 유지합니다. 시간·페이지 안내는
  자동 중단 없이 알리며, 중단 여부는 사용자가 결정합니다.
- 폴더 선택 취소는 설치와 기존 연결을 유지합니다. 연결 후 저장이 실패하거나
  설치 중 Codex 실행 파일을 찾지 못하면 완료된 연결을 유지하고 이어서
  저장하는 방법을 안내합니다.
- 새 흐름과 최신 캡처를 반영한 한국어·영어 사용자 안내를 제공합니다.

여러 위치의 PDF와 대화 첨부 PDF 저장, PDF·저장 대화 통합 검색,
대화 기록 저장·조회·수정·삭제를 계속 지원합니다. 원본 PDF는 수정·이동·삭제하지
않으며, 연결한 위치의 후속 갱신은 새로 추가되거나 변경된 PDF만 처리합니다.
시각 검토는 필요한 페이지를 대상으로 하며 모든 PDF 페이지를 확인하는 것은
아닙니다. macOS 알림은 Codex 대화에 새 메시지를 자동으로 추가하지 않습니다.

## 배포 파일

- `research-agent-0.4.0.tar.gz`: 개발 하니스·테스트·개인 자료를 제외한 제품 묶음
- `install-release.sh`: 내려받기와 새 설치를 진행하는 실행 파일
- `SHA256SUMS`: 다운로드 파일 무결성 확인 값

GitHub가 별도로 제공하는 **Source code**는 개발 소스입니다. 일반 사용자는
README의 설치 명령을 사용하세요.

현재 사용자 지원 대상은 macOS입니다. 실제 Codex 권한과 알림, 모델 호출은
사용자 환경에 따라 달라질 수 있습니다. 자동 검사는 모델을 호출하지 않으며
PDF 시각 해석의 정확도 전체를 보증하지 않습니다.

---

Research Agent v0.4.0 connects folder selection and PDF storage in one workflow.
Open or reopen the connection window from Codex, collect folders from several
locations, and confirm the list to save their text and review the pages that
need image inspection.

## Installation

Follow the [v0.4.0 README installation instructions](https://github.com/LWH4Data/research-agent/tree/v0.4.0#readme).
After installation, ask Codex to open the connection window; you do not need
to reinstall or enter another Terminal command.

This release supports fresh installation only and refuses to overwrite an
existing destination. Automatic updates and an update procedure that preserves
an existing library are not yet provided. Do not delete your installation or
research data to install the new release.

## Changes in this version

- Use **연결할 폴더** (Folders to connect), **폴더 추가하기** (Add folders),
  Command-click multi-selection, **목록에 추가** (Add to list), checkboxes and
  **폴더 더 추가하기** (Add more folders), then **연결하고 PDF 저장하기**
  (Connect and save PDFs).
- Connect and save PDF text only from confirmed folders or directly supplied
  paths. Reselecting a connected location includes it in this request without
  processing unrelated locations.
- Text storage hands off to visual review of the pages that need it. Text is
  searchable while review continues, with storage, review progress, and failures
  reported separately.
- Pause and resume visual review for a PDF or the whole library. A library-wide
  pause persists across later saves and restarts. Time and page guidance warns
  without stopping automatically; the user decides when to stop.
- Canceling folder selection keeps the installation and existing connections.
  Storage failure, or a missing Codex executable during installation, keeps
  completed connections and explains how to continue saving.
- Korean and English guides cover the new workflow with updated screenshots.

Read-only folder sources, PDF attachment imports, combined PDF/conversation
retrieval, and saved conversation management remain available. Original PDFs
are not modified, moved, or deleted. Later update requests process new or changed
PDFs. Visual review does not inspect every PDF page, and macOS notifications do
not automatically post new messages to Codex conversations.

## Release assets

- `research-agent-0.4.0.tar.gz`: product bundle without development harnesses,
  tests, or personal research data
- `install-release.sh`: downloads and installs a fresh copy
- `SHA256SUMS`: integrity checks for the downloadable files

GitHub's separate **Source code** download is the development source. Use the
README installation command for the product release.

macOS is the supported user platform. Actual Codex permissions, notifications,
and model calls depend on the environment. Automated checks do not call
subscription models or establish the accuracy of all PDF visual interpretation.
