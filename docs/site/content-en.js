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
        answer: 'The command below installs the v0.4.1 prerelease. Run it once for a fresh installation.',
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
        flow: [
          {
            title: 'Open the folder picker',
            body: 'Click “폴더 추가하기” (Add folders).',
            capture: {
              key: 'folder-draft-empty',
              caption: 'An empty draft for choosing folders to add this time. Click “폴더 추가하기” (Add folders). The black outline is a guide annotation.',
              alt: 'A Korean connection window with no folders selected for this draft, the Add folders button, and the disabled Connect and save PDFs button'
            }
          },
          {
            title: 'Choose folders',
            body: 'Click the picker window once, then hold ⌘ Command beside the spacebar and click each folder name once. Then click “목록에 추가” (Add to list).',
            capture: {
              key: 'folder-selection',
              caption: 'Three folders selected together in an actual Korean picker. Click “목록에 추가” (Add to list) at the bottom right when ready. The black outline is a guide annotation.',
              alt: 'A macOS picker with three Desktop folders selected together, the 3 items and 3 folders counts, a Command multi-selection instruction, and the Add to list button at the bottom right'
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
            answer: 'Canceling the inner picker keeps your checked folders in the list. Canceling the whole flow discards this draft. Ask “@Research Agent Reopen the PDF folder connection window.” It opens a new empty list where you can choose again.'
          },
          {
            question: 'Folders will not select, or an error appeared?',
            answer: 'Click the picker window once, then hold ⌘ Command and click the folder names. If an error appears, share its message with Codex. Do not switch to Full access.'
          },
          {
            question: 'The folders are connected, but saving has not started?',
            answer: 'A connection is not proof of completed storage. If the Codex executable is unavailable, the connection stays saved and storage is deferred. Ask Codex to check and continue storage. If text is saved but visual review could not start, ask to check and resume review instead. A library-wide pause requires an explicit request to resume all visual reviews.'
          },
          {
            question: 'Why does my window look different?',
            answer: 'An earlier installation may have different buttons or steps. Share the screen or message with Codex. The installation command is for fresh installations and does not overwrite an existing one. Do not delete your research library to update.'
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
    answer: 'Yes. Ask Codex to open the connection window, then collect the folders in its list. Confirm with “연결하고 PDF 저장하기” (Connect and save PDFs) to start saving PDFs from the selected folders, followed by visual review.',
    captures: [
      {key: 'folder-draft-empty', caption: 'An empty draft for choosing folders to add this time. Click “폴더 추가하기” (Add folders). The black outline is a guide annotation.', alt: 'A Korean connection window with no folders selected for this draft, the Add folders button, and the disabled Connect and save PDFs button'},
      {key: 'folder-selection', caption: 'Three folders selected together in an actual Korean picker. Click “목록에 추가” (Add to list) at the bottom right to add them to the confirmation list. The black outline is a guide annotation.', alt: 'A macOS picker with three Desktop folders selected together, the 3 items and 3 folders counts, a Command multi-selection instruction, and the Add to list button at the bottom right'},
      {key: 'folder-draft-confirmation', caption: 'Check the list and click “연결하고 PDF 저장하기” (Connect and save PDFs). The black outline is a guide annotation.', alt: 'Three checked folders and the Connect and save PDFs button'}
    ],
    steps: [
      'Select Research Agent in Codex and use the prompt below to connect your folders.',
      'In the connection window, click “폴더 추가하기” (Add folders).',
      'Click the picker window once, then hold ⌘ Command and click each folder name once. Click “목록에 추가” (Add to list).',
      'Uncheck any unwanted folders in the confirmation list. Use “폴더 더 추가하기” (Add more folders) for another location.',
      'Click “연결하고 PDF 저장하기” (Connect and save PDFs), then check the storage results and review status in the Codex reply.'
    ],
    note: 'Folders connected during installation do not need connecting again. Your original folders and PDFs stay unchanged. Canceling the inner picker keeps the checked list; canceling the whole confirmation window discards this draft. If you closed it, ask “@Research Agent Reopen the PDF folder connection window” and choose again in a new list.',
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
      {question: 'What if it takes too long or uses too much of your allowance?', answer: 'Ask “Pause visual review of this PDF.” Its saved text remains available. Later, ask “Resume visual review of this PDF.” If you paused all reviews, ask “Resume visual review for the entire library.” Time and page guidance thresholds do not stop review automatically; you decide when to stop.'}
    ],
    prompt: '@Research Agent Save the attached PDFs to my research library and summarize the key points of each attached document.',
    prev: 'start',
    next: 'compare'
  },
  organize: {
    title: 'Save PDFs from folders',
    question: 'How do I check whether PDFs from connected folders were saved?',
    answer: 'Saving starts when you confirm with “연결하고 PDF 저장하기” (Connect and save PDFs). Use the prompt below to check storage and visual review status separately. Your original PDFs stay unchanged.',
    capture: 'An actual Korean status check after saving: nine PDFs from three folders are saved, and visual review is complete for seven documents. Each of the other two needs one page reviewed further; no review job is currently running.',
    captureAlt: 'A Korean storage and visual-review status request, with a Codex response reporting nine PDFs saved without failures, seven documents visually complete, one page needing further review in each of two documents, and no active review job',
    followUps: [
      {
        key: 'organize-refresh',
        title: 'Added or changed PDFs in a connected folder?',
        explanation: 'Folders are not continuously watched for changes. After adding or editing PDFs, use this prompt to process new and changed documents in connected locations.',
        prompt: '@Research Agent Organize only new or changed PDFs in my connected folders, then tell me the storage results and visual review status. Briefly list newly saved documents and the number of documents kept unchanged.',
        result: 'You do not need to reconnect existing folders. Connect a new folder first. Check the reply for newly saved documents, existing documents kept unchanged, failures, and review status. Also check the stated scope of visual review page counts.',
        captures: [
          {
            key: 'organize-refresh-request',
            caption: '1. An actual Korean request to process only new or changed PDFs in connected folders and report newly saved document names and the number kept unchanged.',
            alt: 'A Korean Research Agent request to process only new or changed PDFs in connected folders and report storage results, visual review status, newly saved document names, and the unchanged document count'
          },
          {
            key: 'organize-refresh-result',
            caption: '2. The Korean reply reports three PDFs newly saved: FastBERT, BERT-of-Theseus, and SqueezeBERT; nine existing documents kept unchanged; and no storage failures or missing originals. Within the current request scope, 109 pages are verified and eight are in progress or waiting, with background review continuing.',
            alt: 'A Korean reply reporting FastBERT, BERT-of-Theseus, and SqueezeBERT newly saved, nine existing documents unchanged, no storage failures or missing originals, and within the current request scope 109 pages verified, eight in progress or waiting, no pages currently needing further attention, and background review continuing'
          }
        ]
      },
      {
        "key": "organize-review-controls",
        "title": "Pause visual review and continue later",
        "explanation": "If review takes too long or usage is a concern, name the documents and ask to pause their review. Your saved text remains available. The same controls work for PDFs saved from folders or attached in a conversation. Replace the example document names with your own.",
        "result": "If you paused the whole library, resuming individual documents does not clear that hold. Ask to resume visual review for the whole library when ready. Time and page thresholds only give guidance; you decide whether to pause.",
        "followUps": [
          {
            "key": "review-control-store",
            "title": "1. Check storage and review startup",
            "explanation": "This example starts by attaching three new PDFs. For PDFs already saved, check their review status without attaching or saving them again.",
            "prompt": "@Research Agent Save the attached ALBERT, ELECTRA, and DeBERTa PDFs to my research library. Briefly tell me the text storage results and whether visual review has started.",
            "result": "Check text storage and review startup separately. Send the pause request below while visual review is in progress.",
            "captures": [
              {
                "key": "review-control-store-request",
                "caption": "An actual Korean request with three attached PDFs: ALBERT, ELECTRA, and DeBERTa. It asks for storage results and whether visual review has started.",
                "alt": "A Korean request with three ALBERT, ELECTRA, and DeBERTa PDF attachments, asking to save them and report text storage results and visual review startup"
              },
              {
                "key": "review-control-store-result",
                "caption": "The Korean reply reports text saved for all three documents without failures, with visual review started and running in the background.",
                "alt": "A Korean reply reporting all three ALBERT, ELECTRA, and DeBERTa PDFs saved, text extraction and storage complete, no failed files, and background visual review started and still in progress"
              }
            ]
          },
          {
            "key": "review-control-pause",
            "title": "2. Pause review for specific documents",
            "explanation": "Name the documents to pause and the results to retain. Check that the reply confirms an actual stop. A stopping status is not a completed pause.",
            "prompt": "@Research Agent Pause visual review only for ALBERT, ELECTRA, and DeBERTa. Keep the saved text and completed review results, and tell me whether review has actually stopped and what remains.",
            "result": "This example pauses only the three named documents. Saved text and verified results remain available; review can continue from the remaining work later.",
            "captures": [
              {
                "key": "review-control-pause-request",
                "caption": "The Korean request pauses review only for the three documents while retaining saved text and completed review results.",
                "alt": "A Korean request to pause visual review only for ALBERT, ELECTRA, and DeBERTa, keep saved text and completed results, and report the actual stop and remaining work"
              },
              {
                "key": "review-control-pause-result",
                "caption": "The Korean reply confirms the execution process has exited. ALBERT has four pages reviewed and six remaining; ELECTRA has 13 remaining and DeBERTa has 16. Saved content is retained, and other documents are unaffected.",
                "alt": "A Korean reply confirming the three document reviews paused and the execution process exited, with saved text and completed results retained. ALBERT has four reviewed and six remaining pages; ELECTRA zero reviewed and 13 remaining; DeBERTa zero reviewed and 16 remaining. No failed or further-attention pages at that time; other document reviews are unaffected"
              }
            ]
          },
          {
            "key": "review-control-resume",
            "title": "3. Continue the remaining review",
            "explanation": "Name the paused documents and ask to continue the remaining review. Keep completed review results.",
            "prompt": "@Research Agent Continue the remaining visual review for ALBERT, ELECTRA, and DeBERTa. Keep completed review results and briefly tell me whether review has resumed.",
            "result": "Resuming is separate from completing the review. You can keep asking questions using saved text while background review continues.",
            "captures": [
              {
                "key": "review-control-resume-request",
                "caption": "The Korean request continues only the remaining visual review for the same documents while keeping completed results.",
                "alt": "A Korean request to continue remaining visual review for ALBERT, ELECTRA, and DeBERTa, preserve completed results, and report whether review resumed"
              },
              {
                "key": "review-control-resume-result",
                "caption": "The Korean reply reports that remaining review resumed in the background, with saved text and existing results retained and no current failures.",
                "alt": "A Korean reply reporting remaining visual review for ALBERT, ELECTRA, and DeBERTa resumed in the background, saved text and existing results retained, and review in progress without current failures"
              }
            ]
          },
          {
            "key": "review-control-status",
            "title": "4. Check current status and remaining work",
            "explanation": "Ask for status later and distinguish work in progress or waiting from pages needing further attention. This screenshot does not show all review completed.",
            "prompt": "@Research Agent Tell me the visual review results for ALBERT, ELECTRA, and DeBERTa. If any work is still in progress or needs further attention, give the document names, pages, and reasons.",
            "result": "The denominator counts selected visual review pages, not every page in the PDF. For pages needing further attention, such as ALBERT page 10, follow the further-review guide below. Work in progress or waiting is not a confirmed error.",
            "captures": [
              {
                "key": "review-control-status-request",
                "caption": "The Korean request asks for current review results and the documents, pages, and reasons for remaining work.",
                "alt": "A Korean request for visual review results of ALBERT, ELECTRA, and DeBERTa and document names, pages, and reasons for work still in progress or needing further attention"
              },
              {
                "key": "review-control-status-result",
                "caption": "For selected review pages, the Korean reply reports ALBERT 9/10 verified with page 10 needing further attention, ELECTRA 8/13 verified, and DeBERTa 8/16 verified. Other work is in progress or waiting; ALBERT page 10 needs further checks for table column alignment and OCR.",
                "alt": "A Korean status reply for selected visual review pages: ALBERT 9/10 verified with page 10 needing further attention, ELECTRA 8/13 verified with pages 14–18 waiting or in progress, and DeBERTa 8/16 verified with pages 16–23 waiting or in progress. On ALBERT page 10, the extracted text omits the dash from Table 10’s UPM row RACE column, and an OCR issue with evaluation benchmark also requires further checking. Saved text and completed results remain; no execution failure is reported. Review is not fully complete"
              }
            ]
          }
        ]
      },
      {
        key: 'organize-review',
        followUps: [
          {
            "key": "albert-page10-review",
            "title": "Example: recheck ALBERT page 10",
            "explanation": "This example targets ALBERT page 10, which needed further attention in the earlier status screenshot. Replace the document name and page with your own. Page numbers count from the first page of the PDF.",
            "prompt": "@Research Agent Check page 10 of the saved ALBERT PDF, counting from the first PDF page. If further attention is still needed, visually review only that page again and save the result. Compare Table 10 column alignment, the UPM row RACE entry, and OCR of evaluation benchmark against the original. Briefly report completion, corrections, and reasons for anything still unconfirmed. If the page is already verified, show the saved result.",
            "result": "Check both page verification and result storage in the reply. This example reports corrections recorded in the visual review notes, with the base extracted text and existing review results retained. Completion applies to the requested ALBERT page 10.",
            "captures": [
              {
                "key": "albert-page10-review-request",
                "caption": "1. An actual Korean request targets only ALBERT PDF page 10, asking to compare table columns, the UPM row RACE entry, and OCR against the original and save the result.",
                "alt": "A Korean request to check ALBERT page 10 counted from the first PDF page, re-review only that page if needed and save the result, compare Table 10 column alignment, the UPM row RACE entry, and evaluation benchmark OCR with the original, and report completion, corrections, and unresolved reasons. If already verified, show the saved result"
              },
              {
                "key": "albert-page10-review-result",
                "caption": "2. The Korean reply reports only page 10 re-reviewed, verified, and saved. Table 10 column order and the UPM row were checked; the RACE dash missing from extracted text and the OCR correction were recorded in visual review notes. Nothing remains unconfirmed on this page, and base extracted text and existing review results were retained.",
                "alt": "A Korean result reporting only ALBERT PDF page 10 re-reviewed, verified, and saved, with existing review results retained. Table 10 columns model, SQuAD1.1 dev, SQuAD2.0 dev, SQuAD2.0 test, and RACE test and the Ensembles UPM row dash, dash, 90.7/88.2, dash were compared with the original. The final RACE dash missing from extracted text and evaluation benchmark OCR correction were recorded in saved visual review notes. No unconfirmed details on this page; base extracted text retained"
              }
            ]
          }
        ],
        title: 'What if further review is needed?',
        explanation: 'The PDF is saved, but some details in figures, equations, or tables could not be confirmed. Waiting alone does not trigger repeated reviews. Ask Codex to check only the pages that still need attention.',
        prompt: '@Research Agent Identify the documents and pages needing further review, review only those pages again, and save the results. When finished, report completion by document and page, and explain anything that remains unconfirmed.',
        result: 'If the reply says review is in progress, you can keep chatting. Later ask “What are the results of the further review I requested?” Check which documents and pages were verified. Some details may remain unresolved, with an explanation. Do not treat those details or values as verified; check the indicated original page. Your saved PDFs and already verified content remain available.',
        capture: 'An actual Korean reply after a request for further review. It reports that BERT page 15 and Auto-Encoding Variational Bayes page 14 were checked again and saved, with no pending review, unresolved pages, or failures remaining.',
        captureAlt: 'A Korean request to recheck and save only pages needing further review, followed by a Codex response reporting BERT page 15 and Auto-Encoding Variational Bayes page 14 verified and saved, with zero pending, unresolved, or failed pages'
      }
    ],
    steps: [
      'If you connected folders during installation, you do not need to reconnect them or attach their PDFs.',
      'Select Research Agent in a local Codex conversation and use the prompt below to check the storage results.',
      'Check how many documents were saved and whether any files could not be processed. Documents can be searched once their text is saved.',
      'Check separately whether visual review is running and which documents or pages need further attention. Follow the instructions below for anything remaining.'
    ],
    alternative: {route: 'connect', label: 'No folders connected yet? Connect PDF folders'},
    note: 'Visual content still under review is not treated as verified. macOS notifications can report the start, completion, further attention, errors, and progress on longer tasks. Notifications may not appear depending on your settings; they do not add conversation messages automatically. A library-wide pause stays active after new storage. Ask explicitly to resume all reviews when ready.',
    prompt: '@Research Agent Briefly tell me the PDF storage results and visual review status for my connected folders.',
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
