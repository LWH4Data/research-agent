# Sources and PDF attachments

## Manage source locations

Delegate source listing and exact-path registration to
`research_library_manager`. It uses the registered launcher with `source-list`
and `source-add <path>`.

When the user asks to choose folders or reopen the connection window without
supplying paths, the primary session checks only whether
`STORE_ROOT/scripts/select_sources.py` exists in the resolved installed store:

- If the helper exists, invoke the absolute registered skill launcher with
  `source-add` without paths. Its default window language follows macOS preferences.
  Use the direct launcher path,
  without a shell wrapper, pipeline, or preceding `cd`; the user need not type a
  terminal command.
- If the helper is absent, this installation uses the legacy picker. Ask the
  user to run `bash "$STORE_ROOT/add-source.sh"` in a normal terminal, replacing
  `STORE_ROOT` with the exact absolute installed path and quoting it safely.
  Do not send no-argument `source-add` through that older skill launcher or
  promise the temporary selection list described below.

Do not create or update the helper, upgrade the runtime, or expand permissions
as part of a library operation. If the existence check is blocked, report that
stage rather than assuming either route is available. Exact paths use the
registered `source-add <path>` launcher. If `STORE_ROOT/scripts/source_intake.py`
exists, both exact paths and confirmed picker paths use the managed handoff below.
Older installations only register locations; they need a separate save request.
Do not add the new helper to an older installation during a library operation.

### Window language

For an explicit request to open the window in Korean or English, check the same
registered launcher's `source-add --help` once for `--language` support, then call
it directly with `source-add --language ko` or `source-add --language en`.
`auto` follows the first supported macOS preferred language; unsupported or
unavailable language detection falls back to English. The window language does
not change the user's macOS settings, library data, or the language of the reply.
Do not prepend environment assignments or wrappers. If an older installed
launcher does not support the option, report that limitation; do not patch the
installation or bypass its launcher to force another language.

The same language is used for installation onboarding and the following folder
selection flow. Only confirmed folder paths reach registration and storage;
language selection is host-side presentation data, not part of the intake spec.

With the helper present, the host-side window keeps a temporary selection list:
add folders, uncheck items to exclude them, then explicitly connect the checked
folders. Closing the inner picker preserves the remaining checked folders.
Closing the whole flow returns cancellation
without registration; the same user request can reopen a fresh list. Only the
confirmed paths go through the existing constrained storage command. A cancelled
result is not a failure and does not undo earlier registrations. Do not auto-sync
or retry a cancelled flow. If the launcher or UI is blocked, report the stage;
do not broaden permissions or claim that the window opened. An exact path supplied
by the user remains an alternative. The source-list command can identify already
connected folders; do not imply the temporary list manages existing connections.

In the managed folder flow, the final **연결하고 PDF 저장하기 / Connect and save PDFs** confirmation registers
exactly the checked locations and immediately submits their PDFs for text storage
and visual review. The same rule applies when the user supplies exact paths and
asks to connect them. `selected` is the processing scope, including previously
connected locations the user selected again; `added` only describes registration
changes. Never expand to every configured source or issue a second sync/submit
on top of the host handoff. An explicit request to connect without saving uses
`source-add --registration-only <exact-path> [...]` and does not start processing.
This explicit mode requires paths rather than opening the save-confirmation picker.

### Wait for the folder flow's result

The primary session owns the foreground `source-add` call until it returns.
While the user selects folders, explain the next click in a progress update;
do not end the task with only "the window is open." If the execution tool yields
a running session or cell ID, keep that ID and use its corresponding continuation
or wait tool in bounded intervals. Continue after folder confirmation until the
command exits and consume its output, including partial results on a nonzero exit.
Do not relaunch `source-add` or submit a second intake because the call is still
running. Respect an explicit user interruption instead of waiting indefinitely.

`RESEARCH_SOURCE_INTAKE_RECEIPT` is printed before text storage. Preserve it for
recovery; its appearance is not completion. The completed JSON's `processing`
receipt is the basis for the final reply. If that output is lost or truncated,
use the known request ID with the registered `research-review status --request
<request_id>` launcher to check only that request. Also check saved status after
an interrupted/failed submit, whose returned request may still be the earlier
prepared snapshot. If neither completion nor status can be obtained, state what
is unconfirmed rather than claiming success.

