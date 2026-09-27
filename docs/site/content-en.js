window.RESEARCH_GUIDE_EN = {
  start: {
    title: 'Get started',
    question: 'How do I start using Research Agent?',
    requirements: 'Use a Mac with Codex signed in. ChatGPT Pro 5x is recommended; Plus may reach usage limits sooner. You do not need a separate API key or a Git or Python installation.',
    stageNav: 'Installation guide steps',
    back: 'Previous step',
    forward: 'Next step',
    firstTask: 'Start by attaching a PDF',
    folderTask: 'Connect existing PDF folders',
    stages: [
      {
        label: 'Open Terminal',
        question: 'Where do I start the installation?',
        answer: 'Start in Terminal, an app that comes with your Mac. If Terminal is already open, go to the next step.',
        steps: ['Press ⌘ + Space and type “Terminal.”', 'Select the Terminal app and press Enter.'],
        captures: [
          {key: 'spotlight', caption: 'Select Terminal in Spotlight. This example shows Korean macOS.'},
          {key: 'terminal', caption: 'You are ready when a window like this opens. Its colors and text may differ.'}
        ]
      },
      {
        label: 'Install',
        question: 'What do I enter in Terminal?',
        answer: 'The command below installs the v0.3.0 prerelease. Run it once for a fresh installation.',
        steps: ['Click “Copy” below, then paste into Terminal with ⌘ + V.', 'Press Enter and wait for “research-agent 설치가 완료되었습니다.” — the Korean installation-complete message.'],
        captures: [{key: 'install-complete', caption: 'The installation-complete message in Terminal'}],
        noteLabel: 'Already installed, or seeing an error?',
        note: 'This command is for fresh installations. If it says the destination already exists, keep that folder and share the message with Codex. Normal installation does not ask for your Mac administrator password.',
        composer: 'install'
      },
      {
        label: 'Choose folders',
        question: 'How do I connect my PDF folders?',
        answer: 'Add folders to the list, check your choices, then connect them. Your original files stay unchanged.',
        notice: 'Development preview: this flow is not yet included in v0.3.0, which the current installation command installs.',
        flow: [
          {
            title: 'Open the folder picker',
            body: 'Click “폴더 추가하기” (Add folders).',
            capture: {
              key: 'folder-draft-empty',
              caption: 'The empty folder list. The black outline is a guide annotation.',
              alt: 'The development version’s empty folder list and “폴더 추가하기” (Add folders) button'
            }
          },
          {
            title: 'Choose folders',
            body: 'Hold ⌘ Command beside the spacebar and click each folder name once. Then click “목록에 추가” (Add to list).',
            capture: {
              key: 'folder-selection',
              caption: 'An example of selected folders, cropped from an earlier screenshot.',
              alt: 'Three folder names selected and highlighted together'
            }
          },
          {
            title: 'Check the list and connect',
            body: 'Check the folder list, then click “이 폴더들 연결하기” (Connect these folders). To add another location first, click “폴더 더 추가하기” (Add more folders).',
            capture: {
              key: 'folder-draft-confirmation',
              caption: 'Three folders selected, before connecting. The black outline is a guide annotation around the connect button.',
              alt: 'The confirmation list with three folders checked and the “이 폴더들 연결하기” (Connect these folders) button'
            }
          }
        ],
        helpLabel: 'Need help?',
        help: [
          {
            question: 'No PDFs ready yet?',
            answer: 'Click “취소” (Cancel). Canceling folder selection does not undo installation. You can connect folders later or attach PDFs directly in Codex.'
          },
          {
            question: 'Selected the wrong folder?',
            answer: 'Before connecting, uncheck it to exclude it from this list. If it is already connected, ask Codex to identify the connection, then remove that connection. Your original folder and files remain unchanged.'
          },
          {
            question: 'Closed a window?',
            answer: 'Canceling the inner picker keeps your checked folders in the list. Canceling the whole flow discards this selection. Ask Codex to reopen the folder connection window; reopening directly from Codex is still being validated.'
          },
          {
            question: 'Folders will not select, or an error appeared?',
            answer: 'Click the picker window once, then hold ⌘ Command and click the folder names. If an error appears, share its message with Codex. Do not switch to Full access.'
          },
          {
            question: 'Why does my window look different?',
            answer: 'Published v0.3.0 uses the earlier picker, where “선택” (Select) finishes selection directly. The draft-list flow shown here is an upcoming development version.'
          }
        ]
      },
      {
        label: 'Try it in Codex',
        question: 'How do I call Research Agent after installation?',
        answer: 'After installation, fully quit and reopen the desktop app. You can use your usual project.',
        steps: ['Select Codex from the product menu, then open a Local conversation.', 'Type @research in the composer and select Research Agent from the results.', 'Ask about its features using the prompt below. You do not need a PDF yet.'],
        captures: [{key: 'codex-invocation', caption: 'An actual Korean conversation with Research Agent selected, showing its features and how to get started.', alt: 'A selected Research Agent mention and its Korean response describing PDF organization, search, conversation storage, and starting with one PDF'}],
        safety: 'Use Ask for approval or Approve for me. Do not use Full access with Research Agent.',
        noteLabel: 'Cannot find it in the menu?',
        note: 'If the composer shows Instant, you are in a regular ChatGPT chat. This version of Research Agent runs in a local Codex task. If it is still missing in Codex, check that installation finished and fully quit and reopen the app. If that does not help, share the installation messages with Codex.',
        composer: 'prompt',
        prompt: '@Research Agent What can you do, and how should I get started?'
      }
    ],
    prev: 'overview',
    next: 'connect'
  },
  connect: {
    title: 'Connect PDF folders',
    question: 'Can my PDFs stay in different folders?',
    answer: 'Yes. Leave your PDFs where they are and connect their folders. This step only registers the locations. PDFs are processed when you ask to organize them.',
    capture: 'Folder selection and connection result screen',
    steps: [
      'Use the prompt below to ask Codex to connect your folders.',
      'Run the command it gives you in a regular Terminal window to open the folder picker.',
      'To choose several folders, hold down ⌘ Command beside the spacebar and click each folder name once. Double-clicking may finish selection immediately.',
      'Check that the folders you want are selected, release the key, then click “선택” (Select) at the bottom right.',
      'Connect other folders the same way, then ask, “Organize my newly added documents.”'
    ],
    note: 'If you connected folders during installation, you do not need to register them again. These instructions describe published v0.3.0. The development version adds a draft list: exclude or add folders before connecting. Canceling the inner picker preserves the list; canceling the whole flow registers nothing from that draft. Reopening through a Codex request is being prepared. These improvements are not yet released.',
    prompt: '@Research Agent Connect the folders containing my PDFs.',
    prev: 'start',
    next: 'attach'
  },
  attach: {
    title: 'Attach PDFs directly',
    question: 'Can I send PDFs without connecting a folder?',
    answer: 'Yes. Attach one or more PDFs to your Codex conversation and ask Research Agent to work with them. PDF copies and searchable content are saved in your library so you can find them in future conversations.',
    capture: 'PDF attachments and saved results screen',
    steps: [
      'Attach the PDFs you need to your usual Codex conversation.',
      'Select Research Agent from the @ menu and use the prompt below.',
      'Check which documents were saved and whether any files could not be processed. Once text processing finishes, you can continue asking questions.'
    ],
    note: 'Attaching a PDF alone does not save it automatically. Codex must be able to read the attachment. If you do not want to save it, say, “Do not save this; explain it only in this conversation.” Reviewing figures, equations, and tables may take longer.',
    prompt: '@Research Agent Organize the attached PDFs and find what they have in common with my existing materials.',
    prev: 'connect',
    next: 'organize'
  },
  organize: {
    title: 'Organize PDFs',
    question: 'How do I organize PDFs I have just added?',
    answer: 'Ask to organize your documents, and Research Agent will find and process new or changed PDFs in connected folders. Once text processing finishes, you can search or continue the conversation while any needed review of figures, equations, and tables continues in the background.',
    capture: 'Document processing progress and results screen',
    steps: [
      'Connect the folders containing your PDFs. For individual PDFs, you can use “Attach PDFs directly” instead.',
      'Paste the prompt below into Codex to start organizing.',
      'Check the organized documents and pages still under review. If needed, ask, “How far along is the review of equations and figures?”'
    ],
    note: 'Visual content still under review is not treated as verified. macOS notifications can report completion, errors, and progress on longer tasks. Notifications may not appear depending on your settings, and they do not add new messages to the conversation automatically. If processing stops, use the same request to check the saved state and continue the remaining work.',
    prompt: '@Research Agent Organize my newly added documents.',
    prev: 'attach',
    next: 'search'
  },
  search: {
    title: 'Search your library',
    question: 'How do I find what I need in my PDFs?',
    answer: 'Ask in your own words. Research Agent searches across your PDFs and saved conversations, then points you to the supporting documents and pages.',
    capture: 'Question, answer, and sources screen',
    steps: [
      'First, organize the PDFs from connected folders or conversation attachments.',
      'Paste the prompt below into your usual Codex conversation and replace the topic with your own.',
      'Check which parts of the answer come from PDF evidence and which come from your saved ideas.'
    ],
    note: 'You can ask in Korean about English PDFs. Research Agent searches with relevant Korean and English keywords. If figures or equations needed for your answer are still under review, it will explain their status.',
    prompt: '@Research Agent Find ways to improve optical device coupling efficiency in my materials.',
    prev: 'organize',
    next: 'save'
  },
  save: {
    title: 'Save a conversation',
    question: 'Can I revisit the research ideas we just discussed?',
    answer: 'Ask to save the conversation, and Research Agent will first ask which parts to keep. Only the content you choose is saved as research notes, which you can later search alongside your PDFs.',
    capture: 'Save scope selection and result screen',
    steps: [
      'Use the prompt below in the Codex conversation containing the discussion you want to save.',
      'Choose the current topic, the whole conversation, or a range you specify.',
      'Later, ask something like, “Which conditions did we decide to change in the last experiment?”'
    ],
    note: 'Conversations are not all saved automatically. If the exact text of an older conversation is unavailable, Research Agent will explain that limitation.',
    prompt: '@Research Agent Save the parts of this conversation about experimental design.',
    prev: 'search',
    next: 'manage'
  },
  manage: {
    title: 'Manage saved conversations',
    question: 'Can I edit or delete saved records?',
    answer: 'View your saved conversations, then ask to change a record’s title, summary, or tags, or to delete that saved record.',
    capture: 'Saved conversation list and edit results screen',
    steps: [
      'Use the prompt below to view your saved conversations.',
      'Say which record you want to edit or delete, and what you want to change.',
      'If several records look similar, confirm the right one first.'
    ],
    note: 'The conversation text captured when you saved it is not edited. Deleting a saved record cannot be undone. Your original Codex conversation and PDF files remain unchanged.',
    prompt: '@Research Agent Show my saved conversations.',
    prev: 'save',
    next: 'search'
  }
};
