# 버전과 사용자용 Release 배포

[한국어](./releases.md) | [English](./releases.en.md) | [기술 설계 목차](./README.md)

GitHub 저장소는 개발 코드와 문서를 그대로 공개한다. Release는 그중 제품 실행에
필요한 파일만 묶어 사용자가 설치할 수 있게 제공하는 별도의 배포 페이지다.
이 문서는 배포 방식과 확인 절차를 설명하며, 특정 원격 실행의 성공 기록을
뜻하지 않는다. 실제 발행 여부는 GitHub Actions와 Releases에서 확인한다.

## 무엇을 하면 배포되는가

| 작업 | 결과 |
| --- | --- |
| `main`에 커밋·푸시 | 검사와 배포본 설치 시험만 실행 |
| Pull Request 또는 Actions 수동 실행 | 검사와 배포본 설치 시험만 실행 |
| 버전 태그를 푸시 | 검사에 성공하면 사전 출시(pre-release) 게시 |

태그는 특정 커밋에 붙이는 버전 이름이다. 예를 들어 `v0.3.0`은
`pyproject.toml`과 `uv.lock`의 제품 버전 `0.3.0`과 일치해야 한다.
이름이 다르면 검사를 중단하고 게시하지 않는다. 태그를 로컬에 만들기만 해서는
게시되지 않으며, 태그를 GitHub에 푸시해야 한다.

```mermaid
flowchart LR
    A[버전 태그 푸시] --> B[버전 검사·자동 테스트]
    B --> C[허용 목록으로 배포본 생성]
    C --> D[macOS 임시 설치·검색·제거 시험]
    D --> E[검사한 파일을 Release에 게시]
```

## 무엇을 배포하는가

[`release-check.yml`](../../.github/workflows/release-check.yml)이
[`runtime-files.txt`](../../packaging/runtime-files.txt)에 명시된 파일만 묶는다.
현재 목록은 배포 경로 기준 49개다. 프로그램, 스킬, 에이전트, 설치·제거 도구와
사용자 안내를 포함하고, 개발 하니스·테스트·기술 문서·개인 설정·연구 자료는
제외한다. 새 실행 파일을 추가하면 이 목록도 함께 검토해야 한다.

제품 운영 규칙은 [`resources/AGENTS.runtime.md`](../../resources/AGENTS.runtime.md)
한 곳에서 관리한다. 개발용 루트 `AGENTS.md`는 이를 참조하며, 배포본에서는
제품 규칙을 `resources/AGENTS.runtime.md`와 루트 `AGENTS.md`에 동일하게 넣는다.
스킬과 등록된 에이전트는 `resources/AGENTS.runtime.md`를 읽는다. 개발 문서를
사용자에게 전달하지 않으면서 제품 규칙이 서로 달라지는 것을 방지하는 구성이다.

Release에는 다음 세 파일이 올라간다.

| 파일 | 용도 |
| --- | --- |
| `research-agent-0.3.0.tar.gz` | 버전별 사용자용 제품 묶음 |
| `install-release.sh` | 지정한 버전의 새 설치를 시작하는 도구 |
| `SHA256SUMS` | 다운로드 파일의 SHA-256 확인 값 |

