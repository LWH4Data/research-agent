# Research Agent 0.4.1 배포 검증 · 2026-10-06

## 범위와 현재 상태

사용자가 완료한 가이드 변경의 푸시와 배포 버전업을 요청했다. 가이드 보완이므로
0.4.1 패치 버전을 준비한다. 런타임 동작 변경은 없다. 기존 v0.4.0 태그는 유지한다.

- 최신 빈 폴더 선택 초안과 여러 폴더 선택·목록에 추가 화면을 실제 원본으로 반영한다.
- 연결한 폴더의 새·변경 PDF 갱신 요청·결과를 제공한다.
- 저장 후 시각 검토 시작, 지정 문서 일시 정지, 남은 검토 재개, 현재 상태 확인을 실제 요청·결과로 안내한다.
- 선정한 페이지의 완료·진행/대기·추가 확인을 구분한다. ALBERT 10쪽의 추가 확인은 완료로 표현하지 않는다.
- 한영 설치 버전과 배포 파일을 0.4.1로 맞춘다. 새 설치 전용과 기존 설치 업데이트 미지원 안내는 유지한다.

원본 캡처·가이드 브라우저 검증은 [폴더 선택 기록](./guide-folder-picker-captures-2026-10-06.md),
[폴더 갱신 기록](./guide-folder-refresh-2026-10-06.md),
[검토 제어 기록](./guide-review-controls-2026-10-06.md)에 남겼다.
한국어 실제 캡처에 한영 설명을 제공한다. 실제 영문 화면과 ALBERT 추가 확인 결과는 후속 보완이다.

버전과 가이드 검증, 제품 태그·main 푸시와 Pages 게시 확인을 완료했다.
제품 태그의 공개 배포 파일을 먼저 검증한 뒤 같은 커밋의 웹 가이드를 게시했다.

## 로컬 검증 완료

- `uv lock`을 실제 실행했다. 의존성 변경 없이 editable 제품 버전만 0.4.1로 바뀌었다.
- 전체 자동 테스트: 528개 중 521개 통과·7개 조건부 건너뜀, 48.530초.
  실제 권한 통합 opt-in 3개, 실제 압축 미지정 2개, 대소문자 파일시스템 조건 2개다.
  압축 미지정 2개는 아래 별도 실제 배포본 검사에서 통과했다.
- workflow의 압축 생성 Python을 변경 없이 추출해 명시한 manifest로 임시 staging을 만들었다.
  제품 파일 58개·tar 항목 59개의 모든 내용·권한, 개발 파일 제외와 canonical 제품 규칙·설정 매핑,
  압축·설치 파일 SHA-256을 검증했다.
- 최종 한국어 가이드를 포함한 실제 압축 검사 3개 모두 통과, 8.999초.
  macOS 임시 HOME의 설치·버전·검색·원본 보존·제거를 확인했다.
- `--tag v0.4.1` 버전 검사, 한영웹 설치 명령 일치, JavaScript 3개 구문과 변경 형식 검사를 통과했다.
  독립 검토에서 발견한 배포본 한국어 안내의 v0.3.0 표기를 v0.4.1로 수정하고 실제 압축을 재검증했다.
- 실제 브라우저의 한영 설치 안내에서 0.4.1 주소·명령·표시와 갱신한 cache 값을 확인했다.
  앞선 전체 가이드 36개 브라우저 조합 검증은 위 캡처 기록에 유지한다.

검증 요약: `/private/tmp/research-agent-0.4.1-validation-summary.json`.
전체 로그: `/private/tmp/research-agent-0.4.1-full-validation.log`.
실제 압축 로그: `/private/tmp/research-agent-0.4.1-actual-bundle-validation.log`.
로컬 압축 SHA-256은 `06596ecb13cf84a0948e6f184bb594d3df5c18735c1768de6f72af3dcd387047`이다.
로컬 생성 당시 HEAD 시간과 게시 커밋 시간이 다르므로 공개 압축 검증은 공개 SHA256SUMS와
각 member의 내용·권한을 기준으로 한다.

## 검증 범위의 한계

자동 검사는 구독 모델을 호출하지 않는다. 개인 설치·연구 저장소·원본 PDF를
변경하지 않는다. 실제 사용자 환경의 Codex 권한·알림·PDF 해석 정확도 전체는
이번 배포 검사로 보증하지 않는다.

## 원격 게시 완료

- 배포 커밋 `03c3fa43fe224af40dfc3a1885a1c45f971b7ddc`에 새 `v0.4.1` 태그를 붙여 먼저 푸시했다.
  기존 v0.4.0 태그는 변경하지 않았다.
- [태그 검사·게시](https://github.com/LWH4Data/research-agent/actions/runs/37411107572)의
  validate와 publish가 성공했고 [Prototype 사전 출시](https://github.com/LWH4Data/research-agent/releases/tag/v0.4.1)가 게시됐다.
  원격 전체 테스트는 528개 중 520개 통과·8개 제외, 92.215초이다.
  로컬의 7개 제외에 CI의 Codex CLI 미설치로 exact launcher prefix 검사 1개가 더 제외됐다.
  실제 압축 설치 검사 3개는 모두 통과, 14.208초이다. 로컬 결과와 구분한다.
- 공개 설치 파일·제품 압축·SHA256SUMS 세 파일을 내려받았다. 공개 확인 값과 모든 제품 파일 58개의
  내용·권한, 제품 규칙·설정과 버전을 소스와 비교해 일치함을 확인했다.
  제품 압축 SHA-256: `677a0f413859476470102d4ce5c76209e825f6f1d299e43f7e2295d1f453c83f`.
  설치 파일 SHA-256: `95d98dfee239188a40a76f8f908d758a6006f2ab78355c21b677b2d8f033a020`.
- 공개 파일 검증 후 같은 커밋의 main을 푸시했다.
  [main 검사](https://github.com/LWH4Data/research-agent/actions/runs/37411397703)와
  [Pages 배포](https://github.com/LWH4Data/research-agent/actions/runs/37411397723)가 성공했다.
- [공개 웹 가이드](https://lwh4data.github.io/research-agent/?lang=ko&step=3#/start)의
  HTML·스크립트·스타일·새 캡처 26개 파일을 읽어 소스 bytes와 일치함을 검증했다.
  브라우저에서 v0.4.1 표시와 최신 다중 폴더 선택 화면·목록에 추가 버튼,
  이미지 로딩·가로 넘침을 확인했다. 확인 화면은 `/private/tmp/research-agent-v0.4.1-public-guide.png`이다.

원격 실행 로그: `/private/tmp/research-agent-0.4.1-tag-run-37411107572.log`.
공개 파일 검증: `/private/tmp/published-research-agent-0.4.1-dltcspx1/verification.json`.
공개 웹 검증: `/private/tmp/research-agent-0.4.1-pages-verification.json`.
기존 설치본의 자동 업데이트나 개인 자료의 갱신은 수행하지 않았다.
