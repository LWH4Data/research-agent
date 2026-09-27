# Research Agent user guide

[Open the web guide](https://lwh4data.github.io/research-agent/?lang=en#/overview)

Research Agent helps you organize scattered PDFs and selected research
conversations, then find them from your usual Codex conversation. macOS is the
currently supported platform. You need a signed-in Codex subscription, not a
separate API key.

## First installation

1. Press **Command (⌘) + Space**.
2. Type **Terminal** and open the Terminal app.
3. Copy the entire command below, paste it with **Command (⌘) + V**, and press
   **Enter**.
4. Wait for installation to finish. It downloads and verifies the **v0.3.0
   prerelease** automatically; you do not need to install Git or Python or
   extract an archive yourself.

```sh
(
  installer=$(mktemp) &&
  trap 'rm -f "$installer"' EXIT &&
  curl -q --proto '=https' --proto-redir '=https' --tlsv1.2 -fLsS \
    https://github.com/LWH4Data/research-agent/releases/download/v0.3.0/install-release.sh \
    -o "$installer" &&
  bash "$installer" --version 0.3.0
)
```

The installation lives in `research-agent` inside your home folder. If that
location already exists, installation stops without overwriting it. Keep the
existing folder and share the message with Codex. Normal installation does not
ask for your Mac administrator password.

After installing v0.3.0, a dialog offers **폴더 선택하기** (Select folders) and
**나중에 하기** (Later). These buttons currently appear in Korean. Choose Select
folders to open the folder picker, or Later to continue without any PDFs ready.
To choose several folders in the same view:

1. Hold down the **⌘ Command** key beside the spacebar on your keyboard.
2. While holding it, click each folder name **once**. Double-clicking may finish selection immediately.
3. Check that the folders you want are selected, release the key, then click **선택** (Select) at the bottom right.

If Command-clicking does not select folders, click the instructions at the top of the picker once, then try again.

Your original PDFs stay in their existing locations.
Canceling either dialog keeps the completed installation. If no dialog appears,
you can connect folders later or attach PDFs directly in Codex.
Fully quit and reopen the Codex app, VS Code, or CLI after installation.

GitHub's **Code → Download ZIP** downloads the development source. Use the
installation command above for the user release.

> **Development only; not included in v0.3.0:** You can ask Codex to reopen the
> folder picker in the current conversation. **폴더 추가하기** (Add folders) and
> **폴더 더 추가하기** (Add more folders) collect folders in a review list.
> Uncheck any folders to exclude, then press **이 폴더들 연결하기** (Connect these
> folders) to register the checked folders. Canceling the inner picker keeps the
> list; canceling the review list saves nothing. Existing installations have not
> received this change. Keep your existing installation.

## Use it in Codex

In the desktop app, select **Codex** from the product menu and open a **Local**
conversation on your Mac. Type `@research` and select **Research Agent** from
the results. You can use your usual project. This version does not support
regular ChatGPT **Instant** chats or Codex **Cloud** tasks.
Keep your usual **Ask for approval** or
**Approve for me** setting; do not use **Full access** for Research Agent.

You can attach PDFs and ask Research Agent to organize them, connect existing
PDF folders, search across saved documents, or save selected conversation
content. For example:

> Organize these attached PDFs and summarize what they have in common.

Text becomes searchable first. Checking figures, tables, and equations can
continue in the background. Research Agent does not modify the original PDFs.

The [Korean README](../../README.md) has the full feature guide and examples.

## Updates

Version **0.3.0 supports fresh installations only**. An update procedure that
preserves existing library data is not yet available. Running the installation
command again stops if the destination exists.

See [Releases](https://github.com/LWH4Data/research-agent/releases) for new
version announcements. Release installations do not contain Git history and
cannot be updated with `git pull`. Do not remove or overwrite an existing
installation as an update workaround.
