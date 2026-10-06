# Research Agent user guide

[Open the web guide](https://lwh4data.github.io/research-agent/?lang=en#/overview) · [한국어](../../README.md)

Research Agent helps you organize scattered PDFs and selected research
conversations, then find them from your usual Codex conversation. macOS is the
currently supported platform. You need a signed-in Codex subscription, not a
separate API key. Original PDFs stay in their existing locations.

## First installation

1. Press **Command (⌘) + Space**.
2. Type **Terminal** and open the Terminal app.
3. Copy the entire command below, paste it with **Command (⌘) + V**, and press
   **Enter**.
4. Wait for installation to finish. It downloads and verifies the **v0.4.1
   prerelease** automatically; you do not need to install Git or Python or
   extract an archive yourself.

```sh
(
  installer=$(mktemp) &&
  trap 'rm -f "$installer"' EXIT &&
  curl -q --proto '=https' --proto-redir '=https' --tlsv1.2 -fLsS \
    https://github.com/LWH4Data/research-agent/releases/download/v0.4.1/install-release.sh \
    -o "$installer" &&
  bash "$installer" --version 0.4.1
)
```

The installation lives in `research-agent` inside your home folder. If that
location already exists, installation stops without overwriting it. Keep the
existing folder and share the message with Codex. Normal installation does not
ask for your Mac administrator password.

After installation, a dialog offers **폴더 선택하기** (Select folders) and
**나중에 하기** (Later). These buttons currently appear in Korean. Select folders
opens the **연결할 폴더** (Folders to connect) window described below. Later,
closing the dialog, or canceling folder selection keeps the completed
installation. Automated installations do not open the dialog.

The public v0.4.1 dialog text is Korean. Development source adds Korean/English
dialogs based on macOS language preferences and supports requests such as “Open
the PDF folder connection window in English.” See the
[dialog language development record](../technical/ko/experiments/dialog-language-2026-10-06.md)
for implementation and release status.

Fully quit and reopen the Codex app, VS Code, or CLI after installation.
If no dialog appeared, ask Research Agent in Codex to open the folder connection
window. You do not need to reinstall or enter another Terminal command.

If installation cannot find the Codex executable, it keeps the confirmed folder
connections and reports that PDF storage and review have not started. A storage
failure also keeps the installation and completed connections. Share the message
with Codex and ask Research Agent to check saved progress and continue saving
PDFs from those folders.

GitHub's **Code → Download ZIP** downloads the development source. Use the
installation command above for the user release.

## Use it in Codex

In the desktop app, select **Codex** from the product menu and open a **Local**
conversation on your Mac. Type `@research` and select **Research Agent** from
the results. You can use your usual project. This version does not support
regular ChatGPT **Instant** chats or Codex **Cloud** tasks.

Keep your usual **Ask for approval** or **Approve for me** setting; do not use
**Full access** for Research Agent. The internal agents' read-only defaults and
the constrained storage tools do not change the permissions of your entire
Codex conversation. If original PDFs are inside the current writable project,
set that task to read-only for stronger protection. Research Agent must not
request write access to original sources to resolve a blocked operation.

You do not need to choose an internal agent or model. Research Agent coordinates
source management, text storage, and retrieval separately from visual review of
the pages that need it.

## Connect PDF folders

Ask Research Agent:

> Open the PDF folder connection window.

The window opens from your current Codex conversation. You do not need to
reinstall or enter a Terminal command. Its controls currently appear in Korean.

1. In **연결할 폴더** (Folders to connect), click **폴더 추가하기** (Add folders).
2. Click the folder picker once to focus it, then hold the **⌘ Command** key
   beside the spacebar and click each folder name **once** to select several folders.
3. Check your selection and click **목록에 추가** (Add to list) at the bottom right.
4. Back in the list, check the folder names and paths. Uncheck folders to exclude
   them. Use **폴더 더 추가하기** (Add more folders) to collect folders from other
   locations.
5. Click **연결하고 PDF 저장하기** (Connect and save PDFs) to confirm.

Research Agent connects only the checked folders, saves their PDF text, and
submits the pages that need visual review. Other connected folders are outside
this request. Saved text is searchable while review continues; visual review
does not inspect every page of every PDF.

Canceling the inner picker keeps the list you already collected. Canceling the
**연결할 폴더** window registers and saves nothing from this selection. Your
installation and existing connections remain. Reopening starts a new empty
selection list. Ask:

> Reopen the PDF folder connection window.

This temporary list shows your current selection. To see existing connections,
ask “Show my connected PDF locations.”

If you know the paths, you can ask Research Agent to connect several folders or
individual PDFs directly. The same storage and review workflow applies only to
those paths. For example:

> Connect ~/Documents/Photonics papers.

To connect without saving yet, provide the exact path and explicitly ask:

> Connect ~/Documents/Photonics papers, but do not save its PDFs yet.

Original PDFs are not moved, modified, or deleted. Generated documents, caches,
and search data stay inside `research-agent`; nothing is created beside the
originals. An existing connection is not registered twice. Selecting it again
includes it in this request, while unchanged PDFs are not converted again.

Connecting both a folder and its subfolder is rejected to prevent overlapping
scans. If a selection has such a conflict, new connections are not partly added.
Connect the parent alone to include PDFs in its subfolders.

If PDF storage or review startup fails after connection, completed connections
and stored results remain. Share the error and ask Research Agent to check the
saved state and continue. An existing pause of all library review also stays
in effect; text may be saved while review waits for your resume request.

To disconnect a location, first ask for the connected locations, then name the
one to disconnect. This stops future scans and keeps both original PDFs and the
existing searchable snapshot. Reconnecting that path enables checking again.

## Save attached PDFs

You can start with one or more PDFs attached to your Codex conversation without
connecting a folder. Select Research Agent and ask:

> Organize these attached PDFs and summarize what they have in common.

Invoking Research Agent to use the attached PDFs saves the requested set to the
library without a second save request. Merely attaching files does not save
them. For a session-only answer, explicitly say “Do not save these PDFs.”

Research Agent stores private PDF copies and searchable text inside the
installation. You can retrieve saved text from other Codex conversations while
review of equations, tables, and figures continues. Originals remain unchanged.

- One unreadable attachment does not discard the successful results from others.
- Identical PDF content reuses the saved item and its first filename. Changed
  content becomes a separate item, even if the filename is the same.
- Saved attachments do not track later original-file changes. Connect a folder
  for documents that change over time.
- Folder documents and imported attachments are managed separately.
- Encrypted PDFs and attachments larger than 256 MiB are not currently supported.

If Codex cannot read an attachment, Research Agent reports that it was not saved.
Provide an accessible local PDF path or connect its folder.

## Update documents and check progress

Confirming a folder starts its first storage request. After a successful save,
you do not need to ask to save the same PDFs again. When you add or change PDFs
in connected folders, ask:

> Organize newly added or changed documents.

Research Agent checks connected locations and processes new or changed PDFs.
Unchanged PDFs are not converted again. If initial storage was deferred, ask
“Save the PDFs from my connected folders.”

Text storage progress appears in the current Codex conversation. Pages with
equations, tables, or figures that need image inspection are reviewed in the
background. Their visual details remain unconfirmed until review establishes
the evidence. This can take longer and use more Codex subscription allowance.

Ask “How far has review of equations and figures progressed?” to check status.
To pause or resume, specify the PDF:

> Pause visual review of this PDF.

> Resume visual review of this PDF.

You can also ask to pause all visual review in the library. That pause persists
across new saves and restarts. Resuming an individual PDF does not clear it;
only an explicit request to resume all library review does. Saved text remains searchable. Time or page guidance warns
without automatically stopping review. You decide whether to pause or continue.

macOS may notify review startup, completion or unresolved pages, errors,
pauses or holds, and configured time or page guidance thresholds. Progress
notifications may appear after at least five minutes of active review when
processed pages newly cross 25%, 50%, and 75% milestones. Processed counts can
include uncertain pages, which are shown separately from verified pages.
Notifications are best effort and depend on macOS settings and the execution
environment. A missing notification does not stop review.

These are operating-system notifications. They do not automatically add a new
message to your Codex conversation. Ask Research Agent for the saved status.

After an interruption, safely stored results remain. Ask to continue; Research
Agent checks saved state before proceeding. It does not repeatedly retry pages
marked uncertain forever. Ask to review those pages explicitly when needed.

## Search saved material

Ask a topic question from your usual Codex conversation:

> Find material about DBR cavities.

> Compare how my saved documents describe the limits of silicon photonics.

Research Agent searches PDF content and saved conversations together. It selects
relevant Korean and English terms, so you can ask in Korean about English PDFs.
Answers distinguish PDF evidence, your saved ideas, and earlier Codex
explanations, with source paths and pages when available. Visual claims that
have not been checked remain identified as unconfirmed.

## Save and manage conversations

Ask Research Agent to save the research discussion you want to retrieve later:

> Save the experimental design part of this conversation.

It first asks whether to save the current topic, the whole conversation, or a
range you describe. After you choose, it saves the available messages without a
second confirmation. Unavailable older history is not reconstructed; missing
parts are reported.

Ask to list your saved conversations or to find a previous idea. You can update
titles, summaries, and tags, but saved statements and their selected range are
not rewritten. To correct the saved statements or range, delete that record and
save the correct selection again.

Deletion affects only the selected Research Agent conversation record. It does
not delete the actual Codex conversation, PDFs, or other records. If several
records match, Research Agent asks which one you mean. Deleted conversation
records cannot currently be restored.

## Updates

Version **0.4.1 supports fresh installations only**. Automatic updates and an
update procedure that preserves existing library data are not yet available.
Running the installation command again stops if the destination exists.

See [Releases](https://github.com/LWH4Data/research-agent/releases) for new
version announcements. Release installations do not contain Git history and
cannot be updated with `git pull`. Do not remove, delete stored material from,
or overwrite an existing installation as an update workaround.

The [Korean README](../../README.md) also covers troubleshooting, CLI/IDE skill
invocation, and removal.