Summarize the confirmed folder selection, text-storage results and any failures,
counting committed documents rather than source items. Then distinguish visual
review running, queued, paused, failed, unresolved, or startup still
unconfirmed from the request and handoff evidence. `processing.state=submitted`
alone does not establish running. For those state meanings, read the handoff
section in [Sync and background review](sync-and-background.md). Do not ask for
another save request after the user confirmed saving. Return once text and the
handoff result are known; do not wait for all visual pages to finish. Cancellation
returns a cancellation result without starting intake. Ending the foreground
conversation does not itself cancel review already handed off, and this flow
does not send a new message into an already-ended Codex task.

Keep the structured `processing` receipt, including its request ID and retry
key/specification, in the operational context and any agent-to-agent handoff.
Apply the skill's user-facing response rule: summarize the outcome without
appending these internal recovery fields. A registration success alone is not proof of text
storage or visual startup. Report deferred/failed processing honestly and reuse
its recovery identity rather than submitting a new request blindly. Existing
library-wide review pause remains in force: text can be saved while review waits
for the user's resume request. Installation without the Codex executable may
register only and report deferred storage; it never bypasses the review profile.

Resolve the exact registered source before disconnection; ask the user to
choose only if the target is ambiguous. Removing a source uses the registered
launcher's `source-remove <id>` through
`research_library_manager`. Explain that this disables future scans while
retaining the original-path mapping. Its existing Markdown snapshot remains
searchable, and neither originals nor generated Markdown are deleted. Adding
the same path later re-enables it.

## PDF attachments

An attached PDF is an alternative input to a registered folder, not a temporary
answer-only mode. When the user selects or names Research Agent and asks to use
one or more attached PDFs as research material, import all PDFs in the requested
set into the persistent library before answering. This includes requests such
as "find this in these three PDFs" or "compare these PDFs"; the user need not
also say "save" or register a folder. If the user explicitly asks for an
answer only in this session or says not to save, honor that instead. Merely
attaching a PDF or asking Codex a general PDF question without invoking this
skill is not authorization to store it.

Pass the exact accessible path and filename of every requested attachment to
`research_library_manager` in one bounded delegation. Never ask for folder
registration when the task already exposes the attachment paths. Read
[Sync and background review](sync-and-background.md) and use one managed
`research-review submit` with all requested attachment items, its caller-persisted
expiring key, and stdin specification. The host bridge first persists intent,
then reads each explicitly authorized regular attachment as bounded binary
bytes into the existing constrained storage command. It does not write beside
or modify the original. Targeted text conversion, receipt recovery, exact
version linking, and detached review handoff follow deterministically.

The installed launcher remains the only entry point. Invoke its absolute path
without a pipeline, redirection, environment assignment, shell wrapper, or
preceding `cd`/`set`. Keep PDF bytes out of the model context. The specification
is text and uses the normal sentinel; the internal PDF transfer uses binary
EOF. A host attachment read denial is not permission to broaden the sandbox.
Report the blocked stage and preserve other successful item receipts.

If one attachment fails, the request keeps successful links and reports that
item's failure. If interrupted after a committed import, retrying the same key
recovers the owned copy even if the original attachment is gone. It never
infers an intake link from a matching filename or a global pending list. Report
stored text, pending visual evidence, and failures separately. A stored copy is
not a completed conversion or a verified visual note. Identical attachment
bytes may reuse the owned PDF material while distinct user requests retain
independent request IDs. No external folder registration is needed.

Low-level `import-pdf`, `--attachment`, `--stdin --name`, and targeted `sync`
remain storage primitives for managed orchestration and explicit text-only
operations. Do not use them as a normal saved-PDF workflow that omits managed
review intake. Neither input mode modifies the original or uses an external
attachment directory as an output location.

## Unavailable sources and snapshots

For an offline or unreadable registered source, report its path and error,
continue with healthy sources, and preserve its previous document state.
Do not mark its earlier documents missing or describe an incomplete scan as an
empty successful result. The internal `source-add` primitive only changes the
store's `.research-store/config.toml`; the public managed flow then performs
storage and review for the exact selected sources. Neither step writes to originals.

For an already authorized file-reading integration, `import-pdf --stdin --name
<filename.pdf>` accepts binary bytes ending at EOF. This internal primitive does not replace the managed submit flow; never add a
caller-side pipeline to a host-attachment request. Binary import does not use the text stdin sentinel.
