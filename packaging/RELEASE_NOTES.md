Research Agent v0.4.1은 웹 사용 가이드의 설명과 실제 화면을 보완한 패치 릴리스입니다.
제품 실행 동작은 v0.4.0과 같으며, 폴더 갱신과 시각 검토 일시 정지·재개는
이미 제공하던 기능입니다.

## 설치

[v0.4.1 README의 설치 안내](https://github.com/LWH4Data/research-agent/tree/v0.4.1#readme)를
따라 터미널에서 설치 명령을 실행하세요. 이 버전은 사전 출시 버전이며,
현재 사용자 지원 대상은 macOS입니다.

기존 설치 폴더가 있으면 덮어쓰지 않고 중단합니다. 새 설치만 지원하며,
자동 업데이트와 기존 자료를 보존하는 업데이트 절차는 아직 제공하지
않습니다. 새 버전을 설치하려고 기존 설치본이나 연구 자료를 삭제하지 마세요.

## 이번 버전의 변경

- **시작하기 → 폴더 선택**에 최신 빈 목록 화면과 여러 폴더 선택 화면을
  반영했습니다. **목록에 추가** 버튼까지 보이는 전체 화면으로 절차를
  확인할 수 있습니다.
- 연결한 폴더에서 새로 추가되거나 변경된 PDF만 정리하는 요청과 실제
  저장 결과를 가이드에 추가했습니다. 새로 저장한 문서, 변경 없이 유지한
  문서와 시각 검토 진행 상태를 구분해 설명합니다.
- PDF 저장·검토 시작, 특정 문서의 일시 정지, 남은 검토 재개와 결과 확인을
  실제 요청·결과 화면으로 안내합니다. 완료된 본문과 검토 결과를 유지한
  상태에서 처리하는 흐름을 확인할 수 있습니다.
- 시각 검토는 선정된 페이지를 대상으로 하며, 진행·대기와 추가 확인 필요를
  구분합니다. 일부 페이지의 검토 완료를 문서 전체 확인으로 설명하지
  않도록 한국어·영어 문구를 보완했습니다.

[웹 사용 가이드](https://lwh4data.github.io/research-agent/?lang=ko)는
제품 배포본과 별도로 GitHub Pages에 게시합니다. 배포본에는 README와 영문
사용자 안내를 포함하며 웹 화면과 캡처는 웹 가이드에서 확인합니다.

자료실 전체의 시각 검토 일시 정지는 이후 저장과 재실행에도 유지하며,
전체 재개 요청으로 해제합니다. 시간·페이지 안내는 자동으로 검토를
중단하지 않습니다. 원본 PDF는 수정·이동·삭제하지 않습니다.

## 배포 파일

- `research-agent-0.4.1.tar.gz`: 개발 하니스·테스트·개인 자료를 제외한 제품 묶음
- `install-release.sh`: 내려받기와 새 설치를 진행하는 실행 파일
- `SHA256SUMS`: 다운로드 파일 무결성 확인 값

GitHub가 별도로 제공하는 **Source code**는 개발 소스입니다. 일반 사용자는
README의 설치 명령을 사용하세요.

자동 검사는 모델을 호출하지 않으며, 실제 Codex 권한·알림·모델 호출은
사용자 환경에 따라 달라질 수 있습니다. 가이드의 예시는 해당 요청에서
확인한 결과이며 모든 PDF의 시각 해석 정확도를 보증하지 않습니다.

---

Research Agent v0.4.1 is a patch release that improves the web guide's
instructions and actual screenshots. Product runtime behavior is unchanged
from v0.4.0; folder updates and visual review pause/resume were already available.

## Installation

Follow the [v0.4.1 README installation instructions](https://github.com/LWH4Data/research-agent/tree/v0.4.1#readme).
This is a prerelease, and macOS is the supported user platform.

This release supports fresh installation only and refuses to overwrite an
existing destination. Automatic updates and an update procedure that preserves
an existing library are not yet provided. Do not delete your installation or
research data to install the new release.

## Changes in this version

- Updated **Getting started → Select folders** with the latest empty draft and
  multiple-folder selection screenshots. The full picker includes the
  **목록에 추가** (Add to list) button.
- Added the actual request and result for processing new or changed PDFs in a
  connected folder. The guide distinguishes newly saved documents, unchanged
  documents, and visual review progress.
- Added actual request/result screenshots for saving PDFs and starting review,
  pausing selected documents, resuming remaining review, and checking results.
  The walkthrough shows that stored text and completed review results are kept.
- Clarified Korean and English explanations of selected review pages,
  progress/waiting, and pages that require further checking. Completion of
  selected pages is not described as verification of the entire document.

The [web guide](https://lwh4data.github.io/research-agent/?lang=en) is published
separately on GitHub Pages. The product bundle includes the README and English
user guide; web pages and screenshots are available on the web guide.

A library-wide visual review pause persists across later saves and restarts,
and requires an explicit request to resume all library review. Time and page
guidance does not automatically stop review. Original PDFs are not modified,
moved, or deleted.

## Release assets

- `research-agent-0.4.1.tar.gz`: product bundle without development harnesses,
  tests, or personal research data
- `install-release.sh`: downloads and installs a fresh copy
- `SHA256SUMS`: integrity checks for the downloadable files

GitHub's separate **Source code** download is the development source. Use the
README installation command for the product release.

Automated checks do not call subscription models. Actual Codex permissions,
notifications, and model calls depend on the environment. Guide examples reflect
the results checked for those requests and do not establish the accuracy of all
PDF visual interpretation.
