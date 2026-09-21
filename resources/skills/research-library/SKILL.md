---
name: research-library
description: Register scattered read-only PDF locations, synchronize them into a local Markdown research library, search PDF documents and saved conversations together, or save, list, update, and delete selected conversation memories.
---

# Research Library

Use the separately installed research-agent store as the user's persistent
research memory. Treat the directory containing this `SKILL.md` as `SKILL_DIR`;
never resolve its relative paths from the current project. At the start, run the
absolute `SKILL_DIR/scripts/research-root` path and treat its single output as
`STORE_ROOT`. Verify and read `STORE_ROOT/AGENTS.md` for the mandatory source
boundary, evidence labels, and model routing. Use the absolute
`SKILL_DIR/scripts/research-store` launcher for every library command. Never
request write access to a registered source.

## Manage source locations

Delegate source listing and exact-path registration to
`research_library_manager`. It uses `SKILL_DIR/scripts/research-store
source-list` and `SKILL_DIR/scripts/research-store source-add <path>`. If no
path is available, ask the user to run the absolute
`bash "$STORE_ROOT/add-source.sh"` command in a normal terminal so the native
folder picker can open.

Removing a source uses `SKILL_DIR/scripts/research-store source-remove <id>` through
`research_library_manager`. Explain that this disables future scans while
retaining the original-path mapping. Its existing Markdown snapshot remains
searchable, and neither originals nor generated Markdown are deleted. Adding
the same path later re-enables it.

## Synchronize PDF documents

Delegate sync and state management to `research_library_manager`. It scans registered
locations but parses only new or changed PDFs. Do not assume every PDF is a
paper. When the review queue contains equations, tables, figures, or extraction
failures, delegate those pages to `research_paper_converter`; do not ask the user to
change models. The visual reviewer must submit notes through
`review-complete --visual-notes-stdin`, followed by a newline and the exact
standalone `__RESEARCH_STORE_STDIN_END__` line, and must never edit Markdown or
assets directly.

If no source is registered, tell the user to run
`bash "$STORE_ROOT/add-source.sh"` in a normal terminal. If a
source is offline or unreadable, report that path and its error while preserving
its prior document state. Do not describe an incomplete scan as zero results.

## Search

Delegate initial retrieval to `research_library_manager`. It uses
`SKILL_DIR/scripts/research-store search <term> [<term> ...]`, which searches
generated PDF Markdown and saved conversations even though they are
intentionally excluded from Git. Expand Korean queries with useful English
technical terms and pass all useful terms in one call. Read the returned files
around each matching line. Identify each result as PDF evidence, a user note, or
a prior Codex explanation. For base PDF extraction, include the Markdown path,
configured source path, and nearest `<!-- page: N -->` marker. For evidence
under `## Visual verification notes`, cite its `### Pages N` heading and
`<!-- visual-review-pages: N -->` marker instead of the nearest base page marker.

## Save a conversation

When the user asks to remember, record, or save conversation content, always ask
one scope question before writing. Offer concrete choices based on the visible
conversation:

1. The current topic, naming its inferred starting message.
2. The entire current conversation, only when every message is available
   verbatim in the active context.
3. A range the user describes.

After the user chooses, do not ask for another confirmation. Delegate the save
to `research_library_manager`. Store both a search-oriented summary and the selected
messages verbatim. Preserve the distinction between user ideas, decisions,
unverified claims, and paper-backed evidence. Pass the JSON only through
`save-conversation` process stdin, followed by a newline and the exact
standalone `__RESEARCH_STORE_STDIN_END__` line; never create a payload file or
edit the saved Markdown directly. EOF remains supported for compatibility.

Never reconstruct compacted or unavailable messages. If the requested range is
only partly visible, save the available exact messages with
`capture_status: partial` and a clear `capture_note`; do not present the record as
a complete transcript.

Read [references/conversation-payload.md](references/conversation-payload.md)
when preparing the save payload.

## Manage saved conversations

Let the user manage saved memories in natural language. Do not require them to
know or type an internal command, file path, or conversation ID in advance.
Delegate listing, identification, updates, and deletion to
`research_library_manager`; it uses the internal `conversation-list`,
`conversation-update`, and `conversation-delete` commands.

Use `conversation-list` to resolve the intended record before changing it. An
update or deletion must ultimately target one exact `conversation_id`, never a
title or Markdown path. Retain the selected record's `revision` and pass it as
the internal `--expected-revision` value for the mutation; the user does not
need to know this flag. If one record is an unambiguous match, proceed with the
user's requested update or deletion without another confirmation. If several
records match, show concise choices with title, saved time, and ID, and ask only
which record the user means. If none match, report that without changing
anything.

Match the natural-language request against the list's title, tags, and aliases.
If those fields are not enough, run `search` with useful terms from the request,
keep only `conversation` results, and join each result path back to the exact
path and ID returned by `conversation-list`. Read a small number of candidate
Markdown records when context is still needed. Never guess an ID from a title or
search result alone.

Updates may change only search-oriented organization. The exact JSON keys are
`title`, `summary`, `tags`, `aliases`, `user_points`, `decisions`, `unverified`,
`open_questions`, and `related_documents`. `conversation-update` requires the
exact conversation ID, `--expected-revision`, and one complete JSON object
containing all of those mutable fields. For a partial user request, read the
current Markdown at the path returned by `conversation-list` and carry its other
editable values forward; do not omit fields. Never include unknown or immutable
fields. Preserve the stable conversation ID, selected transcript, scope,
original `created_at`, and transcript-capture metadata. A successful update
advances `revision` and `updated_at`. If the transcript or selected range is
wrong, delete the saved record and save the correct range again instead of
rewriting quoted history.

Deletion permanently removes only the matching conversation Markdown and its
SQLite record from Research Agent. It does not delete the actual Codex
conversation, PDFs, PDF-derived Markdown, or other saved conversations. Clearly
state this boundary in the result. There is no conversation trash or undo in the
current prototype.

If `conversation-list` reports `available: false`, the Markdown is already
missing. An update must stop because the immutable transcript cannot be
verified. A deletion may still remove that exact orphaned SQLite record when
its ID and expected revision match; report that no Markdown file remained to
delete.

If an update or deletion reports a revision mismatch, it made no change. Run
`conversation-list` again, re-read the exact record, and rebuild the operation
from its latest revision and content. Never retry with the stale JSON or stale
revision. If concurrent changes keep preventing the operation, report the
conflict instead of looping.

For updates, construct the complete mutable JSON object in memory and send it
only through the command's process-stdin interface using the same 8 MiB limit
and sentinel protocol as conversation saving.
Never create a payload file, use shell redirection or a here-document, or edit
conversation Markdown or SQLite directly. Use the constrained commands for
deletion as well; never remove a Markdown file with a general filesystem
command.
