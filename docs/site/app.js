const pages={
  "start": {
    "title": "시작하기",
    "question": "Research Agent를 처음 써보려면 어떻게 하나요?",
    "requirements": "Mac과 로그인한 Codex를 준비하세요. ChatGPT Pro 5x를 권장하며 Plus는 사용량 제한에 더 빨리 도달할 수 있어요. 별도 API 키나 Git·Python 설치는 필요 없어요.",
    "stageNav": "설치 안내 단계",
    "back": "이전 단계",
    "forward": "다음 단계",
    "saveChoice": "PDF를 저장하는 방법을 선택하세요.",
    "firstTask": "PDF를 첨부해서 저장하기",
    "folderTask": "연결한 폴더의 PDF 저장하기",
    "stages": [
      {
        "label": "터미널 열기",
        "question": "설치는 어디서 시작하나요?",
        "answer": "터미널이라는 Mac 기본 앱에서 시작해요. 이미 터미널이 열려 있다면 다음 단계로 넘어가세요.",
        "steps": ["키보드에서 ⌘ + Space를 누르고 “터미널”을 입력하세요.", "검색 결과의 터미널을 선택하고 Enter를 누르세요."],
        "captures": [
          {"key": "spotlight", "caption": "검색 결과에서 터미널 앱을 선택하세요."},
          {"key": "terminal", "caption": "이런 창이 열리면 준비됐어요. 배경색과 글자는 다를 수 있어요."}
        ]
      },
      {
        "label": "설치하기",
        "question": "터미널에 무엇을 입력하나요?",
        "answer": "아래 명령으로 v0.3.0 사전 출시 버전을 설치해요. 처음 설치할 때 한 번만 실행하세요.",
        "steps": ["아래 “복사”를 누르고, 터미널 창에서 ⌘ + V로 붙여 넣으세요.", "Enter를 누르고 “research-agent 설치가 완료되었습니다.”라는 안내가 나올 때까지 기다리세요."],
        "captures": [{"key": "install-complete", "caption": "터미널에 설치 완료 안내가 표시된 화면"}],
        "noteLabel": "기존 설치가 있거나 오류가 나타났나요?",
        "note": "이 명령은 새 설치용이에요. 기존 폴더가 있다는 안내가 나오면 삭제하지 말고, 표시된 메시지를 Codex에 알려주세요. 정상 설치는 Mac 관리자 암호를 요구하지 않아요.",
        "composer": "install"
      },
      {
        "label": "폴더 선택",
        "question": "PDF가 있는 폴더는 어떻게 연결하나요?",
        "answer": "폴더를 고르고 목록을 확인한 뒤 “연결하고 PDF 저장하기”를 누르세요. 선택한 폴더의 PDF 저장이 시작되고, 텍스트 저장 후 그림·수식·표 확인으로 이어져요. 원본 파일은 수정하지 않아요.",
        "notice": "개발 중인 새 화면을 안내하고 있어요. 현재 설치 명령으로 받는 v0.3.0에는 아직 포함되지 않았어요.",
        "flow": [
          {
            "title": "1. 폴더 추가하기",
            "body": "‘연결할 폴더’ 창에서 “폴더 추가하기”를 누르세요.",
            "capture": {"key": "folder-draft-empty", "caption": "검은 테두리는 눌러야 할 버튼을 알려주는 가이드용 표시예요.", "alt": "연결할 폴더 창의 폴더 추가하기 버튼"}
          },
          {
            "title": "2. 원하는 폴더 고르기",
            "body": "스페이스바 옆 ⌘ Command 키를 누른 채 폴더 이름을 한 번씩 클릭하세요. 원하는 폴더들이 선택되면 키에서 손을 떼고 “목록에 추가”를 누르세요.",
            "capture": {"key": "folder-selection", "caption": "선택된 세 폴더의 모습이에요. 이전 캡처에서 폴더 목록 부분만 잘랐어요.", "alt": "research-agent-test1, test2, test3 폴더가 함께 선택된 목록"}
          },
          {
            "title": "3. 확인하고 PDF 저장 시작하기",
            "body": "연결할 폴더들이 맞는지 확인하고 “연결하고 PDF 저장하기”를 누르세요. 다른 위치의 폴더도 연결하려면 먼저 “폴더 더 추가하기”로 목록에 모으세요. 저장된 본문은 먼저 검색할 수 있고 시각 자료는 이어서 확인해요.",
            "capture": {"key": "folder-draft-confirmation", "caption": "세 폴더를 선택한 확인 화면이에요. 검은 테두리는 “연결하고 PDF 저장하기” 버튼을 알려주는 가이드용 표시예요.", "alt": "세 폴더가 체크된 확인 목록과 연결하고 PDF 저장하기 버튼"}
          }
        ],
        "helpLabel": "문제가 생겼나요? · 취소·잘못 선택·오류 안내",
        "help": [
          {"question": "아직 PDF가 준비되지 않았어요.", "answer": "‘연결할 폴더’ 창에서 “취소”를 누르고 다음 단계로 넘어가세요. 폴더를 연결하지 않아도 설치는 유지돼요."},
          {"question": "원하지 않는 폴더를 골랐어요.", "answer": "연결하기 전이라면 목록에서 해당 폴더의 체크를 해제하세요. 이번에 연결할 목록에서만 제외돼요. 이미 연결했다면 Codex에 잘못 연결한 폴더를 알려주고 연결 해제를 요청하세요. 해제할 폴더가 맞는지 확인하세요."},
          {"question": "폴더를 다 고르기 전에 창을 닫았어요.", "answer": "안쪽 선택창에서 “취소”했다면 앞서 체크한 폴더들이 남아 있어요. “폴더 더 추가하기”로 이어가세요. 확인 목록 전체를 취소했다면 이번 선택은 저장되지 않아요. Codex에 “@Research Agent PDF 폴더 연결창 다시 열어줘”라고 요청하는 기능을 개발 중이며, 실제 Codex에서의 재열기는 확인 중이에요."},
          {"question": "여러 폴더가 선택되지 않거나 오류가 나요.", "answer": "선택창을 한 번 클릭한 뒤 ⌘ 키를 누르고 폴더 이름을 한 번씩 클릭해 보세요. 두 번 클릭하면 선택이 끝날 수 있어요. 오류가 계속되면 표시된 메시지를 Codex에 알려주세요. 해결을 위해 Full access로 바꾸지는 마세요."},
          {"question": "연결했는데 저장이 시작되지 않았어요.", "answer": "연결 완료와 PDF 저장 완료는 다른 상태예요. Codex 실행기를 찾지 못했거나 시작 오류가 나면 연결은 유지하고 저장 대기 상태를 알려줘요. 그 메시지를 Codex에 전달해 이어서 저장하세요. 이전에 전체 시각 검토를 멈췄다면 텍스트 저장 후에도 검토는 재개 요청을 기다려요."},
          {"question": "안내와 다른 창이 보여요.", "answer": "공개된 v0.3.0에서는 “폴더 선택하기”를 누른 뒤 폴더를 고르고 “선택”으로 바로 연결해요. 확인 목록과 저장 자동 시작은 다음 배포에 포함할 예정이에요. v0.3.0에서는 연결 후 Codex에 문서 정리를 요청하세요."}
        ]
      },
      {
        "label": "Codex에서 확인",
        "question": "설치한 Research Agent를 어떻게 불러오나요?",
        "answer": "설치 후 데스크톱 앱을 완전히 종료했다가 다시 열어요. 평소 사용하던 프로젝트에서 시작할 수 있어요.",
        "steps": ["앱의 제품 선택 메뉴에서 Codex를 선택하고, 로컬(Local) 대화를 여세요.", "입력창에 @research를 입력하고 목록에서 Research Agent를 선택하세요.", "아래 문장으로 사용법을 물어보세요. PDF가 없어도 확인할 수 있어요."],
        "captures": [{"key": "codex-invocation", "caption": "Research Agent를 선택해 기능과 시작 방법을 안내받은 실제 화면이에요.", "alt": "Research Agent가 선택된 질문과 PDF 정리·검색·대화 저장 기능, PDF 한 개로 시작하는 방법을 안내하는 응답"}],
        "safety": "권한은 Ask for approval 또는 Approve for me를 사용하세요. Research Agent에는 Full access를 사용하지 마세요.",
        "noteLabel": "메뉴에서 찾을 수 없나요?",
        "note": "입력창에 Instant가 보이면 일반 ChatGPT 채팅이에요. 현재 Research Agent는 Codex의 로컬 작업에서 사용해요. Codex에서도 찾을 수 없다면 설치 완료 안내를 확인하고 앱을 완전히 종료한 뒤 다시 실행하세요. 계속 보이지 않으면 설치 메시지를 Codex에 알려주세요.",
        "composer": "prompt",
        "prompt": "@Research Agent 어떤 기능이 있고, 처음에는 어떻게 사용하면 돼?"
      }
    ],
    "prev": "overview",
    "next": "organize"
  },
  "connect": {
    "title": "PDF 폴더 연결하기",
    "question": "PDF가 여러 폴더에 흩어져 있는데 괜찮나요?",
    "answer": "PDF를 옮길 필요 없어요. 원래 있는 폴더들을 연결하면 됩니다. 현재 배포된 v0.3.0은 연결 후 PDF 정리 요청이 필요해요. 개발본은 확인한 폴더의 PDF 저장을 바로 시작해요.",
    "capture": "폴더 선택과 연결 결과 화면",
    "steps": [
      "Codex에 아래 문장으로 폴더 연결을 요청해요.",
      "안내받은 명령을 일반 터미널에서 실행하면 폴더 선택창이 열려요.",
      "여러 폴더를 고르려면 스페이스바 옆 ⌘ Command 키를 누른 채 폴더 이름을 한 번씩 클릭하세요. 두 번 클릭하면 바로 선택이 끝날 수 있어요.",
      "원하는 폴더들이 선택됐는지 확인한 뒤 키에서 손을 떼고, 오른쪽 아래 “선택”을 누르세요.",
      "다른 위치의 폴더도 연결한 뒤 “새로 추가된 문서를 정리해줘”라고 요청하세요."
    ],
    "note": "설치 중 폴더를 연결했다면 다시 등록할 필요 없어요. 이 안내는 공개된 v0.3.0 기준이에요. 개발본에서는 목록을 확인하고 “연결하고 PDF 저장하기”를 누르면 선택한 폴더의 PDF 저장과 시각 검토로 이어져요. 선택창만 취소하면 목록이 유지되고, 전체를 취소하면 이번 선택은 등록되지 않아요. Codex에 “@Research Agent PDF 폴더 연결창 다시 열어줘”라고 요청하는 방식도 준비 중이며, 아직 공개 버전에는 포함되지 않았어요.",
    "prompt": "@Research Agent 내 PDF가 있는 폴더들을 연결해줘.",
    "prev": "start",
    "next": "organize"
  },
  "attach": {
    "title": "PDF 첨부해서 저장하기",
    "question": "폴더를 연결하지 않고 PDF만 보내도 되나요?",
    "answer": "네. Codex 대화에 PDF를 한 개 또는 여러 개 첨부하고 Research Agent에게 저장을 요청하세요. PDF 사본과 검색용 내용이 연구 자료실에 저장되어 다음 대화에서도 찾을 수 있어요.",
    "capture": "PDF 3개를 첨부해 저장하고 문서별 요약을 받은 실제 화면이에요. 텍스트 저장은 완료됐고, 수식·표·그림 확인은 대기 중이라고 안내해요.",
    "captureAlt": "TinyBERT, MiniLM, Dense Passage Retrieval PDF 3개와 저장·요약 요청, 새 저장 완료 및 문서별 요약, 시각 검토 27쪽 대기 안내가 담긴 Codex 응답",
    "steps": [
      "Codex의 로컬 대화에 PDF를 한 개 또는 여러 개 함께 첨부해요.",
      "@research를 입력해 Research Agent를 선택하고, 아래 문장으로 첨부한 PDF의 저장과 요약을 요청해요.",
      "저장된 문서와 처리하지 못한 파일이 있는지 확인해요. 텍스트 정리가 끝나면 바로 질문을 이어가세요."
    ],
    "alternative": {"route": "organize", "label": "폴더를 연결해 두었다면: 폴더의 PDF 저장하기"},
    "note": "첨부만 하면 자동으로 저장되지는 않아요. Codex에서 첨부 파일을 읽을 수 있어야 해요. 저장을 원하지 않으면 “저장하지 말고 이번 대화에서만 설명해줘”라고 말하세요. 그림·수식·표 확인은 더 걸릴 수 있어요.",
    "prompt": "@Research Agent 첨부한 PDF들을 연구 자료실에 저장하고, 첨부한 문서의 핵심 내용을 각각 정리해줘.",
    "prev": "start",
    "next": "compare"
  },
  "organize": {
    "title": "폴더의 PDF 저장하기",
    "question": "설치할 때 연결한 폴더의 PDF는 어떻게 저장하나요?",
    "answer": "현재 배포된 v0.3.0은 연결 후 아래 문장으로 첫 저장을 요청해요. 개발본은 폴더 확인 후 저장이 시작되므로 처리 상태를 확인하면 돼요. 이후 PDF를 추가하거나 바꾸면 아래 문장으로 갱신하세요. 원본 PDF는 수정하지 않아요.",
    "capture": "연결한 폴더의 PDF 변환·저장 요청과 결과 화면",
    "steps": [
      "설치할 때 폴더를 연결했다면 다시 연결하거나 PDF를 첨부할 필요 없어요.",
      "Codex의 로컬 대화에서 Research Agent를 선택하세요. v0.3.0은 아래 문장으로 저장을 요청하고, 개발본에서 이미 시작했다면 “방금 연결한 폴더의 저장 상태를 알려줘”라고 물어보세요.",
      "결과에서 저장된 문서 수와 처리하지 못한 파일이 있는지 확인하세요. 텍스트 저장이 끝난 문서는 바로 검색할 수 있어요. 그림·수식·표는 확인 중일 수 있어요.",
      "나중에 폴더에 PDF를 추가하거나 바꿨을 때도 같은 요청을 보내세요. 새로 추가되거나 변경된 문서를 갱신해요."
    ],
    "alternative": {"route": "connect", "label": "아직 폴더를 연결하지 않았다면: PDF 폴더 연결하기"},
    "note": "아직 확인 중인 시각 자료는 검증된 결과로 취급하지 않아요. 완료·오류와 오래 걸리는 작업의 진행 상황은 macOS 알림으로 안내할 수 있어요. 알림 설정에 따라 보이지 않을 수 있고, 대화에 새 메시지가 자동으로 추가되지는 않아요. 중단 후 같은 요청을 하면 저장된 상태를 확인해 남은 작업을 이어가요.",
    "prompt": "@Research Agent 연결한 폴더 안의 PDF들을 변환해서 연구 자료실에 저장해줘. 저장된 문서와 아직 처리 중인 부분을 알려줘.",
    "prev": "start",
    "next": "compare"
  },
  "compare": {
    "title": "새 PDF와 기존 자료 함께 정리하기",
    "question": "새 PDF를 저장하면서 기존 자료와 함께 정리할 수 있나요?",
    "answer": "네. 새 PDF를 대화에 첨부하고 저장과 비교를 함께 요청하세요. 첨부한 PDF를 저장한 뒤, 이미 저장된 관련 PDF와 대화 기록을 찾아 함께 정리하고 출처를 알려줘요.",
    "capture": "새 PDF의 저장 결과와 기존 자료의 출처가 함께 보이는 응답 화면",
    "steps": [
      "비교할 기존 자료를 먼저 저장해 두세요. 폴더를 연결했다면 ‘폴더의 PDF 저장하기’에서 저장 완료 여부부터 확인해요.",
      "Codex의 로컬 대화에 새 PDF를 한 개 또는 여러 개 첨부하고 Research Agent를 선택하세요.",
      "아래 문장으로 저장과 기존 자료를 활용한 정리를 한 번에 요청하세요.",
      "답변의 출처에 새 PDF와 기존 자료가 함께 포함됐는지 확인하세요. 관련된 기존 자료를 찾지 못했다면 이번에 첨부한 문서만으로 정리했다는 안내가 나올 수 있어요."
    ],
    "alternative": {"route": "organize", "label": "연결한 폴더의 PDF부터 저장하려면"},
    "note": "저장된 자료 중 질문과 관련된 내용을 찾아 활용해요. 기존 자료가 있어도 관련 내용을 찾지 못할 수 있어요. 답변에 필요한 그림·수식·표의 확인이 아직 끝나지 않았다면 그 상태를 함께 확인하세요.",
    "prompt": "@Research Agent 첨부한 PDF들을 저장하고, 기존에 저장된 관련 자료와 함께 핵심 내용을 정리해줘. 공통점과 차이점을 설명하고, 어떤 문서에 근거했는지도 알려줘.",
    "prev": "organize",
    "next": "search"
  },
  "search": {
    "title": "자료 검색하기",
    "question": "내 PDF에서 필요한 내용을 어떻게 찾나요?",
    "answer": "찾고 싶은 내용을 평소 말하듯 질문하세요. 여러 PDF와 저장한 대화에서 관련 내용을 찾고, 근거가 있는 문서와 페이지를 함께 안내해요.",
    "capture": "질문, 답변과 출처가 보이는 실제 화면",
    "steps": [
      "연결한 폴더나 대화에 첨부한 PDF를 정리해 두세요.",
      "평소 사용하던 Codex 대화에 아래 문장을 붙여 넣고, 원하는 주제로 바꿔 질문하세요.",
      "답변에서 PDF의 근거와 저장한 내 생각을 구분해 확인하세요."
    ],
    "note": "영어 PDF에도 한국어로 질문할 수 있어요. 관련 한국어·영어 핵심어로 자료를 찾아요. 답변에 필요한 그림·수식이 아직 확인 중이면 그 상태를 함께 안내해요.",
    "prompt": "@Research Agent 내 자료에서 광소자 결합 효율을 높이는 방법을 찾아줘.",
    "prev": "compare",
    "next": "save"
  },
  "save": {
    "title": "대화 저장하기",
    "question": "지금 논의한 연구 아이디어를 나중에 다시 보고 싶어요.",
    "answer": "대화를 저장해 달라고 요청하면 먼저 저장할 범위를 물어봐요. 선택한 내용만 연구 메모로 보관하고, 나중에 PDF와 함께 찾아볼 수 있어요.",
    "capture": "저장 범위 선택과 대화 저장 결과 화면",
    "steps": [
      "저장하고 싶은 내용을 논의한 Codex 대화에서 아래 문장으로 요청해요.",
      "현재 주제, 이번 대화 전체, 직접 지정한 범위 중에서 선택해요.",
      "나중에 “지난번 실험에서 어떤 조건을 바꾸기로 했지?”처럼 질문하세요."
    ],
    "note": "모든 대화가 자동으로 저장되는 것은 아니에요. 오래된 대화의 정확한 원문을 확인할 수 없으면 그 한계도 안내해요.",
    "prompt": "@Research Agent 지금 대화에서 실험 설계에 관한 부분을 저장해줘.",
    "prev": "search",
    "next": "manage"
  },
  "manage": {
    "title": "저장한 대화 관리하기",
    "question": "저장한 기록을 수정하거나 삭제할 수도 있나요?",
    "answer": "저장한 목록을 확인한 뒤 원하는 기록의 제목·요약·태그를 수정하거나, 해당 저장 기록을 삭제해 달라고 요청할 수 있어요.",
    "capture": "저장한 대화 조회와 수정 결과 화면",
    "steps": [
      "아래 문장으로 저장한 대화 목록을 확인해요.",
      "어떤 기록을 어떻게 수정하거나 삭제할지 말해요.",
      "비슷한 기록이 여러 개라면 먼저 대상을 확인해요."
    ],
    "note": "저장 당시의 대화 원문은 수정하지 않아요. 삭제한 저장 기록은 복구할 수 없지만, 실제 Codex 대화나 원본 PDF는 지워지지 않아요.",
    "prompt": "@Research Agent 저장한 대화 목록을 보여줘.",
    "prev": "save",
    "next": "search"
  }
};
const installationCaptures={
  spotlight:{src:'assets/screenshots/spotlight-terminal-crop.png?v=20260926-unselected',width:1282,height:326},
  terminal:{src:'assets/screenshots/terminal-ready-crop.png',width:1282,height:220},
  'install-complete':{src:'assets/screenshots/install-complete-crop.png',width:840,height:140},
  'folder-selection':{src:'assets/screenshots/folder-selection-crop.png',width:442,height:145},
  'folder-draft-empty':{src:'assets/screenshots/folder-draft-empty-crop.png',width:1224,height:834,
    highlight:{x:378,y:673,width:468,height:68}},
  'folder-draft-confirmation':{src:'assets/screenshots/folder-draft-confirmation-crop.png?v=20260928-auto-save',width:1280,height:1248,
    highlight:{x:398,y:1000,width:468,height:68}},
  'codex-invocation':{src:'assets/screenshots/codex-introduction.png?v=20260928-introduction',width:1584,height:722}
};
const featureCaptures={
  attach:{src:'assets/screenshots/pdf-attachments-save.png',width:1652,height:1352}
};
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ui={ko:{guide:'사용 가이드',overview:'가이드 둘러보기',menu:'메뉴',skip:'본문으로 이동',nav:'가이드 메뉴',first:'처음이라면',features:'기능',me:'나',assistant:'Research Agent 안내',howto:'사용 방법',note:'알아두세요',previous:'이전',next:'다음',related:'관련 가이드',blank:'실제 캡처를 넣을 빈 영역',capturePending:'캡처 준비 중',copy:'복사',copied:'복사됨',manualCopy:'직접 복사',copiedNotice:'복사했어요.',failedCopy:'복사할 문장을 선택했어요. ⌘ + C 또는 Ctrl + C로 직접 복사하세요.',prompt:'Codex에서 사용할 문장',invocationLabel:'VS Code·CLI에서 사용하려면',invocationNote:'문장 앞의 @Research Agent를 $research-library로 바꾸세요. 또는 /skills에서 research-library를 선택한 뒤 요청을 입력하세요.',install:'터미널에서 실행할 설치 명령',paste:'복사한 문장을 평소 사용하던 Codex 대화에 붙여 넣으세요.',installNote:'명령을 복사해도 설치가 실행되지는 않아요. 터미널에서 직접 실행하세요.',sideNote:'사용 가이드 · v0.3.0\n실제 작업은 Codex에서 진행해요.',overviewQuestion:'Research Agent로 무엇을 할 수 있나요?',overviewAnswer:'흩어진 PDF와 중요한 연구 대화를 정리하고, 필요할 때 다시 찾아볼 수 있어요. 궁금한 기능을 선택해 보세요.',featureDescriptions:{attach:'PDF를 대화에 첨부해 바로 저장하고 질문해요.',organize:'연결한 폴더의 PDF를 변환해 검색할 수 있도록 저장해요.',compare:'새 PDF를 저장하고 기존 자료와 함께 정리해요.',search:'여러 PDF와 저장한 대화에서 관련 내용을 찾아요.',save:'연구 아이디어와 실험 설계를 선택해서 보관해요.'},startLink:'처음이라면 설치부터 시작하세요.',overviewEnd:'현재 지원 환경은 macOS의 Codex예요. 이 웹은 사용 방법을 안내합니다.',},en:{guide:'User guide',overview:'Explore the guide',menu:'Menu',skip:'Skip to content',nav:'Guide navigation',first:'Getting started',features:'Features',me:'You',assistant:'Research Agent guide',howto:'How to use it',note:'Good to know',previous:'Previous',next:'Next',related:'Related guides',blank:'Empty frame reserved for a real screenshot',capturePending:'Screenshot coming soon',copy:'Copy',copied:'Copied',manualCopy:'Copy manually',copiedNotice:'Copied to clipboard.',failedCopy:'The text is selected. Press ⌘ + C or Ctrl + C to copy it.',prompt:'Prompt to use in Codex',invocationLabel:'Using VS Code or the CLI?',invocationNote:'Replace @Research Agent at the start of the prompt with $research-library. Or choose research-library from /skills, then enter your request.',install:'Installation command for Terminal',paste:'Paste this into your usual Codex conversation.',installNote:'Copying does not install anything. Run the command yourself in Terminal.',sideNote:'User guide · v0.3.0\nActual work takes place in Codex.',overviewQuestion:'What can I do with Research Agent?',overviewAnswer:'Organize scattered PDFs and important research conversations, then find them again when you need them. Choose a feature to learn more.',featureDescriptions:{attach:'Attach PDFs in Codex to save them and ask questions.',organize:'Convert and save PDFs from your connected folders.',compare:'Save new PDFs and summarize them with existing materials.',search:'Find related information across PDFs and saved conversations.',save:'Keep selected research ideas and experiment plans.'},startLink:'New here? Start with installation.',overviewEnd:'The supported environment is Codex on macOS. This website explains how to use it.',}};
const preferences={language:'ko'};
try{
  const stored=JSON.parse(localStorage.getItem('research-guide-preferences')||'{}');
  if(['ko','en'].includes(stored?.language))preferences.language=stored.language;
}catch{}
const requestedLanguage=new URL(location.href).searchParams.get('lang');
if(['ko','en'].includes(requestedLanguage))preferences.language=requestedLanguage;
const main=document.querySelector('main');
const composer=document.querySelector('#composer-area');
const promptField=document.querySelector('#prompt');
const titleFor=route=>route==='overview'?ui[preferences.language].overview:(preferences.language==='en'?window.RESEARCH_GUIDE_EN:pages)[route].title;
const currentRoute=()=>{const key=location.hash.replace(/^#\//,'');return key==='overview'||Object.hasOwn(pages,key)?key:'overview'};
function savePreferences(){
  try{localStorage.setItem('research-guide-preferences',JSON.stringify(preferences));}catch{}
  const url=new URL(location.href);
  // Old links still open the same feature, without an environment-specific layout.
  url.searchParams.delete('environment');
  url.searchParams.set('lang',preferences.language);
  if(currentRoute()!=='start')url.searchParams.delete('step');
  if(url.href!==location.href)history.replaceState(null,'',url);
}
function renderCapture(capture, route, language){
  const t=ui[language];
  const asset=route==='start'?installationCaptures[capture.key]:featureCaptures[route];
  const caption=escapeHTML(capture.caption);
  const attributes=`data-capture-language="${language}" data-capture-feature="${route}" data-capture-key="${escapeHTML(capture.key)}"`;
  const highlight=asset?.highlight;
  const annotation=highlight?`<span class="screenshot-highlight" aria-hidden="true" style="left:${(highlight.x/asset.width*100).toFixed(4)}%;top:${(highlight.y/asset.height*100).toFixed(4)}%;width:${(highlight.width/asset.width*100).toFixed(4)}%;height:${(highlight.height/asset.height*100).toFixed(4)}%"></span>`:'';
  return asset
    ? `<figure class="screenshot"><figcaption>${caption}</figcaption><div class="screenshot-frame has-capture" style="max-width:${asset.width+2}px" ${attributes}><img src="${asset.src}" width="${asset.width}" height="${asset.height}" alt="${escapeHTML(capture.alt||capture.caption)}">${annotation}</div></figure>`
    : `<figure class="screenshot"><figcaption>${caption} · ${t.capturePending}</figcaption><div class="screenshot-frame" role="img" aria-label="${caption} — ${t.blank}" ${attributes}></div></figure>`;
}
function setComposer(kind, prompt=''){
  const t=ui[preferences.language];
  composer.classList.toggle('hidden',!kind);
  promptField.value=kind==='install'?window.RESEARCH_GUIDE_RELEASE.installCommand:prompt;
  promptField.rows=kind==='install'?5:2;
  document.querySelector('#prompt-label').textContent=kind==='install'?t.install:t.prompt;
  document.querySelector('#composer-note').textContent=kind==='install'?t.installNote:t.paste;
  const invocationHelp=document.querySelector('#invocation-help');
  invocationHelp.classList.toggle('hidden',kind!=='prompt');
  invocationHelp.open=false;
  document.querySelector('#invocation-label').textContent=t.invocationLabel;
  document.querySelector('#invocation-note').textContent=t.invocationNote;
}
function renderInstallationCopy(stage,t){
  if(!stage.composer)return '';
  const isInstall=stage.composer==='install';
  const text=isInstall?window.RESEARCH_GUIDE_RELEASE.installCommand:stage.prompt;
  return `<div class="installation-copy" role="group" aria-labelledby="installation-copy-label">
    <div class="installation-copy-box">
      <div class="installation-copy-header"><p id="installation-copy-label">${isInstall?t.install:t.prompt}</p><button type="button" data-copy-installation>${t.copy}</button></div>
      <pre id="installation-copy-text" class="installation-copy-text${isInstall?' is-command':''}" tabindex="0" aria-labelledby="installation-copy-label">${escapeHTML(text)}</pre>
    </div>
    <p class="installation-copy-note">${isInstall?t.installNote:t.paste}</p>
    ${isInstall?'':`<details class="invocation-help"><summary>${t.invocationLabel}</summary><p>${t.invocationNote}</p></details>`}
  </div>`;
}
function renderInstallation(page, t, language){
  const requested=Number(new URL(location.href).searchParams.get('step'));
  const step=Number.isInteger(requested)&&requested>=1&&requested<=page.stages.length?requested:1;
  const stage=page.stages[step-1];
  setComposer(null);
  const previous=step>1
    ? `<button type="button" data-install-step="${step-1}">${page.back}</button>`
    : `<a href="#/overview">${t.overview}</a>`;
  const next=step<page.stages.length
    ? `<button type="button" data-install-step="${step+1}">${page.forward}: ${escapeHTML(page.stages[step].label)}</button>`
    : '';
  main.innerHTML=`<div class="conversation installation-guide">
    <nav aria-label="${page.stageNav}" class="installation-nav"><ol>${page.stages.map((s,i)=>`<li><button type="button" data-install-step="${i+1}"${step===i+1?' aria-current="step"':''}><span>${i+1}.</span> ${escapeHTML(s.label)}</button></li>`).join('')}</ol></nav>
    <div class="message user-message"><p class="speaker">${t.me}</p><p class="message-text">${escapeHTML(stage.question)}</p></div>
    <div class="message assistant-message"><p class="speaker">${t.assistant}</p>
      <p class="message-text">${escapeHTML(stage.answer)}</p>
      ${step===1?`<p class="installation-requirements">${escapeHTML(page.requirements)}</p>`:''}
      ${stage.safety?`<p class="installation-requirements">${escapeHTML(stage.safety)}</p>`:''}
      ${stage.notice?`<p class="installation-requirements">${escapeHTML(stage.notice)}</p>`:''}
      ${stage.flow?stage.flow.map(item=>`<section class="installation-flow-step"><h2>${escapeHTML(item.title)}</h2><p>${escapeHTML(item.body)}</p>${renderCapture(item.capture,'start',language)}</section>`).join(''):`<ol class="installation-actions">${stage.steps.map(s=>`<li>${escapeHTML(s)}</li>`).join('')}</ol>${renderInstallationCopy(stage,t)}${stage.captures.map(c=>renderCapture(c,'start',language)).join('')}`}
      ${stage.help?`<details class="howto installation-help"><summary>${escapeHTML(stage.helpLabel)}</summary><dl>${stage.help.map(item=>`<dt>${escapeHTML(item.question)}</dt><dd>${escapeHTML(item.answer)}</dd>`).join('')}</dl></details>`:''}
      ${stage.note?`<details class="howto"><summary>${escapeHTML(stage.noteLabel)}</summary><p class="note">${escapeHTML(stage.note)}</p></details>`:''}
    </div>
    ${step===page.stages.length?`<section class="installation-flow-step"><h2>${escapeHTML(page.saveChoice)}</h2><ul class="feature-list"><li><a href="#/attach">${escapeHTML(page.firstTask)}</a></li><li><a href="#/organize">${escapeHTML(page.folderTask)}</a></li></ul></section>`:''}
    <nav class="installation-pagination" aria-label="${page.stageNav}">${previous}${next}</nav>
  </div>`;
}
function render(){
  const {language}=preferences;const t=ui[language];const route=currentRoute();const translated=language==='en'?window.RESEARCH_GUIDE_EN:pages;
  document.documentElement.lang=language;
  document.querySelectorAll('[data-language]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.language===language)));
  document.querySelector('.sidebar').setAttribute('aria-label',t.nav);
  document.querySelector('.skip-link').textContent=t.skip;
  document.querySelector('#brand-subtitle').textContent=t.guide;
  document.querySelector('.menu-toggle').textContent=t.menu;
  document.querySelector('#nav-start-label').textContent=t.first;
  document.querySelector('#nav-features-label').textContent=t.features;
  document.querySelector('.sidebar-bottom').textContent=t.sideNote;
  document.querySelector('#page-title').textContent=titleFor(route);
  document.title=`${titleFor(route)} · Research Agent ${t.guide}`;
  document.querySelectorAll('[data-route]').forEach(a=>{a.textContent=titleFor(a.dataset.route);if(a.dataset.route===route)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  document.querySelector('#guide-nav').classList.remove('is-open');
  document.querySelector('.menu-toggle').setAttribute('aria-expanded','false');
  document.querySelector('#copy-prompt').textContent=t.copy;
  document.querySelector('#live-message').textContent='';
  if(route==='overview'){
    composer.classList.add('hidden');
    main.innerHTML=`<div class="conversation overview"><div class="message user-message"><p class="speaker">${t.me}</p><p class="overview-question">${t.overviewQuestion}</p></div><div class="message assistant-message"><p class="speaker">${t.assistant}</p><p class="message-text">${t.overviewAnswer}</p><ul class="feature-list">${['attach','organize','compare','search','save'].map(key=>`<li><a href="#/${key}">${titleFor(key)}</a><p>${t.featureDescriptions[key]}</p></li>`).join('')}</ul><div class="overview-start"><a href="#/start">${t.startLink}</a><p>${t.overviewEnd}</p></div></div></div>`;
  }else if(route==='start'){
    renderInstallation(translated.start,t,language);
  }else{
    const p={...translated[route],steps:[...translated[route].steps]};
    const captureFigures=renderCapture({key:route,caption:p.capture,alt:p.captureAlt},route,language);
    setComposer('prompt',p.prompt);
    main.innerHTML=`<div class="conversation"><div class="message user-message"><p class="speaker">${t.me}</p><p class="message-text">${escapeHTML(p.question)}</p></div><div class="message assistant-message"><p class="speaker">${t.assistant}</p><p class="message-text">${escapeHTML(p.answer)}</p>${captureFigures}<details class="howto" open><summary>${t.howto}</summary><ol>${p.steps.map(s=>`<li>${escapeHTML(s)}</li>`).join('')}</ol></details>${p.alternative?`<p class="note"><a href="#/${escapeHTML(p.alternative.route)}">${escapeHTML(p.alternative.label)}</a></p>`:''}<details class="howto"><summary>${t.note}</summary><p class="note">${escapeHTML(p.note)}</p></details></div><nav class="related" aria-label="${t.related}"><a href="#/${p.prev}">${t.previous}: ${titleFor(p.prev)}</a><a href="#/${p.next}">${t.next}: ${titleFor(p.next)}</a></nav></div>`;
  }
  main.scrollTo({top:0,behavior:'instant'});
}
function syncPreferencesFromURL(){
  const language=new URL(location.href).searchParams.get('lang');
  if(['ko','en'].includes(language))preferences.language=language;
  savePreferences();
}
window.addEventListener('popstate',()=>{syncPreferencesFromURL();render()});
window.addEventListener('hashchange',()=>{syncPreferencesFromURL();render();main.focus({preventScroll:true})});
main.addEventListener('click',event=>{
  const copyButton=event.target.closest('[data-copy-installation]');
  if(copyButton){
    const text=main.querySelector('#installation-copy-text');
    copyGuideText(text.textContent,copyButton,()=>{
      text.focus();
      const range=document.createRange();
      range.selectNodeContents(text);
      const selection=window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    });
    return;
  }
  const button=event.target.closest('[data-install-step]');
  if(!button||currentRoute()!=='start')return;
  const url=new URL(location.href);
  url.searchParams.set('step',button.dataset.installStep);
  history.pushState(null,'',url);
  render();
  main.focus({preventScroll:true});
});
document.querySelector('.menu-toggle').addEventListener('click',function(){const open=this.getAttribute('aria-expanded')!=='true';this.setAttribute('aria-expanded',String(open));document.querySelector('#guide-nav').classList.toggle('is-open',open)});
document.querySelector('.skip-link').addEventListener('click',e=>{e.preventDefault();main.focus()});
document.querySelectorAll('[data-language]').forEach(button=>button.addEventListener('click',()=>{preferences.language=button.dataset.language;savePreferences();render();}));
async function copyGuideText(text,button,selectText){
  const t=ui[preferences.language];
  try{
    await navigator.clipboard.writeText(text);
    button.textContent=t.copied;
    document.querySelector('#live-message').textContent=t.copiedNotice;
  }catch{
    selectText();
    button.textContent=t.manualCopy;
    document.querySelector('#live-message').textContent=t.failedCopy;
  }
}
document.querySelector('#copy-prompt').addEventListener('click',function(){copyGuideText(promptField.value,this,()=>{promptField.focus();promptField.select();});});
savePreferences();
render();
