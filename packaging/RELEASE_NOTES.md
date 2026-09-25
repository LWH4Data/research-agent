Research Agent의 첫 사용자용 프로토타입 배포입니다. GitHub 소스는 그대로 유지하고, 설치 파일에는 제품 실행에 필요한 파일만 담았습니다.

## 설치

[README의 설치 안내](https://github.com/LWH4Data/research-agent/tree/v0.3.0#readme)를 따라 터미널에서 설치 명령을 실행하세요. 기존 설치 폴더가 있으면 덮어쓰지 않고 중단합니다. 이 버전은 새 설치를 지원하며, 기존 자료를 보존하는 업데이트 기능은 아직 제공하지 않습니다.

## 포함된 기능

- 여러 위치의 PDF를 원본 수정 없이 등록하고 정리하기
- 대화에 첨부한 PDF를 저장소에 추가하기
- PDF와 저장한 대화를 함께 검색하기
- 그림·표·수식을 별도 시각 검토하고 진행 상태 확인하기
- 대화 기록 저장·조회·수정·삭제하기

## 배포 파일

- `research-agent-0.3.0.tar.gz`: 개발 하니스·테스트·개인 자료를 제외한 제품 묶음
- `install-release.sh`: 내려받기와 새 설치를 진행하는 실행 파일
- `SHA256SUMS`: 다운로드 파일 무결성 확인 값

GitHub가 별도로 제공하는 **Source code**는 개발 소스입니다. 일반 사용자는 README의 설치 명령을 사용하세요.

현재 사용자 지원 대상은 macOS입니다. 실제 Codex 권한과 알림, 모델 호출은 사용자 환경에 따라 달라질 수 있습니다. 자동 검사는 모델을 호출하지 않으며 PDF 시각 해석의 정확도 전체를 보증하지 않습니다.

---

First end-user prototype release. The runtime archive contains only product files; development instructions, tests, and personal research data are excluded.

Follow the [README installation instructions](https://github.com/LWH4Data/research-agent). This release supports fresh installation on macOS and refuses to overwrite an existing destination. An update path that preserves an existing library is not yet provided.

The product supports read-only PDF sources, conversation PDF imports, combined retrieval, background visual review, and saved conversation management. Automated checks do not call subscription models or establish visual interpretation accuracy. Use the custom runtime archive through the installer, rather than GitHub's separate source-code download.
