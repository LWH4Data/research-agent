# Safety and Agent-Routing Validation

[한국어](../../ko/experiments/safety-routing-validation.md) | [English](./safety-routing-validation.md)

Validation dates: 2026-09-22; background-review follow-up: 2026-09-24; review-note storage audit: 2026-09-25

This record captures the live validation performed for storage recovery,
permissions, prompt injection, and model routing issues found before prototype
release. Design-only reviews are explicitly separated from executed validation.

<a id="prepush-2026-09-28"></a>

## 2026-09-28 Final validation before main integration

Ran `bash scripts/reproduce-validation.sh full` against the accumulated changes:
521 tests, 513 passed and 8 skipped, no failures (about 50 seconds). Skips cover
four live sandbox/notification integrations, two tests requiring a separately
assembled release archive, and two requiring case-distinct filenames. GitHub
Actions runs the two archive tests separately after assembling the bundle.

Version consistency, Korean/English/web installation commands, JavaScript syntax,
diff whitespace, and all 58 runtime manifest entries passed validation. The 64
changed/new commit paths contain no source PDFs, private library files, or DBs;
no recognized credential patterns were found. Luna xhigh / Sol high and read-only
defaults remain intact. An additional independent reviewer could not run because
of the account usage limit, so this final audit was performed by the primary
agent. No subscription model calls or user-PDF conversion were run. These results
do not signify publication of a new installation Release.

<a id="usage-introduction-2026-09-28"></a>

## 2026-09-28 Readable introductions and contextual next actions

The user's actual introduction placed capabilities in a dense paragraph and
repeated skill selection after the skill was already selected. The explanation
branch now asks for a capability list, a request the user can send, and a next
action based on already confirmed context. README's feature descriptions and
the existing guide capture were retained.

An independent agent without conversation history answered three cases: a first
introduction, next steps after nine PDFs were saved, and Korean questions about
English PDFs. It returned a capability list and attachment example, a search
example after storage, and a focused feature answer respectively. It did not
repeat installation/selection or execute storage/status commands. However, it
read the entire README, so this evaluation did not satisfy the existing
section-only reading rule. Response structure and reading-scope compliance are
separate findings. A subsequent actual capture supplied by the user showed a
one-sentence introduction, capability list, and PDF attachment request example,
without repeated skill-selection instructions. The original 1584×722 capture
replaced step 4's guide image. It confirms the response structure, not file-read
scope or successful storage/visual review. The displayed 14 seconds describes
this run only.

<a id="native-process-identity-2026-09-28"></a>

## 2026-09-28 Visual startup failure under the actual restricted profile

The personal installation saved text for nine PDFs, but all 96 visual-review
pages remained pending. All nine document links recorded `Cannot verify
execution supervisor`; there was no active execution. The original `/bin/ps`
launch reproduced `Operation not permitted`. This executable is setuid, while
direct `libproc` inspection of the caller and its children succeeds inside the
same sandbox.

- Darwin identity now uses `proc_pidinfo(PROC_PIDTBSDINFO)`, validating PID,
  process group, seconds/microseconds, and the complete record. Permission
  profiles are unchanged.
- Denied or malformed inspection is distinct from confirmed process exit. It
  cannot authorize signalling, ownership release, or replacement execution.
  Pre-dispatch failures close the gate, reap the child, and preserve diagnostics.
- All **27 focused tests** and **22 notifier/release/supervision regressions**
  passed. The eight real-process supervision cases previously skipped when
  `/bin/ps` was unavailable now run successfully.
- A separate integration test applied the **actual Codex research-review-worker
  profile** to a disposable product bundle and ran all eight supervision cases
  without skips. External source writes were denied; source contents, inode,
  modification time, and permissions remained unchanged. Only fake models ran.
- An independent reviewer confirmed matching live-process identity across two
  separate applications of the same real profile. No permission expansion or
  subscription model call was used.
- Guide consistency and diff checks passed. The `permission` reproduction mode
  includes this integration check. The entire suite, actual Sol conversion,
  notification delivery, and a clean-Mac installation were not rerun.

