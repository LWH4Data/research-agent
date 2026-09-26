const pages={
  "start": {
    "title": "시작하기",
    "question": "Research Agent를 처음 써보려면 어떻게 하나요?",
    "requirements": "Mac과 로그인한 Codex를 준비하세요. ChatGPT Pro 5x를 권장하며 Plus는 사용량 제한에 더 빨리 도달할 수 있어요. 별도 API 키나 Git·Python 설치는 필요 없어요.",
    "stageNav": "설치 안내 단계",
    "back": "이전 단계",
    "forward": "다음 단계",
    "firstTask": "PDF를 첨부해서 시작하기",
    "folderTask": "기존 PDF 폴더 연결하기",
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
        "question": "아직 PDF를 준비하지 못했는데 괜찮나요?",
        "answer": "괜찮아요. 설치 후 나타나는 안내창에서 “나중에 하기”를 누르세요. 폴더를 연결하지 않아도 설치는 완료돼요.",
        "steps": ["지금 PDF 폴더를 연결하려면 “폴더 선택하기”를 누르세요.", "열리는 선택창에서 폴더를 고르세요. 같은 화면의 여러 폴더는 ⌘ 키를 누른 채 선택할 수 있어요."],
        "captures": [{"key": "folder-choice", "caption": "“나중에 하기”와 “폴더 선택하기”가 보이는 안내창"}],
        "noteLabel": "선택창을 닫았거나 창이 나타나지 않았나요?",
        "note": "터미널에 설치 완료 안내가 있다면 계속 진행하세요. 폴더 선택을 취소해도 설치는 유지돼요. 나중에 폴더를 추가하거나 PDF를 대화에 바로 첨부할 수 있어요. 폴더 연결만으로 PDF 정리가 시작되지는 않아요."
      },
      {
        "label": "Codex에서 확인",
        "question": "설치한 Research Agent를 어떻게 불러오나요?",
        "answer": "사용 중인 Codex 앱·VS Code·CLI를 완전히 종료한 뒤 다시 열어요. 평소 사용하던 프로젝트의 대화에서 이어가면 돼요.",
        "steps": ["Codex 앱에서는 @ 메뉴를 열고 Research Agent를 선택하세요.", "아래 문장으로 사용법을 물어보세요. PDF가 없어도 확인할 수 있어요."],
        "captures": [{"key": "codex-invocation", "caption": "Research Agent를 선택하고 사용법을 묻는 Codex 대화 화면"}],
        "safety": "권한은 Ask for approval 또는 Approve for me를 사용하세요. Research Agent에는 Full access를 사용하지 마세요.",
        "noteLabel": "메뉴에서 찾을 수 없나요?",
        "note": "설치 완료 안내가 있었는지 확인하고, 새 대화를 여는 것뿐 아니라 Codex 앱이나 VS Code 자체를 완전히 종료한 뒤 다시 실행하세요. 계속 보이지 않으면 설치 메시지를 Codex에 알려주세요.",
        "composer": "prompt",
        "prompt": "@Research Agent 어떤 기능이 있고, 처음에는 어떻게 사용하면 돼?"
      }
    ],
    "prev": "overview",
    "next": "connect"
  },
  "connect": {
    "title": "PDF 폴더 연결하기",
    "question": "PDF가 여러 폴더에 흩어져 있는데 괜찮나요?",
    "answer": "PDF를 옮길 필요 없어요. 원래 있는 폴더들을 연결하면 됩니다. 이 단계에서는 위치만 등록하고, PDF는 정리를 요청할 때 처리해요.",
    "capture": "폴더 선택과 연결 결과 화면",
    "steps": [
      "Codex에 아래 문장으로 폴더 연결을 요청해요.",
      "안내받은 명령을 일반 터미널에서 실행하고, 열리는 선택창에서 폴더를 골라요. 같은 화면에 있는 여러 폴더는 ⌘ 키를 누른 채 선택할 수 있어요.",
      "다른 위치의 폴더도 연결한 뒤 “새로 추가된 문서를 정리해줘”라고 요청하세요."
    ],
    "note": "설치 중 폴더를 연결했다면 다시 등록할 필요 없어요. 폴더를 연결하지 않고 PDF를 대화에 첨부해서 시작할 수도 있어요.",
    "prompt": "@Research Agent 내 PDF가 있는 폴더들을 연결해줘.",
    "prev": "start",
    "next": "attach"
  },
  "attach": {
    "title": "PDF 바로 첨부하기",
    "question": "폴더를 연결하지 않고 PDF만 보내도 되나요?",
    "answer": "네. Codex 대화에 PDF를 한 개 또는 여러 개 첨부하고 Research Agent에게 작업을 요청하세요. PDF 사본과 검색용 내용이 연구 자료실에 저장되어 다음 대화에서도 찾을 수 있어요.",
    "capture": "PDF 첨부와 저장 결과 화면",
    "steps": [
      "평소 사용하던 Codex 대화에 필요한 PDF를 첨부해요.",
      "@ 메뉴에서 Research Agent를 선택하고 아래 문장으로 요청해요.",
      "저장된 문서와 처리하지 못한 파일이 있는지 확인해요. 텍스트 정리가 끝나면 바로 질문을 이어가세요."
    ],
    "note": "첨부만 하면 자동으로 저장되지는 않아요. Codex에서 첨부 파일을 읽을 수 있어야 해요. 저장을 원하지 않으면 “저장하지 말고 이번 대화에서만 설명해줘”라고 말하세요. 그림·수식·표 확인은 더 걸릴 수 있어요.",
    "prompt": "@Research Agent 첨부한 PDF들을 정리하고 기존 자료와 함께 공통된 내용을 찾아줘.",
    "prev": "connect",
    "next": "organize"
  },
  "organize": {
    "title": "PDF 정리하기",
    "question": "새로 넣은 PDF도 정리하고 싶어요.",
    "answer": "문서 정리를 요청하면 연결된 폴더에서 새로 추가되거나 변경된 PDF를 찾아 처리해요. 텍스트 정리가 끝나면 검색하거나 대화를 이어갈 수 있고, 필요한 그림·수식·표 확인은 백그라운드에서 계속돼요.",
    "capture": "문서 정리 진행 상황과 완료 결과 화면",
    "steps": [
      "PDF가 있는 폴더를 연결해요. 개별 PDF라면 “PDF 바로 첨부하기” 방법을 사용할 수 있어요.",
      "아래 문장을 Codex에 붙여 넣어 정리를 요청해요.",
      "정리된 문서와 확인 중인 페이지를 확인하세요. 필요하면 “수식과 그림 확인은 얼마나 진행됐어?”라고 물어보세요."
    ],
    "note": "아직 확인 중인 시각 자료는 검증된 결과로 취급하지 않아요. 완료·오류와 오래 걸리는 작업의 진행 상황은 macOS 알림으로 안내할 수 있어요. 알림 설정에 따라 보이지 않을 수 있고, 대화에 새 메시지가 자동으로 추가되지는 않아요. 중단 후 같은 요청을 하면 저장된 상태를 확인해 남은 작업을 이어가요.",
    "prompt": "@Research Agent 새로 추가된 문서를 정리해줘.",
    "prev": "attach",
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
    "prev": "organize",
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
  spotlight:{src:'assets/screenshots/spotlight-terminal-crop.png',width:1282,height:327},
  terminal:{src:'assets/screenshots/terminal-ready-crop.png',width:1282,height:220}
};
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ui={ko:{guide:'사용 가이드',overview:'가이드 둘러보기',menu:'메뉴',skip:'본문으로 이동',nav:'가이드 메뉴',first:'처음이라면',features:'기능',me:'나',assistant:'Research Agent 안내',howto:'사용 방법',note:'알아두세요',previous:'이전',next:'다음',related:'관련 가이드',blank:'실제 캡처를 넣을 빈 영역',capturePending:'캡처 준비 중',copy:'복사',copied:'복사됨',manualCopy:'직접 복사',copiedNotice:'복사했어요.',failedCopy:'복사할 문장을 선택했어요. ⌘ + C 또는 Ctrl + C로 직접 복사하세요.',prompt:'Codex에서 사용할 문장',invocationLabel:'VS Code·CLI에서 사용하려면',invocationNote:'문장 앞의 @Research Agent를 $research-library로 바꾸세요. 또는 /skills에서 research-library를 선택한 뒤 요청을 입력하세요.',install:'터미널에서 실행할 설치 명령',paste:'복사한 문장을 평소 사용하던 Codex 대화에 붙여 넣으세요.',installNote:'명령을 복사해도 설치가 실행되지는 않아요. 터미널에서 직접 실행하세요.',sideNote:'사용 가이드 · v0.3.0\n실제 작업은 Codex에서 진행해요.',overviewQuestion:'Research Agent로 무엇을 할 수 있나요?',overviewAnswer:'흩어진 PDF와 중요한 연구 대화를 정리하고, 필요할 때 다시 찾아볼 수 있어요. 궁금한 기능을 선택해 보세요.',featureDescriptions:{attach:'PDF를 대화에 첨부해 바로 저장하고 질문해요.',organize:'기존 폴더의 새 문서와 변경된 문서를 정리해요.',search:'여러 PDF와 저장한 대화에서 관련 내용을 찾아요.',save:'연구 아이디어와 실험 설계를 선택해서 보관해요.'},startLink:'처음이라면 설치부터 시작하세요.',overviewEnd:'현재 지원 환경은 macOS의 Codex예요. 이 웹은 사용 방법을 안내합니다.',},en:{guide:'User guide',overview:'Explore the guide',menu:'Menu',skip:'Skip to content',nav:'Guide navigation',first:'Getting started',features:'Features',me:'You',assistant:'Research Agent guide',howto:'How to use it',note:'Good to know',previous:'Previous',next:'Next',related:'Related guides',blank:'Empty frame reserved for a real screenshot',capturePending:'Screenshot coming soon',copy:'Copy',copied:'Copied',manualCopy:'Copy manually',copiedNotice:'Copied to clipboard.',failedCopy:'The text is selected. Press ⌘ + C or Ctrl + C to copy it.',prompt:'Prompt to use in Codex',invocationLabel:'Using VS Code or the CLI?',invocationNote:'Replace @Research Agent at the start of the prompt with $research-library. Or choose research-library from /skills, then enter your request.',install:'Installation command for Terminal',paste:'Paste this into your usual Codex conversation.',installNote:'Copying does not install anything. Run the command yourself in Terminal.',sideNote:'User guide · v0.3.0\nActual work takes place in Codex.',overviewQuestion:'What can I do with Research Agent?',overviewAnswer:'Organize scattered PDFs and important research conversations, then find them again when you need them. Choose a feature to learn more.',featureDescriptions:{attach:'Attach PDFs in Codex to save them and ask questions.',organize:'Organize new and changed documents in their existing folders.',search:'Find related information across PDFs and saved conversations.',save:'Keep selected research ideas and experiment plans.'},startLink:'New here? Start with installation.',overviewEnd:'The supported environment is Codex on macOS. This website explains how to use it.',}};
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
  const asset=route==='start'?installationCaptures[capture.key]:null;
  const caption=escapeHTML(capture.caption);
  const attributes=`data-capture-language="${language}" data-capture-feature="${route}" data-capture-key="${escapeHTML(capture.key)}"`;
  return asset
    ? `<figure class="screenshot"><figcaption>${caption}</figcaption><div class="screenshot-frame has-capture" ${attributes}><img src="${asset.src}" width="${asset.width}" height="${asset.height}" alt="${caption}"></div></figure>`
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
function renderInstallation(page, t, language){
  const requested=Number(new URL(location.href).searchParams.get('step'));
  const step=Number.isInteger(requested)&&requested>=1&&requested<=page.stages.length?requested:1;
  const stage=page.stages[step-1];
  setComposer(stage.composer,stage.prompt);
  const previous=step>1
    ? `<button type="button" data-install-step="${step-1}">${page.back}</button>`
    : `<a href="#/overview">${t.overview}</a>`;
  const next=step<page.stages.length
    ? `<button type="button" data-install-step="${step+1}">${page.forward}: ${escapeHTML(page.stages[step].label)}</button>`
    : `<a href="#/attach">${page.firstTask}</a>`;
  main.innerHTML=`<div class="conversation installation-guide">
    <nav aria-label="${page.stageNav}" class="installation-nav"><ol>${page.stages.map((s,i)=>`<li><button type="button" data-install-step="${i+1}"${step===i+1?' aria-current="step"':''}><span>${i+1}.</span> ${escapeHTML(s.label)}</button></li>`).join('')}</ol></nav>
    <div class="message user-message"><p class="speaker">${t.me}</p><p class="message-text">${escapeHTML(stage.question)}</p></div>
    <div class="message assistant-message"><p class="speaker">${t.assistant}</p>
      <p class="message-text">${escapeHTML(stage.answer)}</p>
      ${step===1?`<p class="installation-requirements">${escapeHTML(page.requirements)}</p>`:''}
      ${stage.safety?`<p class="installation-requirements">${escapeHTML(stage.safety)}</p>`:''}
      <ol class="installation-actions">${stage.steps.map(s=>`<li>${escapeHTML(s)}</li>`).join('')}</ol>
      ${stage.captures.map(c=>renderCapture(c,'start',language)).join('')}
      ${stage.note?`<details class="howto"><summary>${escapeHTML(stage.noteLabel)}</summary><p class="note">${escapeHTML(stage.note)}</p></details>`:''}
    </div>
    <nav class="installation-pagination" aria-label="${page.stageNav}">${previous}${next}</nav>
    ${step===page.stages.length?`<p class="installation-alternative"><a href="#/connect">${page.folderTask}</a></p>`:''}
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
    main.innerHTML=`<div class="conversation overview"><div class="message user-message"><p class="speaker">${t.me}</p><p class="overview-question">${t.overviewQuestion}</p></div><div class="message assistant-message"><p class="speaker">${t.assistant}</p><p class="message-text">${t.overviewAnswer}</p><ul class="feature-list">${['attach','organize','search','save'].map(key=>`<li><a href="#/${key}">${titleFor(key)}</a><p>${t.featureDescriptions[key]}</p></li>`).join('')}</ul><div class="overview-start"><a href="#/start">${t.startLink}</a><p>${t.overviewEnd}</p></div></div></div>`;
  }else if(route==='start'){
    renderInstallation(translated.start,t,language);
  }else{
    const p={...translated[route],steps:[...translated[route].steps]};
    const captureFigures=renderCapture({key:route,caption:p.capture},route,language);
    setComposer('prompt',p.prompt);
    main.innerHTML=`<div class="conversation"><div class="message user-message"><p class="speaker">${t.me}</p><p class="message-text">${escapeHTML(p.question)}</p></div><div class="message assistant-message"><p class="speaker">${t.assistant}</p><p class="message-text">${escapeHTML(p.answer)}</p>${captureFigures}<details class="howto" open><summary>${t.howto}</summary><ol>${p.steps.map(s=>`<li>${escapeHTML(s)}</li>`).join('')}</ol></details><details class="howto"><summary>${t.note}</summary><p class="note">${escapeHTML(p.note)}</p></details></div><nav class="related" aria-label="${t.related}"><a href="#/${p.prev}">${t.previous}: ${titleFor(p.prev)}</a><a href="#/${p.next}">${t.next}: ${titleFor(p.next)}</a></nav></div>`;
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
document.querySelector('#copy-prompt').addEventListener('click',async function(){const t=ui[preferences.language];try{await navigator.clipboard.writeText(promptField.value);this.textContent=t.copied;document.querySelector('#live-message').textContent=t.copiedNotice;}catch{promptField.focus();promptField.select();this.textContent=t.manualCopy;document.querySelector('#live-message').textContent=t.failedCopy;}});
savePreferences();
render();