사용자는 [해당 버전 README](https://github.com/LWH4Data/research-agent/tree/v0.3.0#readme)의
명령을 복사하면 된다. 명령이 설치 도구를 내려받고, 설치
도구가 제품 묶음과 확인 값을 받아 압축 파일을 검증한 뒤 설치한다. GitHub의
**Code → Download ZIP**, `git clone`, Release의 자동 **Source code** 다운로드는
여전히 개발 소스 전체를 받는 경로다.

검사를 마친 파일은 Actions의 `runtime-release` artifact로 3일간 보관한다.
태그 실행의 게시 단계는 그 파일을 그대로 받아 Release에 첨부한다. Release에
첨부한 파일은 Actions artifact의 3일 보관 기한이 끝나도 함께 만료되지 않는다.

## 어떤 검사를 하는가

자동 테스트 뒤 실제 배포 압축을 별도의 macOS 임시 HOME에 풀어 설치한다.
스킬·에이전트 등록, 버전 표시, 테스트 PDF 등록·변환·검색, 원본 보존과 제거를
확인한다. 테스트의 HOME과 휴지통은 임시 공간이며 사용자의 실제 설치를
제거하지 않는다. 파일 목록, 원본과 압축 내용의 일치, 실행 권한과 체크섬도
검사한다. 자세한 범위는 [`test_release_bundle.py`](../../tests/test_release_bundle.py)에 있다.

이 검사는 구독 모델을 호출하지 않는다. 조건부 권한 통합 검사는 기본 실행에서
건너뛰므로, 모든 Codex 환경의 실제 권한·알림·모델 호출이나 PDF 시각 해석
정확도를 검증했다는 의미는 아니다. GitHub Actions 실행 결과에서도 건너뛴
항목과 실패한 단계가 있는지 확인해야 한다.

## 다음 버전을 내는 순서

1. `pyproject.toml`의 버전을 변경한다. 예를 들어 버그 수정이면 `0.3.1`을 사용할 수 있다.
2. 개발 환경의 `uv lock`으로 `uv.lock`을 다시 생성한다. 잠금 파일의 버전 문자열만 수동 교체하지 않는다.
3. README와 한글·영문 사용자 안내에 고정한 다운로드 태그와 `--version` 값, [`RELEASE_NOTES.md`](../../packaging/RELEASE_NOTES.md)를 함께 갱신한다. 실행 파일이 늘었다면 배포 목록도 확인한다.
4. 변경한 동작의 테스트, 전체 자동 테스트와 버전 검사를 실행한다. 아래 `0.3.1`은 다음 배포의 예시다.

```sh
bash scripts/reproduce-validation.sh full
.venv/bin/python -B scripts/check_release_version.py --tag v0.3.1
```

5. 의도한 변경만 커밋해 `main`에 푸시하고, 해당 커밋의 Actions 검사가 성공했는지 확인한다.
6. 배포할 커밋에서 태그를 만들고 해당 태그만 푸시한다.

```sh
git tag -a v0.3.1 -m "Research Agent v0.3.1"
git push origin v0.3.1
```

7. **Actions → Validate and release**에서 `validate`와 `publish`가 성공했는지 확인한다. **Releases**에서 같은 버전과 세 배포 파일이 보이면 게시된 것이다.

검사가 실패하면 실패한 단계를 수정한다. 이미 게시한 태그를 다른 커밋으로
옮기거나 같은 버전의 파일을 몰래 교체하지 않고, 수정 버전을 새로 배포한다.
새 버전의 실제 발행 전에는 README의 새 다운로드 링크가 아직 동작하지 않을 수 있다.

## 아직 제공하지 않는 업데이트

현재 설치 도구는 **새 설치만** 지원한다. 목적지에 폴더·파일·링크가 이미 있으면
덮어쓰지 않고 중단한다. 자동 업데이트나 기존 연구 자료를 옮기는 기능은 없다.
기존 사용자에게 설치를 위해 연구 저장소를 삭제하라고 안내하지 않는다.
향후 업데이트는 실행 중인 작업과의 충돌, 저장 형식 호환성, 자료 보존과 복구를
별도로 설계·검증한 뒤 제공해야 한다.

## 웹 사용 가이드 배포

[웹 가이드](https://lwh4data.github.io/research-agent/)는 제품 Release와 별도로
GitHub Pages에 공개한다. [`docs/site`](../site/)에 있는 HTML·CSS·JavaScript와
승인된 캡처만 게시하며, 연구 자료나 개발 문서는 사이트에 올리지 않는다.

[`pages.yml`](../../.github/workflows/pages.yml)은 `main`에 웹 가이드 변경을
푸시할 때 자동 배포한다. Actions의 **Deploy web guide**에서 결과를 확인한다.
설치 명령은 `docs/site/config.js`에서 한글·영문 화면이 공유한다. 새 제품 버전을
공개하면 README와 함께 이 명령과 가이드의 버전 안내도 갱신한다. 기능 설명은
`app.js`와 `content-en.js`, 화면 스타일은 `styles.css`에서 관리한다. 빈 프레임은
아직 준비 중인 실제 캡처 자리이며, 결과 화면을 만들어 보여주지 않는다.
