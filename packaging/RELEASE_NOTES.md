Research Agent v0.4.2는 설치 후 안내창과 폴더 연결창에 한국어·영어 지원을
추가한 패치 릴리스입니다.

## 설치

[v0.4.2 README의 설치 안내](https://github.com/LWH4Data/research-agent/tree/v0.4.2#readme)를
따라 터미널에서 설치 명령을 실행하세요. 이 버전은 사전 출시 버전이며,
현재 사용자 지원 대상은 macOS입니다.

기존 설치 폴더가 있으면 덮어쓰지 않고 중단합니다. 새 설치만 지원하며,
자동 업데이트와 기존 자료를 보존하는 업데이트 절차는 아직 제공하지
않습니다. 새 버전을 설치하려고 기존 설치본이나 연구 자료를 삭제하지 마세요.

## 이번 버전의 변경

- 설치 완료 안내, 폴더 선택·추가·확인, 빈 목록, 선택 개수와 오류 문구가
  macOS 언어 설정에 따라 한국어 또는 영어로 표시됩니다.
- Codex에서 “영어로 PDF 폴더 연결창을 열어줘”라고 요청하면 영어로 열 수
  있습니다. 실행기의 `--language` 옵션은 `auto`, `ko`, `en`을 받으며,
  `source-add --language en`처럼 지정할 수 있습니다. 기본값은 `auto`입니다.
- 폴더 경로, 체크 선택, 중복 제외와 취소 동작은 유지합니다. 선택한 목록을
  확인하면 해당 PDF 저장과 필요한 페이지의 시각 검토를 시작합니다.
- 설치 터미널 출력은 주로 한국어입니다. macOS가 제공하는 사이드바·검색 등은
  시스템 언어를 따르며, 안내창의 언어 선택은 시스템 설정을 바꾸지 않습니다.

[웹 사용 가이드](https://lwh4data.github.io/research-agent/?lang=ko)는
제품 배포본과 별도로 GitHub Pages에 게시합니다. 배포본에는 README와 영문
사용자 안내를 포함하며 웹 화면과 캡처는 웹 가이드에서 확인합니다.

## 배포 파일

- `research-agent-0.4.2.tar.gz`: 개발 하니스·테스트·개인 자료를 제외한 제품 묶음
- `install-release.sh`: 내려받기와 새 설치를 진행하는 실행 파일
- `SHA256SUMS`: 다운로드 파일 무결성 확인 값

GitHub가 별도로 제공하는 **Source code**는 개발 소스입니다. 일반 사용자는
README의 설치 명령을 사용하세요.

자동 검사는 모델을 호출하지 않으며, 실제 Codex 권한·알림·모델 호출은
사용자 환경에 따라 달라질 수 있습니다. 영문 폴더 선택·목록 화면의 실제
사용자 환경 캡처는 아직 준비 중이며, 모든 PDF의 시각 해석 정확도를 검증한
릴리스라는 의미는 아닙니다.

---

Research Agent v0.4.2 is a patch release that adds Korean and English support to
post-installation and folder connection dialogs.

## Installation

Follow the [v0.4.2 README installation instructions](https://github.com/LWH4Data/research-agent/tree/v0.4.2#readme).
This is a prerelease, and macOS is the supported user platform.

This release supports fresh installation only and refuses to overwrite an
existing destination. Automatic updates and an update procedure that preserves
an existing library are not yet provided. Do not delete your installation or
research data to install the new release.

## Changes in this version

- Setup messages, folder selection and confirmation, empty lists, selection
  counts, and errors use Korean or English based on macOS language preferences.
- Ask Research Agent to “Open the PDF folder connection window in English” to
  choose English explicitly. The launcher's `--language` option accepts `auto`,
  `ko`, or `en`, for example `source-add --language en`; `auto` is the default.
- Folder paths, checked selections, deduplication, and cancellation behavior
  are preserved. Confirming the selected list starts PDF storage and visual
  review of the pages that need it.
- The installer’s Terminal output remains mostly Korean. System-owned controls
  such as the sidebar and search field follow the macOS language setting.
  Choosing a dialog language does not change the system language.

The [web guide](https://lwh4data.github.io/research-agent/?lang=en) is published
separately on GitHub Pages. The product bundle includes the README and English
user guide; web pages and screenshots are available on the web guide.

## Release assets

- `research-agent-0.4.2.tar.gz`: product bundle without development harnesses,
  tests, or personal research data
- `install-release.sh`: downloads and installs a fresh copy
- `SHA256SUMS`: integrity checks for the downloadable files

GitHub’s separate **Source code** download is the development source. Use the
README installation command for the product release.

Automated checks do not call subscription models. Actual Codex permissions,
notifications, and model calls depend on the environment. Real user-environment
captures of the English folder picker and selection list are still being
prepared; this release does not establish the accuracy of all PDF visual
interpretation.