Previous supervision tests skipped in this sandbox and previous permission
integration checked file writes only; that gap missed the defect. Only the
installed execution script was replaced after backup. Existing nine PDFs and
pending pages are reused. Data, originals, and settings matched their content
and metadata snapshots; native inspection from the installed script succeeded.
Actual review resumption remains the next user test.

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_process_identity.py' -v
.venv/bin/python -B -m unittest discover -s tests -p 'test_lifecycle_*.py' -v
# Run in a regular terminal; disposable bundle/data and fake models only.
RESEARCH_AGENT_RUN_SANDBOX_TEST=1 .venv/bin/python -B -m unittest tests.test_process_identity_integration -v
```

<a id="folder-auto-storage-2026-09-28"></a>

## 2026-09-28 automatic storage after folder confirmation

**Development validation only; the personal installation and published v0.3.0
were not updated.** Final folder confirmation now proceeds through exact source
registration, text storage, and visual-review intake. Existing `added` receipts
remain; `selected` separately identifies this request's exact processing scope.

- An independent reviewer verified **86 focused tests** for selection, transport,
  onboarding, native dialogs, and intake: cancellation does nothing, existing
  sources can be reselected, unrelated sources stay excluded, one submit owns
  dispatch, installation without Codex defers storage, and runtime failures do
  not bypass the constrained launcher.
- Review found and fixed hidden recovery output during onboarding and malformed
  receipt handling. Key/specification output reaches the caller before storage;
  interruptions report that work may have begun. The affected 27 tests were rerun,
  with additional malformed-response checks preserving recovery identity.
- A disposable archive assembled from the product manifest exercised public
  `source-add`: two selected folders, reverse/duplicate reselection, and an
  unrelated registered folder. Only selected documents were stored. A library
  review hold allowed text storage with zero visual attempts. Original content,
  directory entries, inode, mode, and modification times remained unchanged.
  This uses fake Codex and does not prove real sandbox enforcement or model use.
- Final full run: **493 tests, 478 passed and 15 skipped**. Skips were permission
  integrations (3), OS process-ownership conditions (8), archive environment
  conditions (2), and case-sensitive filesystem conditions (2). Archive content
  validation passed separately. This run did not test a new Mac, actual download
  installation, subscription models, notification receipt, or manual UI clicks.
- The real release-workflow assembly produced **58 product files**. Manifest and
  archive-content checks (2 tests), version/guide agreement, and JavaScript syntax
  passed. No published tag or asset was changed.

Reproduce in the development checkout, with temporary inputs and stores:

```sh
.venv/bin/python -B -m unittest tests.test_source_selection tests.test_source_picker_transport tests.test_install_onboarding tests.test_picker tests.test_source_intake -v
.venv/bin/python -B -m unittest tests.test_lifecycle_release_integration -v
bash scripts/reproduce-validation.sh full
.venv/bin/python -B scripts/check_guides.py
```

After the automated checks above, the user explicitly authorized preparation
steps 1–3. The completed legacy review and free locks were confirmed; the full
installation and owned registrations were backed up, and state/material
directories were moved into the backup rather than deleted. Development product
files were applied at the same path using the existing private Python environment.
The protected project `.codex/config.toml` was retained because its parsed values
match the current runtime settings and only comments differ. Personal registrations
were refreshed. Actual public launchers reported zero sources/requests, no execution,
and no library hold; the initialized DB has schema 5 and zero documents/conversations.
Content, inode, mode, and modification times of all four original locations were
unchanged. This does not validate actual PDF processing, model calls, or a new Mac.

The next actual-use check is the user's folder confirmation followed by text
storage and review handoff. Existing screenshots are labeled as showing the old
button wording. Previous material can be restored from the local backup.

<a id="visual-review-lifecycle-implementation-2026-09-28"></a>

## 2026-09-28 Visual Review Lifecycle Implementation Validation

Following the user's decision, **time/page-triggered automatic stopping was
removed**. Configured thresholds provide guidance while review continues unless
the user stops it or authorization/execution fails. No default time/page cap is
enabled. Missing token measurements remain unknown; there is no conversion to
subscription percentage or exact cost.

Implementation and storage work were split in an isolated checkout. A reviewer
who did not author the code performed repeated review and final tests. These
results concern development code, not a v0.3.0 publication or an update to the
existing `~/research-agent` installation.

| Area | Reproduction and result |
| --- | --- |
| Independent requests/shared execution | A/B on one document, overlapping pages, union of duplicate input scopes; cancelling A preserves B's authorized results |
| Text → review handoff | Stable key, attachment transport, committed text, exact version links, acknowledged execution; a pending input prevents premature whole-request completion |
| Stop/process ownership | Real local child processes running a fake model; controller/supervisor death, explicit cancellation, and PID birth mismatch prevent overlap or signalling an unrelated process |
| Storage boundary | Journal acceptance and page authority; only current verified notes count as evidence; durable intake receipts recover commits before link creation |
| Delete/retry | Delete one of two attachments, delete during staging, or delete after text commit before linking; retry cannot silently restore the removed item |
| Retention/cleanup | Expiry embedded in keys prevents resurrection after denial-marker cleanup; owned image manifests clean intermediates while preserving original PDFs and committed notes |
| Notices | Ledger-only updates without storage-journal recovery; bounded retries, concurrent cancellation, no replay of short-task milestones; delivery failure never stops review |
| Packaged files | Extracted product manifest exercises public loading, ownership rejection, persistent library hold, and two-attachment intake with original content/directory preservation |

Regression fixes cover reservation-before-lock publication, A cancellation
discarding B results, expired-key resurrection, overwritten page scopes,
orphan-model stopping, premature intake completion, pause-before-link loss,
and reimport after deletion. Visual routing remains Sol high; management remains
Luna xhigh.

Reproduce from the development checkout using disposable stores, sources, and
HOME. No real user PDFs or subscription model calls are used:

```sh
bash scripts/reproduce-validation.sh full
.venv/bin/python -B -m unittest discover -s tests -p 'test_lifecycle_supervision.py' -v
.venv/bin/python -B scripts/check_release_version.py
.venv/bin/python -B scripts/check_guides.py
```

The process suite requires OS process-ownership inspection and must run
separately where that is allowed; a restricted Codex sandbox skips it. Final
full run was **473 tests: 458 passed, 15 skipped**. The **8 skipped process
cases passed separately on the final code with no skips**. The other skips were
3 permission integrations, 2 archive-environment tests, and 2 case-sensitive
filesystem tests. Archive content equality subsequently passed separately;
the live download/install/remove test was not rerun. The manifest/archive pair
of checks and version/guide consistency checks passed. Archive validation uses the actual release workflow
assembler and includes 57 product files, excluding development harnesses,
tests, and research data.

**Limits:** a fake Codex boundary checks profile names, arguments, shipped
modules, and source preservation; it does not prove actual Codex sandbox
enforcement. This change did not newly measure subscription calls, visible OS
notification receipt, fresh-Mac setup, or Plus/Pro usage. Live model responses
and notification arrival still require a separate check. The package was checked
locally; existing tags and release assets were not replaced.

<a id="visual-review-lifecycle-audit-2026-09-28"></a>

## 2026-09-28 Request and Shared Visual Review Lifecycle Audit

**Later user decision:** this audit reviewed the then-current automatic-limit
draft. At implementation start the user clarified that stopping is their
decision. Automatic budget pauses and extension-required resume were superseded
by advisory usage notices with continued execution until a user stop. Limit and
deadline entries below are historical findings, not current product promises.

**This was a document and targeted-code design review. No runtime changes, fault
injection, or model calls were performed in this task.** The target was the
[visual review lifecycle proposal](../visual-review-lifecycle.md), separate from
current [progress and recovery](../progress-recovery.md).

A new independent reviewer, `lifecycle_contract_audit`, examined lost requests,
shared execution ownership, stop/resume/budgets, journals, notifications, and
expiration/deletion. Targeted implementation reads established relevant
boundaries, including separate page commits and job-state updates. Six findings
from the first pass were addressed, followed by another review and fixes for two
additional findings.
A final check limited to those two amended clauses found them resolved at the
design level. That narrow confirmation was not an implementation test.

| Pass | Gap | Contract added |
| --- | --- | --- |
| 1 | Lost initial response leaves retries unidentifiable | Caller-persisted key before side effects, conflicting-input rejection, expiry rejection, bounded deletion marker |
| 1 | Cancelling initiating A could reject B's required result | Commit authority derives from review/page/current valid links; initiating request is provenance |
| 1 | Crash after commit can leave a request waiting forever | Reconcile request evidence state and missing events from committed versioned page results |
| 1 | Model child can survive its controller without recoverable ownership | Execution/process ownership identity; block new calls until previous exit is confirmed |
| 1 | Budget timing for B joining an in-flight call is unspecified | Freeze accountable requests at reservation; B reuses that call and participates in subsequent reservations |
| 1 | Expired but undeleted records may still confer authority | Apply logical expiration on each operation; delayed cleanup cannot extend permission |
| 2 | Removing A could remove an in-flight time cap | Preserve reservation allowances/deadlines until that attempt ends |
| 2 | A new B request could undo store-wide stop | Persistent library dispatch hold, cleared only by explicit library resume; retain separate cancellation/exhausted budgets |

The proposal also distinguishes evidence from answering, defines version-change
handling, lock order and partial success, and disclaims exactly-once remote model
execution. Both languages contain the contracts and 16 future acceptance
scenarios. This number is not a count of passing tests.
Checked 184 local links/anchors across nine documents, paired code fences,
acceptance numbering in both languages, and diff whitespace. No missing targets
or formatting errors were found by those checks.

Implementation must reproduce lost receipts, A cancellation while B awaits the
result, crashes after commit, surviving model children, late joins, uncollected
expired records, and store-wide stop racing new intake using disposable stores.
Time/page defaults and warning thresholds still require measured product-policy
choices; thirty-day retention is a proposed default. This limited audit does not
prove that no omissions remain or establish runtime safety.

## Confirmed Results

- Conversation save, update, and deletion use an operation journal and a
  cross-process lock. Tests injected child-process `os._exit` before and after
  file application, file-replacement and synchronization failures, and
  concurrent updates to the same revision. The next operation rolled the
  approved change forward without returning a partial state.
- Stored transcripts round-tripped LF, CRLF, and lone-CR line endings.
- Synchronization committed state after each PDF, allowing a conversation write
  to complete while the next PDF was in a long conversion. A separate
  `sync.lock` serializes synchronization runs without holding the conversation
  write lock throughout conversion.
- PDF synchronization and page-review writes use a `document_operations`
  journal. Tests stopped a child process with `os._exit` immediately after
  Markdown replacement; the next synchronization or review-related command
  rolled SQLite and Markdown forward to the target state exactly once.
  Unexpected file or database state fails closed instead of being overwritten.
- The first live permission E2E failed to load the dedicated configuration
  because it lacked top-level `default_permissions`. It also exposed that using
  the project root as the launcher's working directory could let that project's
  legacy `sandbox_mode` take precedence over the permission profile. After
  adding `default_permissions = "research-store"` and isolating both
  `CODEX_HOME` and `-C` in the same dedicated sandbox-configuration directory,
  the regression run allowed internal storage writes while denying writes to
  the external source and project code. Installation and removal also completed
  on the current Mac with an empty temporary HOME.
- A PDF and saved conversation containing execution and deletion instructions
  were synchronized, visually reviewed, and searched. The instructions remained
  data; the source hashes, saved conversation, and registered-source list did
  not change.
- The live Codex sequence completed as **primary Codex → Luna manager → primary
  Codex → Sol converter → primary Codex → Luna manager**. A Luna manager cannot
  invoke Sol as a nested agent in this custom-agent environment. This was the
  direct-routing experiment before background review.
- A separate Luna xhigh Codex session ran the JSONL progress stream exactly
  once. Phase `1/3` reached commentary before command completion; the more
  closely spaced `2/3`, `3/3`, and completion events arrived together just
  after that same command finished. Instructions now prohibit replaying work to
  observe progress or fabricating live milestones for a fast command.

## 2026-09-24 Background-Review Follow-Up

- Within the constrained `research-review-worker` profile, Sol high returned
  a schema-conforming review for one synthetic image. This does not establish
  equation or table accuracy on real research papers.
- Fake-model integration tests covered detached start, document-scope merging,
  status, retry after a partially saved batch, temporary rendered-image
  cleanup, and preservation of unrelated folders.
- On macOS, starting a second `codex sandbox` inside the reviewer profile
  failed with `sandbox_apply: Operation not permitted`. The reviewer now enters
  one profile and invokes the project-owned store command inside it. Status on
  the installed copy succeeded; its existing 33 pending pages were preserved
  without starting a review.
- The full automated suite passed 292 tests with 4 skips. A live permission
  integration test also denied source writes. Fresh-task loading of the new
  execution rule, visual accuracy on real papers, and subscription usage at
  scale remain to be checked separately.

## 2026-09-25 Review-Note Storage Audit

The 2026-09-25 read-only audit of the personal installed store found 5 documents
and 66 `verified` pages matched by 66 nonempty per-page Markdown notes. Stored
document identity, SHA-256, state, model, and review time matched; managed
sections were valid, and every current pending list was empty. Missing, empty,
duplicate, mismatched, or orphan notes and unfinished document journals all
numbered zero; SQLite `quick_check` passed. SHA-256 fingerprints of the database,
configuration, and five Markdown files (seven files total) were unchanged after the audit.
This store required no migration for this requirement.

The audit compared only that personal installation's database and Markdown. It
did not inspect older test or development copies, rehash source PDFs, establish
actual image inspection, or assess the notes' semantic accuracy, and it made no
new model calls. It does not establish that historical records in other stores
are consistent.

2026-09-25 validation record: 313 of 318 tests passed, with five environmental
skips. Three core regression tests also passed against the installed copy. This
validation made no new model calls.

## 2026-09-26 Development Instructions, Documentation, and Release Boundaries

Validation followed separation of development/product settings and extraction
of duplicated operating instructions into task-specific references. The version
remains `0.3.0`; the archive below was built for local validation. This work did
not publish a new Release or web deployment.

| Check | Result |
| --- | --- |
| Full automated suite with the actual archive | 359 passed out of 364; 5 environment-dependent checks skipped |
| Actual install, search, and removal in temporary HOME | Passed; checked skill/agent registration, original contents and modification time, and removal into temporary Trash |
| Release contents | Archive matched all 52 allowed product files; development AGENTS, config, and checking tools excluded |
| Product settings | Semantically identical TOML to the former product settings; only `resources/codex.runtime.toml` supplies the shipped config |
| Korean, English, and web installation instructions | Command, download URL, and version checks passed, including deliberately inconsistent guide fixtures |
| Documentation moves | Checked 488 local Markdown links, all former README heading anchors, and preservation of 22 code/diagram blocks per language |
| Skill and agents | Official skill-format validation and registration tests passed; Luna xhigh and Sol high preserved |

Skipped checks cover one nested macOS notification sandbox integration, two
opt-in attachment/storage permission integrations, and two tests requiring a
filesystem that preserves case-distinct filenames. These results do not establish
permissions, notifications, or subscription model behavior on a new Mac. No real
user installation or research originals were used. No new visual model calls,
subscription usage measurements, or processing-speed measurements were made.

An independent instruction review followed numeric comparison across two PDFs,
same-title conversation updates with legacy/revision conflicts, and one invalid
file among three attachments. It exposed a missing documented route for a
verified page whose note lacks a required value; the existing `render-review
--page` command is now documented. This was a written workflow review, not a
measurement of actual Codex model behavior.

To reproduce, assemble the archive using the allowlist step in the
[release workflow](../../../../.github/workflows/release-check.yml), then set
`RESEARCH_AGENT_RELEASE_ARCHIVE` to its absolute path when running the full suite.
Without that variable, two archive tests also skip. Check versions and guides with:

```sh
.venv/bin/python -B scripts/check_release_version.py
.venv/bin/python -B scripts/check_guides.py
```

## 2026-09-26 Usage Help Reading Scope and Installed Update

The installed bundle selected by the personal skill still had a 430-line
`SKILL.md` with every workflow inline. An introduction loaded that file, and
operational setup preceded the help branch. The original user test's complete
trace was unavailable, so this finding does not prove that it also read every
additional reference.

The introduction now branches first and reads only the relevant sections of the
existing README. Six skill documents were updated in the installed bundle after
backup, saving references before replacing the entrypoint. Its entrypoint is now
89 lines. Folder instructions also account for the older bundle's missing
selection helper rather than prescribing an unsupported call.

| Check | Result and scope |
| --- | --- |
| Installed documents | Six files match the development copy. The existing conversation payload reference was unchanged |
| Protected state | Runtime/configuration hashes and research data sizes, modification times, and inodes match before and after |
| Registration and packaging references | Fourteen relevant tests passed using temporary environments; actual personal registration was not rerun |
| Guide consistency | Installation commands and versions agree; the public installer still targets v0.3.0 |
| Independent behavior | An agent without conversation history received the installed skill and the Korean equivalent of “What can you do, and how do I get started?” It used three commands: read the skill, resolve the root read-only, and read the two introductory README sections |
| Unnecessary operations | That run did not read runtime rules, task references, or research data, check status, delegate work, or write files |

The basic skill validator could not run because both the project and bundled
Python lacked PyYAML. Automated tests cover references and registration; the
independent check covers one introduction request. They do not establish the
behavior of every Codex app session or refresh instructions already loaded into
an existing conversation. A fresh user conversation remains the next guide
capture. The public Release and runtime code were not changed in this update.

```sh
.venv/bin/python -B -m unittest tests.test_release_bundle.RuntimeManifestTests tests.test_personal_registration
.venv/bin/python -B scripts/check_guides.py
```

## Reproduce the Automated Checks

From the repository root, run the following command to replay the core recovery,
concurrency, and fault-injection checks without changing research originals or
personal registration:

```sh
./scripts/reproduce-validation.sh core
```

Use `full` instead of `core` for the complete automated suite. Run
`./scripts/reproduce-validation.sh permission` separately in a normal macOS
terminal to exercise the real permission profile. That check removes its
temporary source and probe files when it finishes.

The replay command does not include the live Luna-to-Sol run because that run
consumes subscription usage and temporarily changes the active personal
registration. The result above came from a live Codex run against an isolated
store copy.

## Interpretation and Remaining Scope

Subagents can inherit the parent turn's active permission mode and have live
overrides such as `/permissions` or `--yolo` reapplied. The `read-only` default
in an agent TOML is therefore not an enforcement boundary under a Full access
parent. The recorded permission results cover the constrained storage command
and workflows with a read-only parent. The current usage policy allows Ask for
approval and Approve for me and prohibits Full access; a read-only parent is an
optional stronger restriction. This experiment did not validate all effective
parent and child permissions or approval exceptions in both approval modes. See
the official
[Codex subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)
for this behavior.

Permission profiles are beta, and a legacy `sandbox_mode` in any loaded
configuration can cause Codex to choose the older sandbox settings. This is why
the regression fix isolates the configuration stack. After Codex upgrades, the
official [permissions documentation](https://learn.chatgpt.com/docs/permissions)
and the live integration test must be checked again.

The prompt-injection result covers one controlled scenario. It is not a
universal guarantee against every malicious document; additional instruction
styles, hidden text, and composite documents still require testing.

The empty-HOME test reproduced an unconfigured user on the current Mac. The
non-developer experience from developer-tool installation onward has not been
validated on a physically new Mac.

Separate journals and locks now protect the saved-conversation lifecycle and
PDF synchronization and visual-review writes. Forced-exit validation injected
`os._exit` in a child process; it did not physically power off the Mac or inject
a storage-device failure. PDF equation, table, and figure accuracy and Plus/Pro
usage measurement were outside this validation. The task-level token count from
the progress integration run is recorded as a preliminary observation in the
[subscription usage experiment](./subscription-usage.md).


<a id="conversation-pty-2026-10-01"></a>

## Long terminal input for conversation saves · 2026-10-01

The user's confirmed conversation save failed. Tool records show that the exact
personal launcher started, but the long single-line JSON sent to its PTY was
partly echoed and followed by BEL bytes and a stalled reader. A noninteractive
invocation received EOF without JSON. A subsequent Node child-process call failed
with `sandbox-exec: sandbox_apply: Operation not permitted`. The personal execution
rule existed; the final denial does not establish a missing permission rule as
the cause of the original failure.

A synthetic macOS PTY reproduced the canonical-input failure: 12,045 input bytes
produced 11,021 BEL bytes and the reader did not finish within eight seconds. Only
the disposable process was stopped; no live library or original PDF was changed.

The CLI now prepares terminal text input without canonical buffering, echo, or
byte-transforming input flags, then emits `__RESEARCH_STORE_STDIN_READY__` on
stderr. The caller waits for READY before sending JSON and the existing end
sentinel. Original terminal settings are restored after success, errors, and
Ctrl-C. Pipes, EOF, size limits, launchers, permission profiles, execution rules,
and model routing remain unchanged.

Validation:

- Ten focused stdin tests passed, covering exact PTY transcript storage, CRLF and
  input-byte preservation, malformed JSON/UTF-8, size limits, unsupported/setup
  failures, Ctrl-C, and terminal restoration.
- The developer's focused run passed 36 tests including 24 conversation-management
  cases and two existing CLI pipe cases. A separate run passed 35 stdin,
  conversation-management, and runtime-manifest checks.
- A disposable installation and HOME used the actual public personal launcher and
  `research-store` permission profile. A **92,183-byte** Korean JSON payload was
  stored exactly without echo/BEL; terminal restoration and denial of writes to
  an external synthetic original, with its hash preserved, passed. The fixture
  used a test CLI entrypoint and does not validate a complete fresh installation.
  There were no live library writes or model calls.
- Version and Korean/English/web guide checks passed. Skill frontmatter is unchanged
  and references were checked by the runtime-manifest test. The shared
  `quick_validate.py` could not run because PyYAML is unavailable.

- Final focused regression in the development checkout ran 78 cases: 76 passed,
  two skipped because the filesystem does not preserve case-distinct filenames:
  `test_case_variant_pdfs_are_converted_to_distinct_markdown` and
  `test_colliding_legacy_document_paths_migrate_deterministically`.
- Actual Codex `exec_command(tty: true)` and `write_stdin` also stored a 28,711-byte
  synthetic JSON payload exactly after READY, in 400-character chunks. A large
  single write was rejected by the tool's review-size limit, so smaller chunks
  were used. This disposable fixture used a temporary HOME in its environment
  and explicit development approval for execution outside the parent sandbox;
  it does not retest the user's default chat policy and personal execution rule.
- Independent review found no normal-path or permission-boundary regression.
  Restoration wording was narrowed to normal completion, handled errors, and
  Ctrl-C; restoration is not guaranteed after SIGTERM/SIGKILL.
- The current personal installation's CLI, two product-policy locations, and two
  conversation references were updated after backing up code. All 45 library
  files retained their content and modification times. Personal registrations
  and permission profiles were unchanged; disposable test stores were removed.

After retrying the same confirmed scope, the user supplied a completion reply
reporting that the DistilBERT/MobileBERT mobile sentence-classification experiment
plan and selection criteria were saved and checked again. It reports four selected
verbatim messages, a summary, and the final selection criterion. The result portion
is preserved in the [conversation-save guide capture](../../../site/assets/screenshots/conversation-save-result.png).
This evidence is a user-provided reply, not an independent inspection of the saved
transcript or database. The scope-choice screen and later search reuse remain
unverified.
