window.RESEARCH_GUIDE_EN = {
  start: {
    title: 'Get started',
    question: 'How do I start using Research Agent?',
    requirements: 'Use a Mac with Codex signed in. ChatGPT Pro 5x is recommended; Plus may reach usage limits sooner. You do not need a separate API key or a Git or Python installation.',
    stageNav: 'Installation guide steps',
    back: 'Previous step',
    forward: 'Next step',
    saveChoice: 'Choose how to save your PDFs.',
    firstTask: 'Attach and save PDFs',
    folderTask: 'Save PDFs from connected folders',
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
        answer: 'Choose your folders, check the list, then click “연결하고 PDF 저장하기” (Connect and save PDFs). Saving starts for those folders, followed by checks of figures, equations, and tables. Your original files stay unchanged.',
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
            title: 'Check the list and start saving',
            body: 'Check the list, then click “연결하고 PDF 저장하기” (Connect and save PDFs). To add another location first, click “폴더 더 추가하기” (Add more folders). Saved text is searchable while visual review continues.',
            capture: {
              key: 'folder-draft-confirmation',
              caption: 'The confirmation screen with three folders selected. The black outline marks “연결하고 PDF 저장하기” (Connect and save PDFs) for this guide.',
              alt: 'The confirmation list with three folders checked and the “연결하고 PDF 저장하기” (Connect and save PDFs) button'
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
            question: 'The folders are connected, but saving has not started?',
            answer: 'A connection is not proof of completed storage. If the Codex executable is unavailable or startup fails, connections stay saved and processing is reported as deferred or failed. Share that message with Codex to continue. An existing library-wide review pause keeps visual work on hold after text storage until you ask to resume.'
          },
          {
            question: 'Why does my window look different?',
            answer: 'Published v0.3.0 uses the earlier picker, where “선택” (Select) finishes selection directly. The draft-list flow and automatic saving are upcoming changes. In v0.3.0, ask Codex to organize PDFs after connecting folders.'
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
    next: 'organize'
  },
  connect: {
    title: 'Connect PDF folders',
    question: 'Can my PDFs stay in different folders?',
    answer: 'Yes. Leave your PDFs where they are and connect their folders. Published v0.3.0 needs a separate organization request. The development version starts saving PDFs from the confirmed folders automatically.',
    capture: 'Folder selection and connection result screen',
    steps: [
      'Use the prompt below to ask Codex to connect your folders.',
      'Run the command it gives you in a regular Terminal window to open the folder picker.',
      'To choose several folders, hold down ⌘ Command beside the spacebar and click each folder name once. Double-clicking may finish selection immediately.',
      'Check that the folders you want are selected, release the key, then click “선택” (Select) at the bottom right.',
      'Connect other folders the same way, then ask, “Organize my newly added documents.”'
    ],
    note: 'If you connected folders during installation, you do not need to register them again. These instructions describe published v0.3.0. The development version lets you confirm the list with “연결하고 PDF 저장하기” (Connect and save PDFs), then saves PDFs from those folders and hands off to visual review. Canceling the inner picker preserves the list; canceling the whole flow registers nothing from that draft. Reopening through a Codex request is being prepared. These improvements are not yet released.',
    prompt: '@Research Agent Connect the folders containing my PDFs.',
    prev: 'start',
    next: 'organize'
  },
  attach: {
    title: 'Save attached PDFs',
    question: 'Can I send PDFs without connecting a folder?',
    answer: 'Yes. Attach one or more PDFs and ask to save and summarize them. Once the text is saved, you can ask questions immediately. Figures, equations, and tables that need checking are then reviewed in the background, while you keep chatting.',
    capture: 'An earlier Korean capture showing three PDFs saved and summarized. Visual review is only marked as pending, so this does not confirm that it started. A new capture showing review startup and results will replace it.',
    captureAlt: 'Three attached PDFs, TinyBERT, MiniLM, and Dense Passage Retrieval, a save-and-summarize request, and a Korean response reporting new saves, document summaries, and 27 pages awaiting visual review',
    steps: [
      'Attach one or more PDFs together in a local Codex conversation.',
      'Type @research, select Research Agent, and use the prompt below to save and summarize the attached PDFs.',
      'Check which documents were saved, whether any files failed, and whether visual review started. You can keep asking questions once the text is saved.',
      'Check the review results before relying on details in figures, equations, or tables. You can ask, “What are the visual review results for the attached PDFs?”'
    ],
    alternative: {route: 'organize', label: 'Already connected folders? Save their PDFs'},
    note: 'Codex must be able to read the attachment. Attaching a PDF alone does not save it, but asking Research Agent to summarize or compare it also saves it. If you do not want this, say, “Do not save this; explain it only in this conversation.” Saved materials remain available in future conversations.',
    helpLabel: 'Review has not started, or you want to pause?',
    help: [
      {question: 'What if review is pending or could not start?', answer: 'Pending does not mean a review is running. Check the reason in the reply and ask, “Check whether visual review of the attached PDFs has started. If it has not, tell me why.” Do not treat unconfirmed figures, equations, or tables as verified. If further review is needed, ask to recheck only the affected documents and pages.'},
      {question: 'What if it takes too long or uses too much of your allowance?', answer: 'In the current development version, you can ask, “Pause visual review of this PDF.” Its saved text remains available. Later, ask, “Resume visual review of this PDF.” This pause and resume feature is not included in published v0.3.0 yet.'}
    ],
    prompt: '@Research Agent Save the attached PDFs to my research library and summarize the key points of each attached document.',
    prev: 'start',
    next: 'compare'
  },
  organize: {
    title: 'Save PDFs from folders',
    question: 'How do I save PDFs from the folders I connected during installation?',
    answer: 'Published v0.3.0 needs the prompt below for the first save after connecting folders. The development version starts saving after folder confirmation, so check its progress instead. Use the prompt later to update added or changed PDFs. Your originals stay unchanged.',
    capture: 'An actual Korean status check after saving: nine PDFs from three folders are saved, and visual review is complete for seven documents. Each of the other two needs one page reviewed further; no review job is currently running.',
    captureAlt: 'A Korean storage and visual-review status request, with a Codex response reporting nine PDFs saved without failures, seven documents visually complete, one page needing further review in each of two documents, and no active review job',
    followUp: {
      title: 'What if further review is needed?',
      explanation: 'The PDF is saved, but some details in figures, equations, or tables could not be confirmed. Waiting alone does not trigger repeated reviews. Ask Codex to check only the pages that still need attention.',
      prompt: '@Research Agent Identify the documents and pages needing further review, review only those pages again, and save the results. When finished, report completion by document and page, and explain anything that remains unconfirmed.',
      result: 'If the reply says review is in progress, you can keep chatting. Later ask “What are the results of the further review I requested?” Check which documents and pages were verified. Some details may remain unresolved, with an explanation. Do not treat those details or values as verified; check the indicated original page. Your saved PDFs and already verified content remain available.',
      capture: 'An actual Korean reply after a request for further review. It reports that BERT page 15 and Auto-Encoding Variational Bayes page 14 were checked again and saved, with no pending review, unresolved pages, or failures remaining.',
      captureAlt: 'A Korean request to recheck and save only pages needing further review, followed by a Codex response reporting BERT page 15 and Auto-Encoding Variational Bayes page 14 verified and saved, with zero pending, unresolved, or failed pages'
    },
    steps: [
      'If you connected folders during installation, you do not need to reconnect them or attach their PDFs.',
      'Select Research Agent in a local Codex conversation. In v0.3.0, request saving with the prompt below. If the development version already started, ask “What is the storage status of the folders I just connected?”',
      'Check how many documents were saved and whether any files could not be processed. Documents can be searched once their text is saved. Figures, equations, and tables may still be under review.',
      'Use the same request after adding or changing PDFs in those folders. New and changed documents will be updated.'
    ],
    alternative: {route: 'connect', label: 'No folders connected yet? Connect PDF folders'},
    note: 'Visual content still under review is not treated as verified. macOS notifications can report completion, errors, and progress on longer tasks. Notifications may not appear depending on your settings, and they do not add new messages to the conversation automatically. If processing stops, use the same request to check the saved state and continue the remaining work.',
    prompt: '@Research Agent Convert and save the PDFs in my connected folders to my research library. Tell me which documents were saved and what is still being processed.',
    prev: 'start',
    next: 'compare'
  },
  compare: {
    title: 'Use new PDFs with saved materials',
    question: 'Can I save new PDFs and summarize them with materials already in my library?',
    answer: 'Yes. Attach new PDFs and ask to save and compare them in one request. Research Agent saves the attachments, finds related PDFs and conversation records already in your library, and summarizes them together with sources.',
    capture: 'A response showing newly saved PDFs alongside citations to previously saved materials',
    steps: [
      'Save the existing materials you want to compare first. If you connected folders, first check that saving finished in “Save PDFs from folders.”',
      'Attach one or more new PDFs in a local Codex conversation and select Research Agent.',
      'Use the prompt below to save the PDFs and summarize them with existing materials in one request.',
      'Check that the answer cites both the new PDFs and existing materials. If no related saved materials are found, it may explain that the summary uses only the attachments.'
    ],
    alternative: {route: 'organize', label: 'Save PDFs from connected folders first'},
    note: 'Research Agent retrieves saved content relevant to your question. Having saved materials does not guarantee a relevant match. Check whether any figures, equations, or tables needed for the answer are still under review.',
    prompt: '@Research Agent Save the attached PDFs and summarize them together with related materials already in my library. Explain their similarities and differences, and identify the documents supporting your answer.',
    prev: 'organize',
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
    prev: 'compare',
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
