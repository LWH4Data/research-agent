# Research Store

기존 논문 디렉터리를 읽기 전용으로 탐색해 검색용 Markdown을 만드는 작은 로컬 저장소입니다. 친구는 이 폴더를 Codex 프로젝트로 열고 논문과 저장된 연구 메모를 검색할 수 있습니다.

이 버전에는 Plugin, Skill, MCP, 벡터 데이터베이스가 없습니다. 원본 PDF는 복사·수정·삭제하지 않습니다. 변환기는 원본 경로 대신 이 프로젝트 안에 만든 임시 복사본만 전달받습니다.

## 디렉터리

```text
research-agent/
├── config.toml                  # 사용자 설정, Git 제외
├── papers/                      # 사용자가 넣는 원본 PDF, Git 제외
├── knowledge/
│   ├── documents/              # 생성된 Markdown, Git 제외
│   └── conversations/          # Codex가 저장하는 연구 메모, Git 제외
└── .research-store/
    ├── state.json              # 증분 동기화 상태
    └── tmp/                    # 변환 중 사용하는 임시 복사본
```

## 준비

```sh
cp config.example.toml config.toml
```

기본 설정은 프로젝트 안의 `papers/`를 읽습니다. 테스트할 PDF를 여기에 넣으면 됩니다. 기존의 외부 논문 디렉터리를 사용하려면 `path`를 절대 경로로 바꿉니다. 여러 디렉터리를 사용하려면 블록을 추가하고 서로 다른 `id`를 지정합니다.

```toml
[[sources]]
id = "papers"
path = "papers"

[[sources]]
id = "external-papers"
path = "/Volumes/archive/papers"
```

의존성을 설치합니다.

```sh
uv sync
```

## 사용

PDF를 찾아 Markdown으로 동기화합니다.

```sh
uv run research-store sync
```

처리 상태만 확인할 수 있습니다.

```sh
uv run research-store status
```

처음에는 모든 PDF를 처리합니다. 다음 실행부터 파일 크기와 수정 시각을 비교해 변경된 파일만 읽습니다. 원본에서 사라진 파일의 파생 Markdown은 자동으로 삭제하지 않고 상태에서 `missing`으로 표시합니다.

친구는 Codex 앱에서 이 디렉터리를 프로젝트로 열고 다음처럼 요청하면 됩니다.

- `DBR cavity와 관련된 논문을 찾아서 출처와 함께 정리해줘.`
- `내가 전에 thermal rollover에 대해 말한 내용을 찾아줘.`
- `이 내용은 다음에 찾을 수 있도록 연구 메모로 저장해줘.`

현재 PDF 변환은 검색용 텍스트의 공백과 페이지 경계를 안정적으로 보존하기 위해 PyPDF를 사용합니다. 각 페이지 앞에는 `<!-- page: N -->` 표시가 추가됩니다. 검색 대상은 생성된 Markdown 자체이므로 SQLite나 벡터 인덱스 없이도 Codex가 파일 검색을 사용할 수 있습니다. 문서 수가 커져 검색 지연이나 누락이 확인되면 파생 SQLite FTS 인덱스를 추가할 수 있습니다.

## 원본 보호

프로그램은 다음 조건을 확인하고 위반 시 동기화를 중단합니다.

- 생성 파일 경로가 원본 디렉터리 안에 있지 않을 것
- 상태 및 임시 경로가 원본 디렉터리 안에 있지 않을 것
- 서로 다른 원본에 중복된 `id`를 사용하지 않을 것

운영체제 또는 Codex에서도 원본에는 읽기 권한만, 이 프로젝트에는 쓰기 권한만 부여하면 방어가 한 단계 더 강해집니다.
