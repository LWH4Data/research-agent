# Research Agent 0.4.2 배포 검증 · 2026-10-06

## 범위와 현재 상태

사용자가 한영 안내창을 포함한 설치 버전의 배포를 요청했다. 0.4.2 새 설치용
사전 출시를 게시하고 공개 파일 검증을 완료했다. 기존 태그와 Release 파일은 변경하지 않는다.

- 설치 완료 안내, 폴더 선택 설명, 확인 목록·빈 상태·선택 개수·버튼·관련 오류가 한국어와 영어를 지원한다.
- 설치 안내는 macOS 선호 언어에서 첫 지원 언어를 사용하고, 지원 언어가 없거나 감지에 실패하면 영어를 사용한다.
- 설치 이후 등록 실행기의 `source-add --language auto|ko|en`으로 표시 언어를 지정한다. 설치 bootstrap 셸에는 이 옵션이 없다.
- macOS 자체 UI는 시스템 언어를 따르며 설치 셸 전체의 터미널 출력은 번역 범위 밖이다.
- 언어는 호스트 표시에서만 사용하며 확정 경로만 저장 명령에 전달한다. 권한과 모델 경로는 변경하지 않는다.
- README·영문 사용자 안내·웹의 새 설치 링크와 제품 버전을 0.4.2로 맞춘다.

구현·기능별 시험과 실제 영문 설치 안내 미리보기의 범위는
[안내창 언어 기록](./dialog-language-2026-10-06.md)에 남겼다.
실제 영문 폴더 선택·확인 목록 캡처와 다른 Mac의 포커스 확인은 후속 사용자 시험이다.
기존 한국어 캡처를 영문 화면으로 꾸미지 않는다.

사용자가 영어 가이드 촬영을 위해 승인한 개인 설치 초기화는 유지한다.
이번 배포는 개인 설치를 재생성하거나 기존 자료를 갱신하지 않는다.
시험은 임시 HOME·시험 원본·시험 저장소에서 실행하며 실제 모델을 호출하지 않는다.

## 로컬 검증

- `uv lock --offline`으로 잠금 파일을 재생성했다. 의존성은 그대로이며 제품 버전만 변경됐다.
- `bash scripts/reproduce-validation.sh full`: 559개 중 552개 통과·7개 조건부 제외, 50.813초.
  외부 권한 opt-in 3개, 압축 미지정 2개, 대소문자 파일시스템 조건 2개다.
  압축 미지정 2개는 아래 별도 압축 시험에서 통과했다.
- workflow의 Python 조립 코드를 변경 없이 임시 staging에서 실행했다.
  제품 파일 58개·tar 항목 59개의 전체 내용·권한, 개발 파일 제외, canonical 제품 규칙·설정 매핑과 SHA-256을 확인했다.
- 실제 압축을 지정한 시험 3개 모두 통과, 16.515초. macOS 임시 HOME에서 설치·버전·등록·검색·원본 보존·제거를 확인했다.
  비대화형 설치 시험이므로 GUI 표시 검증과 구분한다.
- `check_release_version.py --tag v0.4.2`, `check_guides.py`, JavaScript 3개 구문,
  가이드 일치 시험 8개, 한영 설치 단계 렌더링과 `git diff --check`가 통과했다.
- 개인 설치 경로는 없는 상태를 유지했다. 실제 모델이나 개인 라이브러리를 사용하지 않았다.

전체 로그: `/private/tmp/research-agent-0.4.2-full-validation.log`.
실제 압축 로그: `/private/tmp/research-agent-0.4.2-actual-bundle-validation.log`.
파일 검증 요약: `/private/tmp/research-agent-0.4.2-release-validation.json`.
로컬 압축 SHA-256: `87fcb2bf2fdfb5a88f3edccb121f6c9fdbdcdc0475507aeda2f5c169d9e0a2ef`.
로컬 조립과 게시 커밋의 시각이 다를 수 있으므로 공개 파일은 공개 SHA256SUMS와 각 파일의 내용·권한으로 검증한다.

## 원격 게시

- 배포 커밋 `c6d20112e1b6d8bd4c03240e9167ea1a943941f3`의 새 `v0.4.2` 태그를 먼저 푸시했다.
  기존 태그와 Release는 변경하지 않았다.
- [태그 검사·게시](https://github.com/LWH4Data/research-agent/actions/runs/37427013279)의
  validate·publish가 성공했고 [v0.4.2 Prototype 사전 출시](https://github.com/LWH4Data/research-agent/releases/tag/v0.4.2)가 게시됐다.
  CI 전체 559개 중 551개 통과·8개 조건부 제외, 87.539초. 실제 압축 시험 3개는 모두 통과, 12.581초.
- 공개 첨부파일 3개를 내려받아 SHA256SUMS와 실제 압축·설치 파일의 해시를 검증했다.
  58개 제품 파일 내용·권한과 canonical 규칙·설정, 내장 pyproject·lock 버전, Release 본문은 태그 소스와 일치한다.
  공개 제품 압축 SHA-256: `2cc0e9faaebc7ab9f16f19b0c6fbf5339020455870d514f4975aba80d793aad6`.
  설치 파일 SHA-256: `95d98dfee239188a40a76f8f908d758a6006f2ab78355c21b677b2d8f033a020`.
- 공개 파일 검증 후 같은 배포 커밋의 main을 푸시했다. [main 검사](https://github.com/LWH4Data/research-agent/actions/runs/37427512477)의 validate가 성공하고 publish는 정상 제외됐다.
  CI 전체 559개 중 551개 통과·8개 제외, 75.479초. 실제 압축 시험 3개는 모두 통과, 10.868초.

공개 파일 검증: `/private/tmp/research-agent-v042-asset-audit.tXw57q/verification.json`.
사용자의 개인 설치는 없는 상태를 유지한다. 원본 PDF와 휴지통에 보관한 기존 설치·자료는 변경하지 않았다.

- [Pages 배포](https://github.com/LWH4Data/research-agent/actions/runs/37427512393)가 성공했다.
  공개 `index.html`, `config.js`, `content-en.js`, `app.js`, `styles.css`는 배포 소스와 바이트 일치한다.
  실제 Chrome의 한영 설치 페이지에서 v0.4.2 표시·Release 다운로드 URL·`--version 0.4.2`를 확인했다.
  한영 폴더 안내에서는 macOS 언어 설명·웹 언어와의 구분·한국어 실제 캡처 표시와 영어 버튼명을 확인했다. 임시 탭은 닫았다.
  공개 웹 검증: `/private/tmp/research-agent-0.4.2-pages-verification.json`.

main 검사 기록: `/private/tmp/research-agent-v042-asset-audit.tXw57q/main-verification.json`.
