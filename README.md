# Research Store

흩어진 기존 논문 폴더를 읽기 전용으로 탐색하여 검색 가능한 Markdown
저장소를 만드는 Codex 프로젝트입니다. 원본 PDF를 한곳으로 옮길 필요가
없으며, 첫 동기화 이후에는 새 파일과 변경된 파일만 변환합니다.

친구가 사용하는 기능은 자연어 요청 세 가지입니다.

- `논문 저장소 업데이트해줘.`
- `내 논문에서 DBR cavity와 관련된 내용을 찾아줘.`
- `이 대화를 다음에 찾을 수 있도록 저장해줘.`

Codex는 문서 관리와 검색에 GPT-5.6 Luna xhigh를 사용하고, 수식·표·그림이
있는 페이지만 GPT-5.6 Sol high에 전달합니다. 친구가 모델이나 에이전트를
직접 선택할 필요는 없습니다.

## 저장 구조

```text
research-agent/
├── .codex/
│   ├── agents/
│   │   ├── library-manager.toml     # Luna xhigh
│   │   └── paper-converter.toml     # Sol high
│   └── skills/research-library/
├── config.toml                      # 개인 경로, Git 제외
├── knowledge/
│   ├── documents/                   # 논문 Markdown, Git 제외
│   ├── conversations/               # 저장한 대화, Git 제외
│   └── assets/                      # 필요한 표·수식 이미지, Git 제외
└── .research-store/
    ├── library.sqlite               # 동기화 상태, Git 제외
    └── tmp/                          # 변환·검토용 임시 파일
```

`.codex/agents`에는 에이전트 설정만 들어갑니다. 논문과 대화에서 만든
지식은 모두 `knowledge`에 저장됩니다.

## 최초 설정

저장소를 내려받은 후 Codex 앱에서 이 폴더를 프로젝트로 엽니다. 친구는
Codex에 다음처럼 말하면 됩니다.

```text
내 논문은 문서 폴더와 바탕화면의 Research 폴더에 흩어져 있어.
두 폴더를 원본 위치로 등록해줘.
```

Codex는 `config.example.toml`을 참고해 로컬 `config.toml`을 만듭니다.
직접 작성한다면 다음과 같습니다.

```toml
[store]
documents = "knowledge/documents"
conversations = "knowledge/conversations"
assets = "knowledge/assets"
state = ".research-store/library.sqlite"
temporary = ".research-store/tmp"

[[sources]]
id = "documents"
path = "~/Documents"

[[sources]]
id = "desktop-research"
path = "~/Desktop/Research"
```

`id`는 영문과 숫자, `-`, `_`로 만든 서로 다른 이름이어야 합니다. 절대경로가
들어가는 `config.toml`은 Git에 올라가지 않습니다.

의존성 설치가 필요할 때 Codex가 다음 명령을 실행합니다.

```sh
uv sync
```

## 증분 동기화

```sh
uv run research-store sync
```

폴더 전체에서는 파일 경로, 크기와 수정 시각만 확인합니다. 정보가 달라진
PDF에 한해 SHA-256을 계산하고 실제 내용이 바뀌었을 때 다시 변환합니다.
원본에서 사라진 PDF의 Markdown은 삭제하지 않고 `missing` 상태로 남깁니다.

동기화 상태는 SQLite에 기록합니다. 이 SQLite는 벡터 데이터베이스가
아니며 파일 변경 여부와 검토 상태를 관리하는 원장입니다.

```sh
uv run research-store status
```

## 수식과 표의 이미지 검토

기본 변환기는 PyPDF로 전체 본문과 `<!-- page: N -->` 경계를 저장합니다.
표 캡션, 수식 밀도, 그림, 추출 글자 부족이 감지된 페이지만 검토 대기열에
등록합니다.

```sh
uv run research-store review-list
```

`paper_converter`는 대기 중인 페이지만 220 DPI PNG로 렌더링하고 원본과
Markdown을 비교합니다.

```sh
uv run research-store render-review "documents:folder/paper.pdf"
```

확인된 수식은 LaTeX로, 단순한 표는 Markdown 표로 보정합니다. 복합 헤더나
불분명한 기호는 추측하지 않고 `needs_review`로 남깁니다. 페이지 검토 결과는
다음 명령으로 SQLite에 기록합니다.

```sh
uv run research-store review-complete "documents:folder/paper.pdf" \
  --page 4 --page 5 --status verified --model gpt-5.6-sol
```

## 대화 저장

친구가 대화를 저장해 달라고 하면 Codex는 먼저 범위를 한 번 묻습니다.

1. 방금 대화한 현재 주제
2. 이번 대화 전체
3. 친구가 직접 지정하는 범위

범위를 선택하면 검색용 요약과 선택 범위의 원문을 함께 저장합니다. 사용자
생각, 결정, 검증되지 않은 주장, 미해결 질문과 논문 근거를 구분하므로 나중에
개인적인 추측이 논문 사실처럼 검색되는 일을 줄일 수 있습니다.

실제 저장은 `research-library` skill의 JSON 스키마를 사용합니다.

```sh
uv run research-store save-conversation --payload /tmp/conversation.json
```

결과는 날짜와 주제별 파일로 저장됩니다.

```text
knowledge/conversations/2026/09/15-pdf-수식-변환-설계-a1b2c3.md
```

## 검색 원칙

Codex는 `knowledge/documents`와 `knowledge/conversations`를 함께 검색합니다.
한국어 질문에는 대응하는 영어 기술 용어도 함께 사용합니다. 결과는 다음
출처 유형을 구분해서 보여줍니다.

- 논문 근거
- 사용자의 과거 발언과 연구 메모
- 이전 Codex 설명
- 검증되지 않은 생각

논문 결과에는 Markdown 경로, 원본 PDF의 등록 경로와 가장 가까운 페이지
표시를 포함합니다. 정확한 숫자나 수식이 필요한 답변에서는 이미지 검토
상태를 확인합니다.

## 원본 보호

프로그램은 생성 문서, 대화, 상태 DB와 임시 디렉터리가 원본 디렉터리
안에 있으면 실행을 중단합니다. 변환할 때도 원본을 파서에 직접 전달하지
않고 프로젝트의 임시 디렉터리에 복사한 파일을 사용합니다. 원본 PDF를
수정·이동·삭제하는 기능은 제공하지 않습니다.
