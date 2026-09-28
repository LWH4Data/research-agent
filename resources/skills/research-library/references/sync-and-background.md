# Sync, requests, and background review

Use the absolute installed `research-review` launcher directly. The manager may
run managed intake; it never opens images or writes visual notes itself. The
managed command fixes Luna xhigh management and Sol high visual execution.

## One request, one durable receipt

Before storage, call `research-review key`. Keep its `key` and
`key_expires_at` in the current tool/task record. The key embeds its immutable
expiry (`vr2.<expiry-epoch>.<random-key>`). Use that exact key, expiry, initial
scope, and initial guidance settings on a retry. A new user request gets a new
key even when it targets the same PDF. Do not fabricate a replacement key to
make an expired or forgotten request resume.

Call `research-review submit --key <key> --key-expires-at <epoch> --spec-stdin`
and send minimal JSON through process stdin, followed by the standalone
`__RESEARCH_STORE_STDIN_END__` line. Never use a payload file, shell pipeline,
redirection, or transcript/question text as operational metadata. Examples of
individual items in the `items` array:

- Attachment: `{ "item_id": "attachment-1", "attachment": "/exact/file.pdf" }`.
- Existing stored PDF: `{ "item_id": "paper-1", "document_key": "source-id:paper.pdf", "sha256": "<current digest>", "incarnation": "<current storage ID>", "pages": [1, 3] }`.
- Connected source sync: `{ "item_id": "source-1", "source_id": "<exact registered ID>" }`.

A successful public `source-add` in the managed folder flow already performs
intake. Reuse its `processing` receipt; do not follow it with another submit.
For a separate request to update connected folders, obtain the exact registered
IDs first. Include only the
requested source items. The command freezes a source inventory before text
conversion, persists committed item receipts, and links only those versions.
A retry does not adopt newly added files or a changed PDF. Attachment intake
uses the host's existing read-only binary bridge, targeted text conversion,
and exact document links; it never scans unrelated folders or saved attachments.

One managed submit performs intent → text storage → review links → detached
handoff. Do not ask the model to remember a second start operation. `prepare`
is a recovery primitive, not the normal user save path. `start` is an alias of
managed submit and also requires the exact specification and key.

A receipt contains `request_id`, per-item successes/failures, linked page scopes,
current evidence, guidance/accounting, expiration, and a handoff result. Two
requests may share an execution while keeping different scopes and counts. A
spawned PID means preparing; only an executor acknowledgement means running.
`starting_unconfirmed` is neither success nor failure. If startup fails, text
remains searchable and the saved request is available for explicit resume.
Return control once text and handoff are known. Text-based answers may proceed
while visual evidence is pending. Evidence readiness does not mean the user's
question was answered, or that any notification was seen.

## Status and user controls

Use `status --request <request_id>` for this request; use `status` only for an
intentional library-wide overview. Count each link's committed `verified`
outcomes separately from `needs_review`, failures, and pending pages. Do not
infer proof from disappearance from the pending queue. Reconciliation checks
current SHA, incarnation, committed notes, and accepted journals.

Use one exact scope with `pause`, `cancel`, or `resume`:

- `--request <id>` detaches or pauses only this request. Other requests may keep
  shared work running; explain that effect.
- `--document <key>` stops that PDF's shared review. Document cancellation
  suppresses automatic review across ordinary sync and new versions. A new
  explicit review request can authorize the specified current version.
- `--library` persists a whole-library dispatch hold. Text storage and search
  still work. Later intake, retry, or document resume cannot clear this hold;
  only explicit library resume clears it. Independent pauses/cancellations stay.

Treat time/cost-driven “stop” as stopping the requested execution scope, not
muting notifications. Use request-only detachment only when the user asks to
cancel just their request. When context identifies one scope, act. Clarify only
if several scopes remain plausible. A response saying `stopping` means commits
are fenced but physical exit remains unconfirmed; do not call that stopped.

Time and page-attempt guidance is optional (`--warn-seconds`, `--warn-pages`,
`--warning-ratio`). No execution-time or page-count threshold is enabled by
default. Guidance warns only: crossing it does not pause, cancel, reduce a batch,
or require a budget extension. The user decides when to stop. Queue/paused time
is excluded from active execution accounting; retries remain cumulative. Late
joiners are not charged for a call already reserved. Tokens missing after a
failure remain unknown. Never estimate plan quota from tokens/pages/time.

Inactive requests have a displayed `expires_at`; the initial retention policy
is 30 days and is configurable with `--retention-seconds`. Polling and another
request's work do not extend it. Expired links immediately lose authority even
before cleanup runs. `cleanup` removes expired owned operational records when
safe; it preserves originals, committed notes, and live shared resources.
`forget --request <id>` revokes that request and keeps only a bounded key denial
marker after safe cleanup. `delete-document <key>` is a separate explicit user
action: stop/reconcile first, then remove only the document's owned material and
keep a source collection exclusion. Never interpret source removal as deletion.

## Evidence, notifications, and progress

`needs_review` is unresolved evidence and is not retried indefinitely. An
explicit correction uses the exact current version/pages with `rereview: true`
in that item. Add `--wait` for explicitly synchronous work; interrupting the
foreground wait does not erase the detached request. Use the visual reference
for image-evidence rules and read-only targeted inspection.

Check saved `notification_watcher` before claiming macOS alerts work. The
separate host watcher sends generic, best-effort completion/failure notices and,
after five minutes, newly crossed 25%, 50%, and 75% milestones. Processed counts
may include uncertain pages but never label them verified. Warning delivery
failure cannot stop review. These are OS notices, never unsolicited messages
into another Codex task. Status remains authoritative.

For foreground text progress, accept only stderr `RESEARCH_PROGRESS ` JSON
with `type=research_progress`, `schema_version=1`, and `operation=sync`. Display
phase changes, errors, and useful count milestones in the user's language.
Show source locations as the inventory denominator, then durably processed PDFs,
then visually verified pages. Keep `needs_review` separate. Do not fabricate
live progress when a command has already finished. Keep the original process
session until completion; never start another sync just to repeat the display.
Source access failures preserve prior records and are not zero-result success.

Existing v1 job records require `migrate --confirm-legacy-exit` only after old
worker and child exit is confirmed. Migration refuses live locks/processes,
keeps library material, and never invents historical request consent. Never
bypass this boundary or manually remove its lock files.
