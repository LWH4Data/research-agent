# Safety and Agent-Routing Validation

[한국어](./safety-routing-validation.md) | [English](./safety-routing-validation.en.md)

Validation date: 2026-09-22

This record captures the live validation performed for storage recovery,
permissions, prompt injection, and model routing issues found before prototype
release.

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
  invoke Sol as a nested agent in this custom-agent environment, so the primary
  session now coordinates both agents directly.
- A separate Luna xhigh Codex session ran the JSONL progress stream exactly
  once. Phase `1/3` reached commentary before command completion; the more
  closely spaced `2/3`, `3/3`, and completion events arrived together just
  after that same command finished. Instructions now prohibit replaying work to
  observe progress or fabricating live milestones for a fast command.

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
parent. The parent session that invokes Research Library must be read-only. See
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
[subscription usage experiment](./subscription-usage.en.md).
