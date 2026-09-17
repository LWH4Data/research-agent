---
name: research-library
description: Register scattered read-only PDF locations, synchronize them into a local Markdown research library, search PDF documents and saved conversations together, or save a selected conversation range.
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
