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
    capture: 'An actual Korean reply reporting three PDFs saved, their text converted, and each document summarized. It reports visual review complete for DistilBERT, with remaining pages of Sentence-BERT and SimCSE being checked in the background.',
    captureAlt: 'Three attached PDFs, DistilBERT, Sentence-BERT, and SimCSE, a save-and-summarize request, and a Korean response reporting completed storage and text conversion, individual summaries, DistilBERT review complete, and some pages of the other two documents still under review',
    followUp: {
      title: 'Check the visual review results',
      explanation: 'If the save response says review is still running, ask for the results later in the same conversation. Check both the reviewed pages and anything that remains unconfirmed.',
      prompt: '@Research Agent Tell me the visual review results for the three PDFs I just attached. If anything remains unconfirmed, include the document, page, and reason.',
      result: 'Completion of the selected review pages does not mean every page of a PDF was visually checked. In the example below, some pages were not selected for automatic review and have no verification record. If you need figures, equations, or tables from those pages, name the document and pages and ask for an additional review.',
      capture: 'This actual Korean reply reports all 24 selected pages checked, with no pending pages or reported reading failures. Sentence-BERT page 2 and SimCSE pages 10–12 were not selected for automatic review and have no verification record; the precise reason for their exclusion is not available from the current records.',
      captureAlt: 'A request for visual review results for three attached PDFs. The Korean reply reports 24 selected pages checked: DistilBERT pages 1–4, Sentence-BERT pages 1 and 3–8, and SimCSE pages 1–9 and 13–16. Four other pages were not selected and have no verification record; current records do not explain their exclusion.'
    },
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
    captures: [
      {
        key: 'compare-request',
        caption: '1. An actual Korean request with three new PDFs attached, asking to save and summarize them with existing materials.',
        alt: 'MobileBERT, ConSERT, and DeCLUTR PDF attachments with a Korean request to Research Agent to save and compare them, distinguishing sources from new and previously saved documents'
      },
      {
        key: 'compare-result',
        caption: '2. The Korean reply summarizes the newly saved MobileBERT, ConSERT, and DeCLUTR papers and cites existing DistilBERT, Sentence-BERT, and SimCSE papers. It reports completed storage, text extraction, and verification of the pages selected for review.',
        alt: 'A Korean reply reporting three PDFs saved, text extracted, and selected pages verified; summaries and comparisons citing existing DistilBERT, Sentence-BERT, and SimCSE papers, with a note that results from different experimental settings cannot be compared directly'
      }
    ],
    steps: [
      'Save the existing materials you want to compare first. If you connected folders, first check that saving finished in “Save PDFs from folders.”',
      'Attach one or more new PDFs in a local Codex conversation and select Research Agent.',
      'Use the prompt below to save the PDFs and summarize them with existing materials in one request.',
      'Check that the answer cites both the new PDFs and existing materials. If no related saved materials are found, it may explain that the summary uses only the attachments.'
    ],
    alternative: {route: 'organize', label: 'Save PDFs from connected folders first'},
    note: 'Research Agent retrieves saved content relevant to your question. Having saved materials does not guarantee a relevant match. Check whether any figures, equations, or tables needed for the answer are still under review.',
    prompt: '@Research Agent Save the attached PDFs and summarize them together with related materials already in my library. Explain their similarities and differences, and identify which new or previously saved documents support your answer.',
    prev: 'organize',
    next: 'search'
  },
  search: {
    title: 'Search your library',
    question: 'How do I find what I need in my PDFs?',
    answer: 'Ask in your own words. Research Agent searches across your PDFs and saved conversations, then points you to the supporting documents and pages.',
    captures: [
      {
        key: 'search-request',
        caption: 'Ask Research Agent to find ways to make BERT smaller and faster in saved materials, with supporting documents and pages. No PDF is attached again in this request.',
        alt: 'A Korean request to Research Agent to find BERT compression methods in saved materials and explain the key differences with supporting documents and pages'
      },
      {
        key: 'search-result',
        caption: 'The Korean reply compares DistilBERT, MobileBERT, MiniLMv2, quantization, and pruning with document/page references. It identifies the pruning evidence as a secondary citation.',
        alt: 'A Korean reply comparing BERT compression methods, citing DistilBERT page 2, MobileBERT pages 1–4, MiniLMv2 pages 1–2, and evidence for quantization and pruning. It identifies pruning as a secondary citation and explains that links open saved text extracts and pages count from the first PDF page.'
      }
    ],
    steps: [
      'First, organize the PDFs from connected folders or conversation attachments.',
      'Paste the prompt below into your usual Codex conversation without attaching the PDFs again. You can replace the topic with your own.',
      'Check the supporting documents and pages. If saved conversations appear among the sources, distinguish PDF evidence from your saved ideas.'
    ],
    note: 'You can ask in Korean about English PDFs. Research Agent searches with relevant Korean and English keywords. Document links open saved text extracts, and page numbers count from the first PDF page. If figures or equations needed for your answer are still under review, it will explain their status.',
    "followUp": {
      "key": "search-memory",
      "open": true,
      "title": "Find saved conversations with related PDFs",
      "explanation": "First keep your experiment plan or selection criteria using “Save a conversation.” Later, you can ask for that saved record and related papers in another local Codex conversation. You do not need to attach the discussion or PDFs again.",
      "prompt": "@Research Agent Find the DistilBERT/MobileBERT comparison experiment plan and my selection criteria that I saved earlier. Summarize them with supporting evidence from related papers.",
      "result": "Distinguish your decisions from the saved conversation and research results from the papers. This example retrieves a saved plan, not measured experiment results. Concrete thresholds were to be determined after initial measurements. The § references identify paper sections, not pages.",
      "captures": [
        {
          "key": "memory-search-request",
          "caption": "1. Ask for the previously saved experiment plan and selection criteria, together with supporting evidence from related papers.",
          "alt": "A Korean request to Research Agent to find the previously saved DistilBERT/MobileBERT comparison experiment plan and selection criteria, with related paper evidence"
        },
        {
          "key": "memory-search-selection",
          "caption": "2. This Korean reply reports finding the saved record and quotes the selection criterion the user stated at the time.",
          "alt": "A Korean reply reporting retrieval of the saved DistilBERT/MobileBERT plan. It quotes the decision to choose the configuration using the least memory among those meeting accuracy and response-time requirements, with concrete thresholds set after initial measurements."
        },
        {
          "key": "memory-search-plan",
          "caption": "3. The saved experiment plan is summarized in a table and linked to DistilBERT and MobileBERT paper sections. Measurements and thresholds remain undecided, and the reply explains why published acceleration figures are not directly comparable.",
          "alt": "A saved experiment plan covering four DistilBERT/MobileBERT and FP32/INT8 configurations, matched training, Accuracy/macro-F1, response time, RAM, and input length. It preserves the selection sequence and undecided setup, cites DistilBERT sections 2–4 and MobileBERT sections 3 and 4.3–4.5, and says to compare measurements on the same target phone."
        }
      ]
    },
    prompt: '@Research Agent Find ways to make BERT smaller and faster in my saved materials. Briefly summarize the key differences between methods and cite the supporting documents and pages.',
    prev: 'compare',
    next: 'save'
  },
  save: {
    title: 'Save a conversation',
    question: 'Can I revisit the research ideas we just discussed?',
    answer: 'Ask to save the conversation, and Research Agent will first ask which parts to keep. Only the content you choose is saved as research notes, which you can later search alongside your PDFs.',
    captures: [
      {
        key: 'save-scope-choice',
        caption: 'This Korean reply chooses “the current DistilBERT/MobileBERT topic (recommended)” as the save scope. Choose the topic or range you want to keep.',
        alt: 'A collapsed save-scope question and a Korean reply choosing the current DistilBERT/MobileBERT topic (recommended). Only part of the question is visible; the full list of choices is not shown.'
      },
      {
        key: 'save-result',
        caption: 'A separate save-completion example. This Korean reply reports saving the DistilBERT/MobileBERT experiment plan and selection criteria, then checking the record again. It says the saved record includes four selected verbatim messages, a summary, and the final decision.',
        alt: 'A Korean reply reporting that the DistilBERT/MobileBERT mobile sentence-classification experiment plan and selection criteria were saved and checked again, including four verbatim messages and a summary. The decision is to minimize peak RAM among configurations meeting accuracy and response-time requirements, with concrete thresholds determined after initial measurements.'
      }
    ],
    steps: [
      'Discuss your experiment plan or ideas, and state the decisions and selection criteria you want to keep.',
      'Request saving in that Codex conversation using the prompt below. Replace the example experiment topic with your own.',
      'When asked which scope to save, choose the current topic or specify a range. The whole conversation is an option when all its messages are available verbatim.',
      'Check that the completion reply describes the right content and final decisions. Later, you can ask to find this record again.'
    ],
    alternative: {route: 'search', label: 'Find your saved conversations again'},
    note: 'Conversations are not all saved automatically. If the exact text of an older conversation is unavailable, Research Agent will explain that limitation. The four messages in the completion example reflect its selected scope, not a limit on how many messages can be saved.',
    prompt: '@Research Agent Save the DistilBERT/MobileBERT comparison experiment plan we just discussed and my selection criteria as a research note.',
    prev: 'search',
    next: 'manage'
  },
  manage: {
    title: 'Manage saved conversations',
    question: 'Can I edit or delete saved records?',
    answer: 'View your saved conversations, then ask to change a record’s title, summary, or tags, or to delete that saved record.',
    captures: [
      {
        key: 'manage-list',
        caption: 'This Korean reply lists two saved conversations with their titles and save times in Korea time. It reports that all original messages within each saved scope are preserved.',
        alt: 'A Korean list of two saved conversations, identified by title and save time: a DistilBERT/MobileBERT experiment-plan and selection-criteria review saved on October 1, 2026 at 19:34, and the mobile sentence-classification experiment plan and selection criteria saved that day at 09:48. The reply reports preservation of the original messages within each saved scope.'
      }
    ],
    steps: [
      'Use the prompt below to view your saved conversations.',
      'Choose a record by its title and save time. If several records look similar, confirm the right one first.',
      'Identify the record by title and save time, then ask to change its title, summary, or tags, or to delete that record.',
      'Check the completion reply for the right record and changes. After an edit, you can request the list again to check the new title.'
    ],
    note: 'The conversation text captured when you saved it is not edited. Deleting a saved record cannot be undone. Your original Codex conversation and PDF files remain unchanged.',
    prompt: '@Research Agent Show my saved conversations.',
    followUps: [
      {
        key: 'manage-update',
        open: true,
        title: 'Edit a title and tags',
        explanation: 'Identify a record from the list by its title and save time. Replace the example title, save time, new title, and tag below with your own.',
        prompt: '@Research Agent Rename the record “DistilBERT/MobileBERT comparison experiment plan and selection criteria review,” saved on October 1, 2026 at 19:34 Korea time, to “DistilBERT/MobileBERT experiment plan review notes” and add the “mobile model comparison” tag. Keep the original messages, existing summary, and selection criteria, then check the record again and tell me the result.',
        result: 'Check the completion reply for the new title and added tag. This example reports preserving the original messages, existing summary and selection criteria, other tags, and original save time.',
        captures: [
          {
            key: 'manage-update-request',
            caption: 'The request identifies the record by title and save time, asks to rename it and add the “mobile model comparison” tag, and requests another check while preserving the original messages, summary, and selection criteria.',
            alt: 'A Korean request identifying the DistilBERT/MobileBERT comparison experiment plan and selection criteria review saved on October 1, 2026 at 19:34. It asks to rename it to experiment plan review notes, add the mobile model comparison tag, preserve the original messages, existing summary, and selection criteria, and check the record again.'
          },
          {
            key: 'manage-update-result',
            caption: 'This Korean reply reports checking the record again after changing its title and adding a tag. It reports that the original messages, existing summary and selection criteria, other tags, and original save time were preserved.',
            alt: 'A Korean reply reporting another check after the edit. The new title is DistilBERT/MobileBERT experiment plan review notes and the added tag is mobile model comparison. It reports that the original messages, existing summary and selection criteria, other tags, and original save time were preserved.'
          }
        ]
      },
      {
        key: 'manage-delete',
        open: true,
        title: 'Delete a saved record',
        explanation: 'Identify the record by its title and save time. Replace the example below with your own and check the target before requesting deletion. Deleting a saved record cannot be undone. The actual Codex conversation and original PDFs are not deleted.',
        prompt: '@Research Agent Delete “DistilBERT/MobileBERT experiment plan review notes,” saved on October 1, 2026 at 19:34 Korea time. Show the remaining saved conversations afterward. Keep other saved records, the actual Codex conversation, and original PDFs.',
        result: 'Check the completion reply for the deleted title and remaining list. This example reports deleting the review note and keeping one record containing the original experiment plan.',
        captures: [
          {
            key: 'manage-delete-request',
            caption: 'The request identifies the review note by title and save time, asks to delete it and show the remaining list, and asks to preserve other saved records, the actual Codex conversation, and original PDFs.',
            alt: 'A Korean request to delete the DistilBERT/MobileBERT experiment plan review notes saved on October 1, 2026 at 19:34 Korea time. It asks to show the remaining list and preserve other saved records, the actual Codex conversation, and original PDFs.'
          },
          {
            key: 'manage-delete-result',
            caption: 'This Korean reply reports deleting the review note while preserving other saved records, the actual Codex conversation, and original PDFs. It lists one remaining record containing the original experiment plan.',
            alt: 'A Korean reply reporting deletion of the review note and preservation of other saved records, the actual Codex conversation, and original PDFs. After another check, the remaining record is the DistilBERT/MobileBERT mobile sentence-classification experiment plan and selection criteria, saved on October 1, 2026 at 09:48:55 Korea time.'
          }
        ]
      }
    ],
    prev: 'save',
    next: 'search'
  }
};
