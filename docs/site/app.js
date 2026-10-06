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
        "answer": "아래 명령으로 v0.4.1 사전 출시 버전을 설치해요. 처음 설치할 때 한 번만 실행하세요.",
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
        "flow": [
          {
            "title": "1. 폴더 추가하기",
            "body": "‘연결할 폴더’ 창에서 “폴더 추가하기”를 누르세요.",
            "capture": {"key": "folder-draft-empty", "caption": "이번에 추가할 폴더를 고르는 빈 목록이에요. “폴더 추가하기”를 누르세요. 검은 테두리는 가이드용 표시예요.", "alt": "이번에 추가할 폴더가 아직 없는 연결할 폴더 창과 폴더 추가하기 버튼, 비활성 연결하고 PDF 저장하기 버튼"}
          },
          {
            "title": "2. 원하는 폴더 고르기",
            "body": "선택창을 한 번 클릭한 뒤, 스페이스바 옆 ⌘ Command 키를 누른 채 폴더 이름을 한 번씩 클릭하세요. 원하는 폴더들이 선택되면 키에서 손을 떼고 “목록에 추가”를 누르세요.",
            "capture": {"key": "folder-selection", "caption": "폴더 3개를 함께 선택한 예시예요. 선택을 마쳤으면 오른쪽 아래 “목록에 추가”를 누르세요. 검은 테두리는 가이드용 표시예요.", "alt": "바탕화면의 폴더 3개가 함께 선택된 macOS 폴더 선택창. 3 items와 3 folders 표시, Command 다중 선택 안내와 오른쪽 아래 목록에 추가 버튼이 보임"}
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
          {"question": "폴더를 다 고르기 전에 창을 닫았어요.", "answer": "안쪽 선택창에서 “취소”했다면 앞서 체크한 폴더들이 남아 있어요. “폴더 더 추가하기”로 이어가세요. 확인 목록 전체를 취소했다면 이번 선택은 저장되지 않아요. Codex에 “@Research Agent PDF 폴더 연결창 다시 열어줘”라고 요청하세요. 새 빈 목록에서 다시 고르면 돼요."},
          {"question": "여러 폴더가 선택되지 않거나 오류가 나요.", "answer": "선택창을 한 번 클릭한 뒤 ⌘ 키를 누르고 폴더 이름을 한 번씩 클릭해 보세요. 두 번 클릭하면 선택이 끝날 수 있어요. 오류가 계속되면 표시된 메시지를 Codex에 알려주세요. 해결을 위해 Full access로 바꾸지는 마세요."},
          {"question": "연결했는데 저장이 시작되지 않았어요.", "answer": "연결 완료와 PDF 저장 완료는 다른 상태예요. Codex 실행기를 찾지 못하면 연결을 유지하고 저장이 보류돼요. Codex에 저장 상태를 확인하고 이어서 저장해 달라고 요청하세요. 본문은 저장됐지만 시각 검토만 시작하지 못했다면 검토 상태 확인과 재개를 요청하세요. 이전에 전체 검토를 멈췄다면 전체 시각 검토 재개를 요청해야 해요."},
          {"question": "안내와 다른 창이 보여요.", "answer": "이전 버전을 설치했다면 버튼과 순서가 다를 수 있어요. 표시된 화면이나 메시지를 Codex에 알려주세요. 현재 설치 명령은 새 설치용이며 기존 설치를 덮어쓰지 않아요. 업데이트를 위해 연구 자료실을 삭제하지 마세요."}
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
    "answer": "PDF를 옮길 필요 없어요. Codex에 연결창을 열어 달라고 요청하고, 원래 있는 폴더들을 목록에 모으세요. 확인 후 “연결하고 PDF 저장하기”를 누르면 선택한 폴더의 PDF 저장과 시각 검토로 이어져요.",
    "captures": [
      {
        "key": "folder-draft-empty",
        "caption": "이번에 추가할 폴더를 고르는 빈 목록이에요. 먼저 “폴더 추가하기”를 누르세요. 검은 테두리는 가이드용 표시예요.",
        "alt": "이번에 추가할 폴더가 아직 없는 연결할 폴더 목록과 폴더 추가하기 버튼, 비활성 연결하고 PDF 저장하기 버튼"
      },
      {
        "key": "folder-selection",
        "caption": "폴더 3개를 함께 선택한 예시예요. 오른쪽 아래 “목록에 추가”로 확인 목록에 넣어요. 검은 테두리는 가이드용 표시예요.",
        "alt": "바탕화면의 폴더 3개가 함께 선택된 macOS 폴더 선택창. 3 items와 3 folders 표시, Command 다중 선택 안내와 오른쪽 아래 목록에 추가 버튼이 보임"
      },
      {
        "key": "folder-draft-confirmation",
        "caption": "목록을 확인하고 “연결하고 PDF 저장하기”를 눌러요. 검은 테두리는 가이드용 표시예요.",
        "alt": "세 폴더가 체크된 확인 목록과 연결하고 PDF 저장하기 버튼"
      }
    ],
    "steps": [
      "Codex에서 Research Agent를 선택하고 아래 문장으로 폴더 연결을 요청하세요.",
      "열린 “연결할 폴더” 창에서 “폴더 추가하기”를 누르세요.",
      "선택창을 한 번 클릭한 뒤 ⌘ Command 키를 누른 채 폴더 이름을 한 번씩 클릭하세요. 선택한 뒤 “목록에 추가”를 누르세요.",
      "잘못 고른 폴더는 확인 목록에서 체크를 해제하세요. 다른 위치의 폴더도 고르려면 “폴더 더 추가하기”를 누르세요.",
      "“연결하고 PDF 저장하기”를 누르고, Codex 답변에서 저장 결과와 시각 검토 상태를 확인하세요."
    ],
    "note": "설치 중 연결한 폴더는 다시 연결할 필요 없어요. 원본 폴더와 PDF는 수정하지 않아요. 안쪽 선택창을 취소하면 체크 목록이 유지되고, 전체 확인창을 취소하면 이번 선택은 저장되지 않아요. 창을 닫았다면 “@Research Agent PDF 폴더 연결창 다시 열어줘”라고 요청해 새 목록에서 다시 고르세요.",
    "prompt": "@Research Agent 내 PDF가 있는 폴더들을 연결해줘.",
    "prev": "start",
    "next": "organize"
  },
  "attach": {
    "title": "PDF 첨부해서 저장하기",
    "question": "폴더를 연결하지 않고 PDF만 보내도 되나요?",
    "answer": "네. PDF를 한 개 또는 여러 개 첨부하고 저장과 요약을 요청하세요. 본문이 저장되면 바로 질문할 수 있고, 필요한 수식·표·그림은 이어서 백그라운드에서 확인해요. 검토가 진행되는 동안에도 대화를 계속할 수 있어요.",
    "capture": "PDF 3개의 저장·텍스트 변환과 문서별 요약을 확인할 수 있는 실제 화면이에요. 시각 검토는 DistilBERT가 끝났고, Sentence-BERT와 SimCSE는 남은 페이지를 백그라운드에서 확인 중이라고 안내해요.",
    "captureAlt": "DistilBERT, Sentence-BERT, SimCSE PDF 3개와 저장·요약 요청, 저장·텍스트 변환 완료 및 문서별 요약, DistilBERT 검토 완료와 나머지 두 문서의 일부 페이지 검토 진행을 안내하는 Codex 응답",
    "followUp": {
      "title": "시각 검토 결과 확인하기",
      "explanation": "저장 답변에서 검토 중이라고 안내받았다면, 나중에 같은 대화에서 결과를 물어보세요. 확인한 페이지와 아직 확인하지 못한 부분을 함께 살펴볼 수 있어요.",
      "prompt": "@Research Agent 방금 첨부한 PDF 3개의 시각 검토 결과를 알려줘. 확인하지 못한 부분이 있다면 문서와 페이지, 이유도 알려줘.",
      "result": "‘검토 대상 확인 완료’는 PDF의 모든 페이지를 눈으로 확인했다는 뜻은 아니에요. 아래 사례에는 자동 검토 대상에 포함되지 않아 확인 기록이 없는 페이지도 있어요. 그 페이지의 수식·표·그림이 필요하면 문서명과 페이지를 지정해 추가로 확인해 달라고 요청하세요.",
      "capture": "검토 대상으로 지정된 24쪽은 모두 확인됐고, 대기·판독 실패는 없다고 안내해요. Sentence-BERT 2쪽과 SimCSE 10–12쪽은 자동 검토 대상에 포함되지 않아 확인 기록이 없으며, 제외 이유도 현재 기록만으로는 알 수 없다고 설명해요.",
      "captureAlt": "첨부 PDF 3개의 시각 검토 결과를 묻는 요청과 검토 대상 24쪽 완료 응답. DistilBERT 1–4쪽, Sentence-BERT 1쪽과 3–8쪽, SimCSE 1–9쪽과 13–16쪽 확인. 나머지 4쪽은 자동 대상에 포함되지 않아 확인 기록과 구체적인 제외 이유가 없다는 안내"
    },
    "steps": [
      "Codex의 로컬 대화에 PDF를 한 개 또는 여러 개 함께 첨부해요.",
      "@research를 입력해 Research Agent를 선택하고, 아래 문장으로 첨부한 PDF의 저장과 요약을 요청해요.",
      "답변에서 저장된 문서와 실패한 파일, 시각 검토가 시작됐는지 확인해요. 본문 저장이 끝나면 먼저 질문을 이어가세요.",
      "수식·표·그림의 세부 내용을 사용하려면 검토 결과를 확인해요. ‘첨부한 PDF의 시각 검토 결과를 알려줘’라고 물어볼 수 있어요."
    ],
    "alternative": {"route": "organize", "label": "폴더를 연결해 두었다면: 폴더의 PDF 저장하기"},
    "note": "Codex에서 첨부 파일을 읽을 수 있어야 해요. 첨부만 하면 저장되지 않지만 Research Agent에게 그 PDF로 요약·비교를 요청하면 함께 저장돼요. 원하지 않으면 “저장하지 말고 이번 대화에서만 설명해줘”라고 말하세요. 저장한 자료는 다음 대화에서도 찾을 수 있어요.",
    "helpLabel": "검토가 시작되지 않거나, 잠시 멈추고 싶다면?",
    "help": [
      {"question": "‘대기 중’이거나 시작하지 못했다고 나오면?", "answer": "대기는 검토가 진행 중이라는 뜻이 아니에요. 답변에 표시된 이유를 확인하고 “첨부한 PDF의 시각 검토가 시작됐는지 확인하고, 시작하지 못했다면 이유를 알려줘”라고 요청하세요. 확인하지 못한 수식·표·그림은 검토 완료로 취급하지 않아요. 추가 검토가 필요하면 필요한 문서와 페이지만 다시 확인해 달라고 요청하세요."},
      {"question": "시간이 오래 걸리거나 사용량이 부담된다면?", "answer": "“이 PDF의 시각 검토를 잠시 멈춰줘”라고 요청하세요. 저장된 본문은 계속 사용할 수 있어요. 나중에 “이 PDF의 시각 검토를 이어서 해줘”라고 요청하면 돼요. 전체 시각 검토를 멈췄다면 “자료실 전체의 시각 검토를 재개해줘”라고 요청하세요. 시간·페이지 안내 기준을 정해도 자동 중단하지 않으며 중단은 직접 결정해요."}
    ],
    "prompt": "@Research Agent 첨부한 PDF들을 연구 자료실에 저장하고, 첨부한 문서의 핵심 내용을 각각 정리해줘.",
    "prev": "start",
    "next": "compare"
  },
  "organize": {
    "title": "폴더의 PDF 저장하기",
    "question": "연결한 폴더의 PDF가 저장됐는지 어떻게 확인하나요?",
    "answer": "폴더 확인창에서 “연결하고 PDF 저장하기”를 누르면 저장이 시작돼요. 아래 문장으로 저장 결과와 시각 검토 상태를 확인하세요. 본문 저장과 시각 검토 완료는 따로 확인해요. 원본 PDF는 수정하지 않아요.",
    "capture": "저장 후 상태를 확인한 실제 화면이에요. 폴더 3개의 PDF 9개가 저장됐고, 시각 검토는 7개 문서가 완료됐어요. 나머지 2개는 각각 1쪽씩 추가 검토가 필요하며, 진행 중인 검토 작업은 없다고 안내해요.",
    "captureAlt": "연결한 폴더의 저장 결과와 시각 검토 상태를 묻는 질문, PDF 9개 저장·실패 없음, 7개 문서 시각 검토 완료·2개 문서 각 1쪽 추가 검토 필요·실행 중인 검토 없음이라는 Codex 응답",
    "steps": [
      "설치할 때 폴더를 연결했다면 다시 연결하거나 PDF를 첨부할 필요 없어요.",
      "Codex의 로컬 대화에서 Research Agent를 선택하고 아래 문장으로 저장 결과를 물어보세요.",
      "저장된 문서 수와 처리하지 못한 파일을 확인하세요. 텍스트 저장이 끝난 문서는 바로 검색할 수 있어요.",
      "시각 검토가 진행 중인지, 추가 확인이 필요한 문서·페이지가 있는지 따로 확인하세요. 남은 부분은 아래 안내에 따라 요청하세요."
    ],
    "alternative": {
      "route": "connect",
      "label": "아직 폴더를 연결하지 않았다면: PDF 폴더 연결하기"
    },
    "note": "아직 확인 중인 시각 자료는 검증된 결과로 취급하지 않아요. 시작·완료·추가 확인·오류와 오래 걸리는 작업의 진행 상황은 macOS 알림으로 안내할 수 있어요. 알림 설정에 따라 보이지 않을 수 있고, 대화에 새 메시지가 자동으로 추가되지는 않아요. 전체 시각 검토를 멈췄다면 새 저장 후에도 멈춘 상태가 유지돼요. 계속하려면 전체 검토 재개를 요청하세요.",
    "prompt": "@Research Agent 연결한 폴더의 PDF 저장 결과와 시각 검토 상태를 간단히 알려줘.",
    "prev": "start",
    "next": "compare",
    "followUps": [
      {
        "key": "organize-refresh",
        "title": "폴더에 PDF를 추가하거나 바꿨다면",
        "explanation": "폴더를 계속 감시해 자동으로 갱신하지는 않아요. PDF를 새로 넣거나 수정한 뒤에는 아래 문장으로 갱신을 요청하세요. 연결한 위치에서 새로 추가되거나 바뀐 문서를 처리해요.",
        "prompt": "@Research Agent 연결한 폴더에서 새로 추가되거나 변경된 PDF만 정리하고, 저장 결과와 시각 검토 상태를 알려줘. 새로 저장한 문서 이름과 변경 없이 유지한 문서 수도 간단히 알려줘.",
        "result": "이미 연결한 폴더는 다시 고를 필요 없어요. 새 폴더라면 먼저 연결하세요. 답변에서 새로 저장한 문서와 기존 문서 유지 여부, 실패·검토 상태를 확인하세요. 시각 검토의 페이지 수는 답변에 표시된 범위도 함께 확인하세요.",
        "captures": [
          {
            "key": "organize-refresh-request",
            "caption": "1. 연결한 폴더에서 새·변경 PDF만 정리하고, 새로 저장한 문서 이름과 기존 문서 유지 수도 알려 달라고 요청해요.",
            "alt": "Research Agent에 연결한 폴더의 새로 추가되거나 변경된 PDF만 정리하고, 저장 결과·시각 검토 상태·새로 저장한 문서 이름·변경 없이 유지한 문서 수를 알려 달라고 요청한 한국어 화면"
          },
          {
            "key": "organize-refresh-result",
            "caption": "2. FastBERT·BERT-of-Theseus·SqueezeBERT 3개를 새로 저장하고 기존 9개를 유지했다고 안내해요. 저장 실패·원본 누락은 없고, 현재 요청 범위에서 시각 검토 109쪽 완료·8쪽 진행/대기이며 백그라운드 검토가 계속된다고 보고해요.",
            "alt": "PDF 3개 새 저장 응답: FastBERT, BERT-of-Theseus, SqueezeBERT. 기존 9개 변경 없이 유지, 저장 실패와 원본 누락 없음. 현재 요청 범위에서 109쪽 검증 완료, 8쪽 진행·대기, 추가 확인이 필요한 페이지는 없으며 백그라운드 검토가 계속된다는 한국어 안내"
          }
        ]
      },
      {
        "key": "organize-review-controls",
        "title": "시각 검토를 잠시 멈추고 이어서 하려면",
        "explanation": "시간이 오래 걸리거나 사용량이 부담되면 검토할 문서를 지정해 잠시 멈춰 달라고 요청하세요. 저장한 본문은 계속 사용할 수 있어요. 폴더에서 저장한 PDF와 대화에 첨부한 PDF 모두 같은 방식으로 요청해요. 아래 문서 이름은 내 PDF에 맞게 바꾸세요.",
        "result": "전체 자료실의 검토를 멈춘 경우에는 개별 문서를 재개해도 전체 보류가 해제되지 않아요. 계속하려면 “자료실 전체의 시각 검토를 재개해줘”라고 요청하세요. 시간·페이지 안내 기준에 도달해도 자동으로 멈추지 않으며, 중단은 직접 결정해요.",
        "followUps": [
          {
            "key": "review-control-store",
            "title": "1. 저장과 검토 시작 확인",
            "explanation": "아래는 새 PDF 3개를 대화에 첨부한 예시예요. 이미 저장한 PDF라면 다시 첨부하거나 저장할 필요 없이 검토 상태부터 확인하세요.",
            "prompt": "@Research Agent 첨부한 ALBERT, ELECTRA, DeBERTa PDF 3개를 연구 자료실에 저장해줘. 텍스트 저장 결과와 시각 검토가 시작됐는지를 간단히 알려줘.",
            "result": "본문 저장과 검토 시작을 따로 확인해요. 다음 일시 정지 요청은 시각 검토가 진행 중일 때 보내세요.",
            "captures": [
              {
                "key": "review-control-store-request",
                "caption": "ALBERT·ELECTRA·DeBERTa PDF 3개를 첨부하고 저장 결과와 시각 검토 시작 여부를 요청해요.",
                "alt": "ALBERT, ELECTRA, DeBERTa PDF 첨부 3개와 연구 자료실 저장·텍스트 저장 결과·시각 검토 시작 여부를 요청한 한국어 화면"
              },
              {
                "key": "review-control-store-result",
                "caption": "세 문서의 본문 저장 완료·실패 없음과 백그라운드 시각 검토 시작·진행 중을 안내해요.",
                "alt": "ALBERT, ELECTRA, DeBERTa PDF 3개 저장과 텍스트 추출·저장 완료, 실패한 파일 없음, 백그라운드 시각 검토가 시작되어 진행 중이라는 한국어 응답"
              }
            ]
          },
          {
            "key": "review-control-pause",
            "title": "2. 지정한 문서의 검토 잠시 멈추기",
            "explanation": "멈출 문서와 유지할 내용을 알려 주세요. 답변에서 실제로 멈췄는지 확인해요. “중단 중”은 아직 중단 완료가 아니에요.",
            "prompt": "@Research Agent ALBERT, ELECTRA, DeBERTa 세 문서의 시각 검토만 잠시 멈춰줘. 저장된 본문과 완료된 검토 결과는 유지하고, 실제로 멈췄는지와 남은 검토 상태를 알려줘.",
            "result": "이 예시는 세 문서만 멈춘 경우예요. 저장한 본문과 이미 확인한 내용은 유지하고, 나머지 검토는 재개할 때 이어가요.",
            "captures": [
              {
                "key": "review-control-pause-request",
                "caption": "세 문서의 시각 검토만 멈추고, 저장된 본문·완료된 검토 결과를 유지해 달라고 요청해요.",
                "alt": "ALBERT, ELECTRA, DeBERTa 세 문서의 시각 검토만 잠시 멈추고 저장된 본문과 완료된 검토 결과를 유지하며 실제 중단 여부와 남은 상태를 알려 달라는 한국어 요청"
              },
              {
                "key": "review-control-pause-result",
                "caption": "실행 프로세스 종료까지 확인했다고 안내해요. ALBERT는 4쪽 확인·6쪽 남음, ELECTRA는 13쪽, DeBERTa는 16쪽이 남았어요. 저장된 내용은 유지됐고 다른 문서의 검토에는 영향을 주지 않았다고 보고해요.",
                "alt": "세 문서 시각 검토 일시 정지와 실행 프로세스 실제 종료 확인, 저장된 본문·완료된 검토 결과 유지. ALBERT 4쪽 검토 완료·6쪽 남음, ELECTRA 0쪽 완료·13쪽 남음, DeBERTa 0쪽 완료·16쪽 남음. 당시 실패나 추가 확인 페이지 없음, 다른 문서 검토에 영향 없음이라는 한국어 응답"
              }
            ]
          },
          {
            "key": "review-control-resume",
            "title": "3. 남은 시각 검토 이어가기",
            "explanation": "멈췄던 문서의 이름을 말하고 남은 검토를 이어서 해 달라고 요청해요. 완료된 검토 결과는 유지해요.",
            "prompt": "@Research Agent ALBERT, ELECTRA, DeBERTa 세 문서의 남은 시각 검토를 이어서 해줘. 완료된 검토 결과는 유지하고, 재개 여부를 간단히 알려줘.",
            "result": "재개는 전체 완료와 다른 상태예요. 백그라운드 검토가 이어지는 동안 저장한 본문으로 질문을 계속할 수 있어요.",
            "captures": [
              {
                "key": "review-control-resume-request",
                "caption": "같은 세 문서의 완료된 결과를 유지하고 남은 시각 검토만 이어서 해 달라고 요청해요.",
                "alt": "ALBERT, ELECTRA, DeBERTa 세 문서의 남은 시각 검토를 이어서 하고 완료된 결과를 유지하며 재개 여부를 알려 달라는 한국어 요청"
              },
              {
                "key": "review-control-resume-result",
                "caption": "남은 검토가 백그라운드에서 재개됐고, 본문·기존 결과를 유지하며 실패 없이 진행 중이라고 안내해요.",
                "alt": "ALBERT, ELECTRA, DeBERTa 남은 시각 검토 백그라운드 재개, 저장된 본문과 기존 검토 결과 유지, 현재 실패 없이 진행 중이라는 한국어 응답"
              }
            ]
          },
          {
            "key": "review-control-status",
            "title": "4. 현재 상태와 남은 부분 확인",
            "explanation": "나중에 검토 상태를 물어보고 진행·대기 중인 부분과 추가 확인이 필요한 부분을 구분하세요. 아래 화면은 아직 모두 완료된 상태가 아니에요.",
            "prompt": "@Research Agent ALBERT, ELECTRA, DeBERTa 세 문서의 시각 검토 결과를 알려줘. 아직 진행 중이거나 추가 확인이 필요한 부분이 있다면 문서 이름과 페이지, 이유도 알려줘.",
            "result": "완료 수의 분모는 시각 검토 대상으로 선정된 페이지 수이며 PDF 전체 쪽수와 달라요. ALBERT 10쪽처럼 추가 확인이 필요한 페이지는 아래 “추가 검토가 필요하다고 나오면?”에 따라 다시 확인을 요청하세요. 진행·대기는 오류가 확정됐다는 뜻이 아니에요.",
            "captures": [
              {
                "key": "review-control-status-request",
                "caption": "세 문서의 현재 검토 결과와 남은 문서·페이지·이유를 요청해요.",
                "alt": "ALBERT, ELECTRA, DeBERTa 세 문서의 시각 검토 결과와 아직 진행 중이거나 추가 확인이 필요한 문서 이름·페이지·이유를 알려 달라는 한국어 요청"
              },
              {
                "key": "review-control-status-result",
                "caption": "검토 대상으로 선정된 페이지 기준으로 ALBERT는 9/10쪽 확인·10쪽 추가 확인, ELECTRA는 8/13쪽, DeBERTa는 8/16쪽 확인 상태예요. 나머지는 진행·대기 중이며, ALBERT 10쪽의 표 열 정렬과 OCR 문제에 추가 확인이 필요하다고 안내해요.",
                "alt": "현재 검토 상태 한국어 응답. 선정된 시각 검토 대상 기준 ALBERT 9/10쪽 확인·10쪽 추가 확인 필요, ELECTRA 8/13쪽 확인·14–18쪽 대기 또는 진행, DeBERTa 8/16쪽 확인·16–23쪽 대기 또는 진행. ALBERT 10쪽 Table 10의 UPM 행 RACE 열의 대시가 추출문에서 누락된 문제와 evaluation benchmark OCR 인식 문제는 추가 확인 사유. 본문·완료 결과 유지, 실행 실패는 보고되지 않음. 모든 검토 완료 화면은 아님"
              }
            ]
          }
        ]
      },
      {
        "title": "추가 검토가 필요하다고 나오면?",
        "explanation": "PDF는 저장됐지만 그림·수식·표에 아직 확인하지 못한 부분이 있다는 뜻이에요. 기다리기만 하면 자동으로 반복 검토되지는 않아요. Codex에 필요한 페이지만 다시 확인해 달라고 요청하세요.",
        "prompt": "@Research Agent 추가 검토가 필요한 문서와 페이지를 확인하고, 그 부분만 다시 검토해서 결과를 저장해줘. 끝나면 문서명과 페이지별로 완료 여부를 알려주고, 여전히 확인하지 못한 부분은 이유도 설명해줘.",
        "result": "“검토 중”이라는 답변을 받았다면 대화를 계속해도 돼요. 이후 “방금 요청한 추가 검토 결과를 알려줘”라고 물어보세요. 결과에서 어느 문서의 몇 쪽이 확인됐는지 살펴보세요. 여전히 확인하기 어려운 부분은 이유와 함께 남을 수 있어요. 그 내용이나 수치를 검증 완료로 받아들이지 말고, 안내된 원본 페이지를 확인하세요. 이미 저장한 PDF와 확인이 끝난 내용은 그대로 사용할 수 있어요.",
        "capture": "추가 검토를 요청한 뒤 받은 실제 답변이에요. BERT 15쪽과 Auto-Encoding Variational Bayes 14쪽을 다시 확인해 저장했고, 남은 검토나 실패는 없다고 안내해요.",
        "captureAlt": "추가 검토가 필요한 페이지만 다시 확인해 저장해 달라는 요청과, BERT 15쪽·Auto-Encoding Variational Bayes 14쪽의 검토와 저장 완료, 대기·미해결·실패 각 0쪽이라는 Codex 응답",
        "key": "organize-review"
      }
    ]
  },
  "compare": {
    "title": "새 PDF와 기존 자료 함께 정리하기",
    "question": "새 PDF를 저장하면서 기존 자료와 함께 정리할 수 있나요?",
    "answer": "네. 새 PDF를 대화에 첨부하고 저장과 비교를 함께 요청하세요. 첨부한 PDF를 저장한 뒤, 이미 저장된 관련 PDF와 대화 기록을 찾아 함께 정리하고 출처를 알려줘요.",
    "captures": [
      {
        "key": "compare-request",
        "caption": "1. 새 PDF 3개를 첨부하고, 기존 자료와 함께 정리해 달라고 요청한 화면이에요.",
        "alt": "MobileBERT, ConSERT, DeCLUTR PDF 3개를 첨부하고 Research Agent에 저장·비교와 새 문서 및 기존 문서의 출처 구분을 요청한 화면"
      },
      {
        "key": "compare-result",
        "caption": "2. 새로 저장한 MobileBERT·ConSERT·DeCLUTR를 요약하고, 기존 DistilBERT·Sentence-BERT·SimCSE를 출처로 연결한 응답이에요. 이 응답에서는 저장·텍스트 추출과 검토 대상 페이지의 확인을 마쳤다고 안내해요.",
        "alt": "새 PDF 3개의 저장·텍스트 추출과 검토 대상 페이지 확인 완료 안내, 문서별 요약, 기존 DistilBERT·Sentence-BERT·SimCSE를 인용한 공통점·차이점 비교와 논문별 수치를 직접 비교할 수 없다는 설명"
      }
    ],
    "steps": [
      "비교할 기존 자료를 먼저 저장해 두세요. 폴더를 연결했다면 ‘폴더의 PDF 저장하기’에서 저장 완료 여부부터 확인해요.",
      "Codex의 로컬 대화에 새 PDF를 한 개 또는 여러 개 첨부하고 Research Agent를 선택하세요.",
      "아래 문장으로 저장과 기존 자료를 활용한 정리를 한 번에 요청하세요.",
      "답변의 출처에 새 PDF와 기존 자료가 함께 포함됐는지 확인하세요. 관련된 기존 자료를 찾지 못했다면 이번에 첨부한 문서만으로 정리했다는 안내가 나올 수 있어요."
    ],
    "alternative": {"route": "organize", "label": "연결한 폴더의 PDF부터 저장하려면"},
    "note": "저장된 자료 중 질문과 관련된 내용을 찾아 활용해요. 기존 자료가 있어도 관련 내용을 찾지 못할 수 있어요. 답변에 필요한 그림·수식·표의 확인이 아직 끝나지 않았다면 그 상태를 함께 확인하세요.",
    "prompt": "@Research Agent 첨부한 PDF들을 저장하고, 기존에 저장된 관련 자료와 함께 핵심 내용을 정리해줘. 공통점과 차이점을 설명하고, 새 문서와 기존 문서 중 어떤 자료에 근거했는지도 알려줘.",
    "prev": "organize",
    "next": "search"
  },
  "search": {
    "title": "자료 검색하기",
    "question": "내 PDF에서 필요한 내용을 어떻게 찾나요?",
    "answer": "찾고 싶은 내용을 평소 말하듯 질문하세요. 여러 PDF와 저장한 대화에서 관련 내용을 찾고, 근거가 있는 문서와 페이지를 함께 안내해요.",
    "captures": [
      {
        "key": "search-request",
        "caption": "PDF를 다시 첨부하지 않고, 저장된 자료에서 BERT를 더 작고 빠르게 만드는 방법과 문서·페이지 근거를 찾아달라고 요청해요.",
        "alt": "Research Agent에 저장된 자료에서 BERT 경량화 방법을 찾아 핵심 차이와 근거 문서·페이지를 알려달라고 요청한 한국어 화면"
      },
      {
        "key": "search-result",
        "caption": "답변은 DistilBERT·MobileBERT·MiniLMv2, 양자화, 가지치기를 비교하고 문서·페이지 근거를 안내해요. 가지치기 근거는 선행 연구를 소개하는 간접 인용이라고 구분해요.",
        "alt": "BERT 경량화 방법을 비교한 한국어 답변. DistilBERT 2쪽, MobileBERT 1–4쪽, MiniLMv2 1–2쪽과 양자화·가지치기 근거를 안내하고, 가지치기는 간접 인용임을 밝혀요. 링크는 저장된 텍스트 추출본이며 페이지는 PDF 첫 장부터 센 번호라는 설명이 있어요."
      }
    ],
    "steps": [
      "연결한 폴더나 대화에 첨부한 PDF를 정리해 두세요.",
      "PDF를 다시 첨부하지 않고, 평소 사용하던 Codex 대화에 아래 문장을 붙여 넣으세요. 원하는 주제로 바꿔 질문해도 돼요.",
      "답변의 문서·페이지 근거를 확인하세요. 저장한 대화가 출처에 포함됐다면 PDF의 근거와 내 생각을 구분해 확인하세요."
    ],
    "note": "영어 PDF에도 한국어로 질문할 수 있어요. 관련 한국어·영어 핵심어로 자료를 찾아요. 문서 링크는 저장된 텍스트 추출본이며, 페이지 번호는 PDF의 첫 장부터 센 번호예요. 답변에 필요한 그림·수식이 아직 확인 중이면 그 상태를 함께 안내해요.",
    "followUp": {
      "key": "search-memory",
      "open": true,
      "title": "저장한 대화와 PDF 함께 찾아보기",
      "explanation": "실험 계획이나 선택 기준을 ‘대화 저장하기’에서 먼저 보관해 두세요. 나중에 다른 Codex 로컬 대화에서도 저장한 기록과 관련 논문을 함께 찾아 달라고 요청할 수 있어요. 대화 내용이나 PDF를 다시 첨부할 필요는 없어요.",
      "prompt": "@Research Agent 전에 저장한 DistilBERT·MobileBERT 비교 실험 계획과 내 선택 기준을 찾아줘. 관련 논문 근거도 함께 정리해줘.",
      "result": "내가 결정한 기준은 저장한 대화에서, 연구 결과는 논문에서 가져온 것인지 구분해 확인하세요. 이 예시는 저장한 계획을 다시 찾은 답변이며 실제 실험 결과는 아니에요. 구체적인 기준값은 초기 측정 후 정하기로 했다는 내용도 남아 있어요. 논문 근거의 § 표시는 페이지가 아닌 절 번호예요.",
      "captures": [
        {
          "key": "memory-search-request",
          "caption": "1. 전에 저장한 실험 계획과 선택 기준을 찾고, 관련 논문 근거도 함께 정리해 달라고 요청해요.",
          "alt": "Research Agent에 전에 저장한 DistilBERT·MobileBERT 비교 실험 계획과 선택 기준을 찾아 관련 논문 근거와 함께 정리해 달라고 요청한 한국어 화면"
        },
        {
          "key": "memory-search-selection",
          "caption": "2. 저장한 기록을 찾았다고 안내하고, 당시 직접 정한 선택 기준을 인용한 답변이에요.",
          "alt": "저장한 DistilBERT·MobileBERT 실험 계획을 찾았다는 한국어 답변. 정확도와 응답 시간 기준을 충족하는 구성 중 메모리 사용량이 가장 적은 것을 선택하고, 구체적인 기준값은 초기 측정 후 정한다는 사용자의 기준을 인용해요."
        },
        {
          "key": "memory-search-plan",
          "caption": "3. 저장한 실험 계획을 표로 정리하고, DistilBERT·MobileBERT 논문의 절 번호를 근거로 연결해요. 측정 결과와 기준값은 아직 미정이며, 논문별 가속 수치를 직접 비교하기 어렵다는 설명도 있어요.",
          "alt": "DistilBERT·MobileBERT와 FP32·INT8의 네 구성, 동일 학습 조건, Accuracy·macro-F1, 응답 시간, RAM, 입력 길이를 포함한 저장된 실험 계획 표. 초기 측정 후 성능·응답 시간 기준을 정하고 최대 RAM이 가장 작은 구성을 고른다는 순서, 아직 정하지 않은 실험 조건, DistilBERT §2–4와 MobileBERT §3 및 §4.3–4.5 근거, 같은 목표 휴대폰에서 직접 비교해야 한다는 설명이 있어요."
        }
      ]
    },
    "prompt": "@Research Agent 내 자료에서 BERT를 더 작고 빠르게 만드는 방법을 찾아줘. 방법별 핵심 차이를 간단히 정리하고, 근거가 된 문서와 페이지도 알려줘.",
    "prev": "compare",
    "next": "save"
  },
  "save": {
    "title": "대화 저장하기",
    "question": "지금 논의한 연구 아이디어를 나중에 다시 보고 싶어요.",
    "answer": "대화를 저장해 달라고 요청하면 먼저 저장할 범위를 물어봐요. 선택한 내용만 연구 메모로 보관하고, 나중에 PDF와 함께 찾아볼 수 있어요.",
    "captures": [
      {
        "key": "save-scope-choice",
        "caption": "저장 범위를 묻는 질문에 ‘이번 DistilBERT·MobileBERT 주제 (추천)’로 답한 화면이에요. 남기고 싶은 주제나 범위로 답하세요.",
        "alt": "연구 메모로 저장할 범위를 묻는 접힌 질문과 ‘이번 DistilBERT·MobileBERT 주제 (추천)’를 선택한 한국어 응답. 질문은 일부만 보이며 전체 선택지 목록은 표시되지 않아요."
      },
      {
        "key": "save-result",
        "caption": "별도의 저장 완료 예시예요. DistilBERT·MobileBERT 비교 실험 계획과 선택 기준을 저장하고, 다시 조회해 완료를 확인했다고 안내해요. 선택한 대화 원문 4개와 요약, 최종 선택 기준을 포함했다고 설명해요.",
        "alt": "DistilBERT·MobileBERT 모바일 문장 분류 비교 실험 계획과 선택 기준의 저장 및 재조회 완료를 보고한 한국어 응답. 대화 원문 4개와 요약을 포함했고, 정확도·응답 시간 기준을 충족하는 구성 중 최대 RAM을 최소화하며 구체적인 기준값은 초기 측정 후 정한다는 결정이 반영됐다고 안내해요."
      }
    ],
    "steps": [
      "실험 계획이나 아이디어를 논의하고, 남겨둘 결정과 선택 기준도 대화에 적어 두세요.",
      "그 Codex 대화에서 아래 문장으로 저장을 요청해요. 예시의 실험 주제는 내 주제로 바꿔도 돼요.",
      "저장할 범위를 묻는 질문에 현재 주제나 직접 지정한 범위로 답하세요. 이번 대화 전체는 원문을 모두 확인할 수 있을 때 선택할 수 있어요.",
      "완료 답변에서 저장한 내용과 최종 결정이 맞는지 확인해요. 나중에는 이 기록을 찾아 달라고 질문할 수 있어요."
    ],
    "alternative": {"route": "search", "label": "저장한 대화를 다시 찾아보려면"},
    "note": "모든 대화가 자동으로 저장되는 것은 아니에요. 오래된 대화의 정확한 원문을 확인할 수 없으면 그 한계도 안내해요. 저장 완료 예시의 대화 원문 4개는 이때 선택한 범위의 결과이며, 저장 가능한 개수의 제한이 아니에요.",
    "prompt": "@Research Agent 지금 논의한 DistilBERT·MobileBERT 비교 실험 계획과 내 선택 기준을 연구 메모로 저장해줘.",
    "prev": "search",
    "next": "manage"
  },
  "manage": {
    "title": "저장한 대화 관리하기",
    "question": "저장한 기록을 수정하거나 삭제할 수도 있나요?",
    "answer": "저장한 목록을 확인한 뒤 원하는 기록의 제목·요약·태그를 수정하거나, 해당 저장 기록을 삭제해 달라고 요청할 수 있어요.",
    "captures": [
      {
        "key": "manage-list",
        "caption": "저장한 대화 2건의 제목과 한국 시간 기준 저장 시각을 보여주는 응답이에요. 두 기록 모두 저장한 범위의 대화 원문이 완전히 보존됐다고 안내해요.",
        "alt": "저장한 대화 2건을 제목과 저장 시각으로 구분한 한국어 목록. 2026년 10월 1일 19시 34분의 DistilBERT·MobileBERT 비교 실험 계획과 선택 기준 재확인, 같은 날 9시 48분의 모바일 문장 분류 비교 실험 계획과 선택 기준이 있으며, 저장한 범위의 원문이 보존됐다고 안내해요."
      }
    ],
    "steps": [
      "아래 문장으로 저장한 대화 목록을 확인해요.",
      "제목과 저장 시각으로 원하는 기록을 골라요. 비슷한 기록이 여러 개라면 먼저 대상을 확인해요.",
      "고른 기록의 제목과 저장 시각을 말하고, 제목·요약·태그를 어떻게 수정할지 또는 그 기록을 삭제할지 요청해요.",
      "완료 답변에서 대상 기록과 변경 내용을 확인해요. 수정 후 목록을 다시 요청하면 바뀐 제목도 확인할 수 있어요."
    ],
    "note": "저장 당시의 대화 원문은 수정하지 않아요. 삭제한 저장 기록은 복구할 수 없지만, 실제 Codex 대화나 원본 PDF는 지워지지 않아요.",
    "prompt": "@Research Agent 저장한 대화 목록을 보여줘.",
    "followUps": [
      {
        "key": "manage-update",
        "open": true,
        "title": "제목·태그 수정하기",
        "explanation": "목록에서 고른 기록을 제목과 저장 시각으로 지정해요. 아래 예시의 제목·저장 시각과 새 제목·태그를 내 기록에 맞게 바꾸세요.",
        "prompt": "@Research Agent 2026년 10월 1일 19:34(한국 시간)에 저장한 ‘DistilBERT·MobileBERT 비교 실험 계획과 선택 기준 재확인’의 제목을 ‘DistilBERT·MobileBERT 실험 계획 재검토 메모’로 바꾸고, ‘모바일 모델 비교’ 태그를 추가해줘. 대화 원문과 기존 요약·선택 기준은 유지하고, 수정 후 다시 조회해서 결과를 알려줘.",
        "result": "완료 답변에서 바뀐 제목과 추가한 태그를 확인하세요. 이 예시는 원문·기존 요약·선택 기준·나머지 태그·원래 저장 시각을 유지했다고 안내해요.",
        "captures": [
          {
            "key": "manage-update-request",
            "caption": "제목과 저장 시각으로 기록을 지정하고, 제목 변경과 ‘모바일 모델 비교’ 태그 추가를 요청해요. 원문·기존 요약·선택 기준은 유지하고 수정 후 다시 확인하도록 요청해요.",
            "alt": "2026년 10월 1일 19시 34분에 저장한 DistilBERT·MobileBERT 비교 실험 계획과 선택 기준 재확인을 지정한 한국어 요청. 제목을 실험 계획 재검토 메모로 바꾸고 모바일 모델 비교 태그를 추가하며, 원문과 기존 요약·선택 기준을 유지하고 다시 조회해 달라고 요청해요."
          },
          {
            "key": "manage-update-result",
            "caption": "제목·태그를 수정한 뒤 다시 조회했다고 안내한 응답이에요. 원문·기존 요약·선택 기준·나머지 태그·원래 저장 시각이 유지됐다고 보고해요.",
            "alt": "수정 후 다시 조회했다고 안내한 한국어 응답. 제목은 DistilBERT·MobileBERT 실험 계획 재검토 메모, 추가 태그는 모바일 모델 비교이며, 대화 원문·기존 요약·선택 기준·나머지 태그·원래 저장 시각이 모두 유지됐다고 안내해요."
          }
        ]
      },
      {
        "key": "manage-delete",
        "open": true,
        "title": "저장 기록 삭제하기",
        "explanation": "삭제할 기록을 제목과 저장 시각으로 지정해요. 아래 예시를 내 기록에 맞게 바꾸고 대상을 확인한 뒤 요청하세요. 삭제한 저장 기록은 복구할 수 없어요. 실제 Codex 대화와 원본 PDF는 지워지지 않아요.",
        "prompt": "@Research Agent 2026년 10월 1일 19:34(한국 시간)에 저장한 ‘DistilBERT·MobileBERT 실험 계획 재검토 메모’를 삭제해줘. 삭제 후 남은 대화 목록도 보여줘. 다른 저장 기록과 실제 Codex 대화, 원본 PDF는 유지해줘.",
        "result": "완료 답변에서 삭제한 제목과 남은 목록을 확인하세요. 이 예시는 재검토 메모를 삭제하고 원래 실험 계획 기록 1건을 남겼다고 안내해요.",
        "captures": [
          {
            "key": "manage-delete-request",
            "caption": "제목과 저장 시각으로 삭제할 재검토 메모를 지정해요. 다른 저장 기록·실제 Codex 대화·원본 PDF를 유지하고 남은 목록도 보여 달라고 요청해요.",
            "alt": "2026년 10월 1일 19시 34분 한국 시간에 저장한 DistilBERT·MobileBERT 실험 계획 재검토 메모를 삭제하는 한국어 요청. 삭제 후 남은 목록을 보여주고 다른 저장 기록, 실제 Codex 대화, 원본 PDF를 유지하도록 요청해요."
          },
          {
            "key": "manage-delete-result",
            "caption": "재검토 메모를 삭제하고 다른 저장 기록·실제 Codex 대화·원본 PDF는 유지했다고 보고한 응답이에요. 삭제 후 원래 실험 계획 기록 1건이 남았다고 안내해요.",
            "alt": "재검토 메모 삭제와 다른 저장 기록, 실제 Codex 대화, 원본 PDF 보존을 보고한 한국어 응답. 다시 조회한 남은 기록은 DistilBERT·MobileBERT 모바일 문장 분류 비교 실험 계획과 선택 기준 1건이며, 한국 시간 기준 저장 시각은 2026년 10월 1일 09시 48분 55초예요."
          }
        ]
      }
    ],
    "prev": "save",
    "next": "search"
  }
};
const installationCaptures={
  spotlight:{src:'assets/screenshots/spotlight-terminal-crop.png?v=20260926-unselected',width:1282,height:326},
  terminal:{src:'assets/screenshots/terminal-ready-crop.png',width:1282,height:220},
  'install-complete':{src:'assets/screenshots/install-complete-crop.png',width:840,height:140},
  'folder-selection':{src:'assets/screenshots/folder-selection-20261006.png',width:1738,height:942,fullSize:true,
    highlight:{x:1488,y:830,width:196,height:61}},
  'folder-draft-empty':{src:'assets/screenshots/folder-draft-empty-20261006.png',width:1282,height:918,
    highlight:{x:406,y:702,width:468,height:68}},
  'folder-draft-confirmation':{src:'assets/screenshots/folder-draft-confirmation-crop.png?v=20260928-auto-save',width:1280,height:1248,
    highlight:{x:398,y:1000,width:468,height:68}},
  'codex-invocation':{src:'assets/screenshots/codex-introduction.png?v=20260928-introduction',width:1584,height:722}
};
const featureCaptures={
  attach:{src:'assets/screenshots/pdf-attachments-save.png?v=20260928-background-review',width:1636,height:1666},
  'attach-review':{src:'assets/screenshots/pdf-attachments-review-result.png',width:1588,height:1066},
  organize:{src:'assets/screenshots/folder-pdf-status.png',width:1614,height:648},
  'organize-review':{src:'assets/screenshots/folder-pdf-review-result.png',width:1622,height:712},
  'organize-refresh-request':{src:'assets/screenshots/folder-pdf-refresh-request.svg',width:1048,height:194,fullSize:true},
  'organize-refresh-result':{src:'assets/screenshots/folder-pdf-refresh-result.svg',width:1490,height:370,fullSize:true},
  'review-control-store-request':{src:'assets/screenshots/review-control-store-request.svg',width:1048,height:511,fullSize:true},
  'review-control-store-result':{src:'assets/screenshots/review-control-store-result.svg',width:1478,height:118,fullSize:true},
  'review-control-pause-request':{src:'assets/screenshots/review-control-pause-request.svg',width:1047,height:193,fullSize:true},
  'review-control-pause-result':{src:'assets/screenshots/review-control-pause-result.svg',width:1488,height:503,fullSize:true},
  'review-control-resume-request':{src:'assets/screenshots/review-control-resume-request.svg',width:1047,height:147,fullSize:true},
  'review-control-resume-result':{src:'assets/screenshots/review-control-resume-result.svg',width:1464,height:90,fullSize:true},
  'review-control-status-request':{src:'assets/screenshots/review-control-status-request.svg',width:1047,height:193,fullSize:true},
  'review-control-status-result':{src:'assets/screenshots/review-control-status-result.svg',width:1488,height:853,fullSize:true},
  'compare-request':{src:'assets/screenshots/pdf-compare-request.png?v=20260929-crop2',width:1080,height:578,fullSize:true},
  'compare-result':{src:'assets/screenshots/pdf-compare-result.png',width:1610,height:1556,fullSize:true},
  'search-request':{src:'assets/screenshots/pdf-search-request.png',width:1052,height:160,fullSize:true},
  'search-result':{src:'assets/screenshots/pdf-search-result.png',width:1494,height:1126,fullSize:true},
  'save-result':{src:'assets/screenshots/conversation-save-result.png',width:1492,height:170,fullSize:true},
  'save-scope-choice':{src:'assets/screenshots/conversation-save-scope-choice.png',width:1046,height:151,fullSize:true},
  'manage-list':{src:'assets/screenshots/conversation-list.png',width:1490,height:388,fullSize:true},
  'manage-update-request':{src:'assets/screenshots/conversation-update-request.png',width:1045,height:286,fullSize:true},
  'manage-update-result':{src:'assets/screenshots/conversation-update-result.png',width:1490,height:196,fullSize:true},
  'manage-delete-request':{src:'assets/screenshots/conversation-delete-request.png',width:1047,height:196,fullSize:true},
  'manage-delete-result':{src:'assets/screenshots/conversation-delete-result.png',width:1498,height:335,fullSize:true},
  'memory-search-request':{src:'assets/screenshots/memory-search-request.png',width:1056,height:154,fullSize:true},
  'memory-search-selection':{src:'assets/screenshots/memory-search-selection.png',width:1508,height:308,fullSize:true},
  'memory-search-plan':{src:'assets/screenshots/memory-search-plan.png',width:1498,height:1292,fullSize:true}
};
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ui={ko:{guide:'사용 가이드',overview:'가이드 둘러보기',menu:'메뉴',skip:'본문으로 이동',nav:'가이드 메뉴',first:'처음이라면',features:'기능',me:'나',assistant:'Research Agent 안내',howto:'사용 방법',note:'알아두세요',previous:'이전',next:'다음',related:'관련 가이드',blank:'실제 캡처를 넣을 빈 영역',capturePending:'캡처 준비 중',copy:'복사',copied:'복사됨',manualCopy:'직접 복사',copiedNotice:'복사했어요.',failedCopy:'복사할 문장을 선택했어요. ⌘ + C 또는 Ctrl + C로 직접 복사하세요.',prompt:'Codex에서 사용할 문장',invocationLabel:'VS Code·CLI에서 사용하려면',invocationNote:'문장 앞의 @Research Agent를 $research-library로 바꾸세요. 또는 /skills에서 research-library를 선택한 뒤 요청을 입력하세요.',install:'터미널에서 실행할 설치 명령',paste:'복사한 문장을 평소 사용하던 Codex 대화에 붙여 넣으세요.',installNote:'명령을 복사해도 설치가 실행되지는 않아요. 터미널에서 직접 실행하세요.',sideNote:'사용 가이드 · v0.4.1\n실제 작업은 Codex에서 진행해요.',overviewQuestion:'Research Agent로 무엇을 할 수 있나요?',overviewAnswer:'흩어진 PDF와 중요한 연구 대화를 정리하고, 필요할 때 다시 찾아볼 수 있어요. 궁금한 기능을 선택해 보세요.',featureDescriptions:{attach:'PDF를 대화에 첨부해 바로 저장하고 질문해요.',organize:'연결한 폴더의 PDF를 변환해 검색할 수 있도록 저장해요.',compare:'새 PDF를 저장하고 기존 자료와 함께 정리해요.',search:'여러 PDF와 저장한 대화에서 관련 내용을 찾아요.',save:'연구 아이디어와 실험 설계를 선택해서 보관해요.',manage:'저장한 대화 목록을 보고 제목·태그를 수정하거나 기록을 삭제해요.'},startLink:'처음이라면 설치부터 시작하세요.',overviewEnd:'현재 지원 환경은 macOS의 Codex예요. 이 웹은 사용 방법을 안내합니다.',},en:{guide:'User guide',overview:'Explore the guide',menu:'Menu',skip:'Skip to content',nav:'Guide navigation',first:'Getting started',features:'Features',me:'You',assistant:'Research Agent guide',howto:'How to use it',note:'Good to know',previous:'Previous',next:'Next',related:'Related guides',blank:'Empty frame reserved for a real screenshot',capturePending:'Screenshot coming soon',copy:'Copy',copied:'Copied',manualCopy:'Copy manually',copiedNotice:'Copied to clipboard.',failedCopy:'The text is selected. Press ⌘ + C or Ctrl + C to copy it.',prompt:'Prompt to use in Codex',invocationLabel:'Using VS Code or the CLI?',invocationNote:'Replace @Research Agent at the start of the prompt with $research-library. Or choose research-library from /skills, then enter your request.',install:'Installation command for Terminal',paste:'Paste this into your usual Codex conversation.',installNote:'Copying does not install anything. Run the command yourself in Terminal.',sideNote:'User guide · v0.4.1\nActual work takes place in Codex.',overviewQuestion:'What can I do with Research Agent?',overviewAnswer:'Organize scattered PDFs and important research conversations, then find them again when you need them. Choose a feature to learn more.',featureDescriptions:{attach:'Attach PDFs in Codex to save them and ask questions.',organize:'Convert and save PDFs from your connected folders.',compare:'Save new PDFs and summarize them with existing materials.',search:'Find related information across PDFs and saved conversations.',save:'Keep selected research ideas and experiment plans.',manage:'View saved conversations, edit their titles and tags, or delete a saved record.'},startLink:'New here? Start with installation.',overviewEnd:'The supported environment is Codex on macOS. This website explains how to use it.',}};
const preferences={language:'ko'};
try{
  const stored=JSON.parse(localStorage.getItem('research-guide-preferences')||'{}');
  if(['ko','en'].includes(stored?.language))preferences.language=stored.language;
}catch{}
const requestedLanguage=new URL(location.href).searchParams.get('lang');
if(['ko','en'].includes(requestedLanguage))preferences.language=requestedLanguage;
const main=document.querySelector('main');
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
  const asset=featureCaptures[capture.key]||installationCaptures[capture.key];
  const caption=escapeHTML(capture.caption);
  const fullSizeLink=asset?.fullSize?` <a href="${asset.src}" target="_blank" rel="noopener noreferrer">${language==='ko'?'크게 보기':'View full size'}</a>`:'';
  const attributes=`data-capture-language="${language}" data-capture-feature="${route}" data-capture-key="${escapeHTML(capture.key)}"`;
  const highlight=asset?.highlight;
  const annotation=highlight?`<span class="screenshot-highlight" aria-hidden="true" style="left:${(highlight.x/asset.width*100).toFixed(4)}%;top:${(highlight.y/asset.height*100).toFixed(4)}%;width:${(highlight.width/asset.width*100).toFixed(4)}%;height:${(highlight.height/asset.height*100).toFixed(4)}%"></span>`:'';
  return asset
    ? `<figure class="screenshot"><figcaption>${caption}${fullSizeLink}</figcaption><div class="screenshot-frame has-capture" style="max-width:${asset.width+2}px" ${attributes}><img src="${asset.src}" width="${asset.width}" height="${asset.height}" alt="${escapeHTML(capture.alt||capture.caption)}">${annotation}</div></figure>`
    : `<figure class="screenshot"><figcaption>${caption} · ${t.capturePending}</figcaption><div class="screenshot-frame" role="img" aria-label="${caption} — ${t.blank}" ${attributes}></div></figure>`;
}
function renderGuideCopy(stage,t,key){
  if(!stage.composer)return '';
  const isInstall=stage.composer==='install';
  const text=isInstall?window.RESEARCH_GUIDE_RELEASE.installCommand:stage.prompt;
  return `<div class="installation-copy" role="group" aria-labelledby="copy-${key}-label">
    <div class="installation-copy-box">
      <div class="installation-copy-header"><p id="copy-${key}-label">${isInstall?t.install:t.prompt}</p><button type="button" data-copy-guide>${t.copy}</button></div>
      <pre id="copy-${key}-text" class="installation-copy-text${isInstall?' is-command':''}" tabindex="0" aria-labelledby="copy-${key}-label">${escapeHTML(text)}</pre>
    </div>
    <p class="installation-copy-note">${isInstall?t.installNote:t.paste}</p>
    ${isInstall?'':`<details class="invocation-help"><summary>${t.invocationLabel}</summary><p>${t.invocationNote}</p></details>`}
  </div>`;
}
function renderInstallation(page, t, language){
  const requested=Number(new URL(location.href).searchParams.get('step'));
  const step=Number.isInteger(requested)&&requested>=1&&requested<=page.stages.length?requested:1;
  const stage=page.stages[step-1];
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
      ${stage.flow?stage.flow.map(item=>`<section class="installation-flow-step"><h2>${escapeHTML(item.title)}</h2><p>${escapeHTML(item.body)}</p>${renderCapture(item.capture,'start',language)}</section>`).join(''):`<ol class="installation-actions">${stage.steps.map(s=>`<li>${escapeHTML(s)}</li>`).join('')}</ol>${renderGuideCopy(stage,t,`start-${step}`)}${stage.captures.map(c=>renderCapture(c,'start',language)).join('')}`}
      ${stage.help?`<details class="howto installation-help"><summary>${escapeHTML(stage.helpLabel)}</summary><dl>${stage.help.map(item=>`<dt>${escapeHTML(item.question)}</dt><dd>${escapeHTML(item.answer)}</dd>`).join('')}</dl></details>`:''}
      ${stage.note?`<details class="howto"><summary>${escapeHTML(stage.noteLabel)}</summary><p class="note">${escapeHTML(stage.note)}</p></details>`:''}
    </div>
    ${step===page.stages.length?`<section class="installation-flow-step"><h2>${escapeHTML(page.saveChoice)}</h2><ul class="feature-list"><li><a href="#/attach">${escapeHTML(page.firstTask)}</a></li><li><a href="#/organize">${escapeHTML(page.folderTask)}</a></li></ul></section>`:''}
    <nav class="installation-pagination" aria-label="${page.stageNav}">${previous}${next}</nav>
  </div>`;
}
function renderFollowUp(followUp,route,t,language){
  if(!followUp)return '';
  const key=followUp.key||`${route}-review`;
  const captures=(followUp.captures||(followUp.capture?[{key,caption:followUp.capture,alt:followUp.captureAlt}]:[])).map(c=>renderCapture(c,key,language)).join('');
  const prompt=followUp.prompt?renderGuideCopy({composer:'prompt',prompt:followUp.prompt},t,key):'';
  const result=followUp.result?`<p class="note">${escapeHTML(followUp.result)}</p>`:'';
  const steps=(followUp.followUps||[]).map(item=>renderFollowUp(item,key,t,language)).join('');
  return `<details class="howto" data-follow-up-key="${escapeHTML(key)}"${followUp.open?' open':''}><summary>${escapeHTML(followUp.title)}</summary><p class="note">${escapeHTML(followUp.explanation)}</p>${prompt}${result}${captures}${steps}</details>`;
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
  document.querySelector('#live-message').textContent='';
  if(route==='overview'){
    main.innerHTML=`<div class="conversation overview"><div class="message user-message"><p class="speaker">${t.me}</p><p class="overview-question">${t.overviewQuestion}</p></div><div class="message assistant-message"><p class="speaker">${t.assistant}</p><p class="message-text">${t.overviewAnswer}</p><ul class="feature-list">${['attach','organize','compare','search','save','manage'].map(key=>`<li><a href="#/${key}">${titleFor(key)}</a><p>${t.featureDescriptions[key]}</p></li>`).join('')}</ul><div class="overview-start"><a href="#/start">${t.startLink}</a><p>${t.overviewEnd}</p></div></div></div>`;
  }else if(route==='start'){
    renderInstallation(translated.start,t,language);
  }else{
    const p={...translated[route],steps:[...translated[route].steps]};
    const captureFigures=(p.captures||[{key:route,caption:p.capture,alt:p.captureAlt}]).map(c=>renderCapture(c,route,language)).join('');
    const followUp=(p.followUps||(p.followUp?[p.followUp]:[])).map(item=>renderFollowUp(item,route,t,language)).join('');
    const promptCopy=renderGuideCopy({composer:'prompt',prompt:p.prompt},t,route);
    const help=p.help?`<details class="howto installation-help"><summary>${escapeHTML(p.helpLabel)}</summary><dl>${p.help.map(item=>`<dt>${escapeHTML(item.question)}</dt><dd>${escapeHTML(item.answer)}</dd>`).join('')}</dl></details>`:'';
    main.innerHTML=`<div class="conversation"><div class="message user-message"><p class="speaker">${t.me}</p><p class="message-text">${escapeHTML(p.question)}</p></div><div class="message assistant-message"><p class="speaker">${t.assistant}</p><p class="message-text">${escapeHTML(p.answer)}</p><details class="howto" open><summary>${t.howto}</summary><ol>${p.steps.map(s=>`<li>${escapeHTML(s)}</li>`).join('')}</ol></details>${promptCopy}${captureFigures}${p.alternative?`<p class="note"><a href="#/${escapeHTML(p.alternative.route)}">${escapeHTML(p.alternative.label)}</a></p>`:''}<details class="howto"><summary>${t.note}</summary><p class="note">${escapeHTML(p.note)}</p></details>${help}${followUp}</div><nav class="related" aria-label="${t.related}"><a href="#/${p.prev}">${t.previous}: ${titleFor(p.prev)}</a><a href="#/${p.next}">${t.next}: ${titleFor(p.next)}</a></nav></div>`;
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
  const copyButton=event.target.closest('[data-copy-guide]');
  if(copyButton){
    const text=copyButton.closest('.installation-copy').querySelector('.installation-copy-text');
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
savePreferences();
render();
