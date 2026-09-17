# Research Agent

흩어진 위치의 PDF를 **읽기 전용**으로 찾아 검색 가능한 Markdown으로
정리하고, 사용자가 선택한 Codex 대화를 연구 메모로 보관하는 로컬
프로젝트입니다. PDF가 논문이라고 가정하지 않으며 원본을 한곳으로 옮기지
않습니다.

## 설치

이 GitHub 저장소가 비공개인 동안에는 소유자가 먼저 친구를 Collaborator로
초대해야 하며, 친구는 초대를 수락하고 터미널에서 GitHub 인증을 한 번
마쳐야 합니다. 공개 저장소로 전환하면 이 사전 단계가 없어집니다.

GitHub 접근이 준비된 뒤 터미널에 다음 한 줄을 붙여 넣습니다.

```sh
git clone https://github.com/LWH4Data/research-agent.git "$HOME/research-agent" && bash "$HOME/research-agent/install.sh"
```

설치 프로그램은 실행 환경, Python, 라이브러리를 모두
`~/research-agent` 안에 둡니다. 시스템 Python, 셸 설정, `~/.codex`는
수정하지 않습니다. 고정된 공식 `uv` 실행 파일을 프로젝트 내부의 무작위
임시 폴더로 받은 뒤 SHA-256을 확인하고 `.tools/`에 설치합니다. 설치용
캐시도 프로젝트 내부에 만들고 설치가 끝나면 제거합니다.

설치 도중 Finder 폴더 선택창이 열립니다. PDF를 찾아볼 위치를 하나씩
선택합니다. 설치 프로그램은 선택한 경로를 `config.toml`에 기록할 뿐,
이 단계에서 PDF를 스캔하거나 변환하지 않습니다. 선택을 건너뛰면 마지막에
`add-source.sh` 안내가 표시됩니다.

설치가 끝나면 Codex 앱에서 `~/research-agent`를 독립 프로젝트로 열고,
프로젝트 신뢰 요청을 한 번 승인합니다. 이후에는 다음처럼 말하면 됩니다.

- `새로 추가된 PDF를 정리해줘.`
- `DBR cavity와 관련된 내용을 찾아줘.`
- `이 대화에서 실험 설계 부분만 저장해줘.`
- `지난번에 내가 굴절률 보정에 관해 뭐라고 했지?`

Codex는 저장소 관리와 검색을 GPT-5.6 Luna xhigh에 맡기고, 수식·표·그림이
있는 페이지만 GPT-5.6 Sol high에 전달합니다. 사용자가 모델을 고를 필요는
없습니다.

## 원본 보호 경계

다음 조건은 지침이 아니라 설정과 코드 검사로 강제됩니다.

- Codex의 쓰기 범위는 `research-agent` 프로젝트 내부뿐입니다.
- 권한 상승은 비활성화되어 원본 폴더 쓰기를 요청할 수 없습니다.
- 원본과 프로젝트가 서로 포함되는 경로는 등록할 수 없습니다.
- 원본 경로에는 Markdown, 숨김 파일, 캐시, 잠금 파일을 만들지 않습니다.
- 원본의 수정·교체·이동·이름 변경·권한 변경·삭제 기능을 제공하지 않습니다.
- 심볼릭 링크와 `..` 경로로 쓰기 범위를 벗어나려는 동작을 거부합니다.
- 모든 Markdown, 이미지, SQLite, 임시 파일은 프로젝트 내부에만 생성합니다.
- 설치 경로의 심볼릭 링크·하드 링크를 거부하고, 실제 Python이 프로젝트
  내부에 설치됐는지 확인합니다.

원본에서 파일이 사라지면 SQLite에 `missing` 상태만 기록합니다. 생성된
Markdown이나 다른 원본을 대신 삭제하지 않습니다.

## 검색 위치 관리

등록된 위치를 확인합니다.

```sh
cd "$HOME/research-agent"
./research-store source-list --plain
```

Finder 선택창으로 위치를 추가합니다.

```sh
bash "$HOME/research-agent/add-source.sh"
```

정확한 경로나 PDF 파일 하나를 알고 있다면 직접 등록할 수도 있습니다.

```sh
./research-store source-add "$HOME/Documents/광소자 연구"
./research-store source-add "$HOME/Desktop/notes.pdf"
```

`source-remove`는 **앞으로의 스캔만 중단**합니다. 원본 경로 정보는 비활성
상태로 보존되고, 원본과 이미 생성된 Markdown 스냅샷은 모두 남아 계속
검색됩니다. 같은 위치를 다시 추가하면 스캔이 재개됩니다.

```sh
./research-store source-remove <source-id>
```

## 증분 동기화

```sh
./research-store sync
```

처음에는 등록된 위치에서 PDF를 찾습니다. 다음 실행부터는 경로, 크기,
수정 시각을 먼저 비교하고 새 파일과 변경된 파일만 다시 읽습니다. 실제 PDF
파싱은 프로젝트 내부에 만든 무작위 임시 복사본으로 수행합니다.

등록된 위치가 없으면 성공한 빈 검색처럼 처리하지 않고 `add-source.sh`를
안내합니다. 외장 디스크가 연결되지 않았거나 폴더를 읽을 수 없으면 그 위치를
오류로 표시하고, 정상 위치는 계속 처리하며 이전 문서를 삭제됨으로 바꾸지
않습니다.

```sh
./research-store status
./research-store review-list
```

PDF와 저장된 대화를 함께 직접 검색할 수도 있습니다. 생성된 지식 파일은
Git에서 제외되지만 이 명령은 해당 파일을 빠짐없이 검색합니다.

```sh
./research-store search "DBR" "distributed Bragg reflector"
```

표, 수식, 그림 또는 텍스트 추출 실패가 감지된 페이지만 프로젝트 내부에
PNG로 렌더링합니다. 렌더링에는 프로젝트 의존성인 `pypdfium2`를 사용하므로
별도의 시스템 PDF 도구가 필요하지 않습니다. 렌더링 때의 SHA-256과 검토
완료 시점의 원본 SHA-256이 다르면 검토 결과를 받아들이지 않습니다.
시각 검토 노트는 `### Pages N` 제목과
`<!-- visual-review-pages: N -->` 표시를 함께 저장합니다. 따라서 나중에
검색 결과를 인용할 때는 노트 근처의 일반 페이지 표시가 아니라 이 검토
페이지 표시를 사용합니다.

## 대화 저장

사용자가 대화를 저장해 달라고 하면 Codex는 먼저 범위를 묻습니다.

1. 현재 주제
2. 이번 대화 전체
3. 사용자가 설명하는 범위

선택된 사용자 발언은 원문 그대로 저장하고, 검색용 요약·결정·검증되지 않은
생각·미해결 질문·관련 PDF 근거를 구분합니다. 대화 JSON은 임시 파일을 만들지
않고 CLI 표준 입력으로 전달되며, 결과 Markdown은 원자적으로 저장됩니다.
오래된 대화가 압축되어 정확한 원문을
확인할 수 없으면 복원해서 꾸미지 않고, 확인 가능한 원문만 `partial`로
표시하며 누락 범위를 함께 기록합니다.

## 저장 구조

```text
research-agent/
├── .agents/skills/                 # 프로젝트 스킬
├── .codex/agents/                  # Luna/Sol 사용자 정의 에이전트
├── .tools/                         # 프로젝트 전용 uv, Git 제외
├── .python/                        # 프로젝트 전용 Python, Git 제외
├── .venv/                          # 프로젝트 전용 라이브러리, Git 제외
├── config.toml                     # 읽기 전용 원본 경로, Git 제외
├── knowledge/
│   ├── documents/                  # PDF Markdown, Git 제외
│   ├── conversations/              # 저장한 대화, Git 제외
│   └── assets/                     # 검토 이미지, Git 제외
└── .research-store/
    ├── library.sqlite              # 증분 상태, Git 제외
    └── tmp/                         # 프로젝트 내부 임시 파일
```

## 업데이트와 제거

업데이트는 다음 명령으로 받습니다. 개인 경로, Markdown, SQLite는 Git에서
제외되므로 유지됩니다.

```sh
git -C "$HOME/research-agent" pull --ff-only
bash "$HOME/research-agent/install.sh"
```

더 이상 사용하지 않을 때는 Codex에서 이 프로젝트를 제거한 뒤
`~/research-agent` 폴더를 Finder의 휴지통으로 옮깁니다. 전역 설치 파일이나
원본 폴더의 부속 파일이 없으므로 이 폴더 하나가 Research Agent의 전체
영역입니다. 등록했던 원본 위치는 그대로 남습니다.

## macOS 읽기 권한

Documents, Desktop 또는 외장 디스크를 읽지 못한다는 오류가 나오면 macOS의
`시스템 설정 → 개인정보 보호 및 보안 → 파일 및 폴더`에서 Codex가 해당
위치를 읽을 수 있는지 확인합니다. 권한 오류가 난 위치의 이전 검색 자료는
그대로 유지됩니다.
