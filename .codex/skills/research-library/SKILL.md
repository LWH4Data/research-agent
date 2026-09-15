---
name: research-library
description: Synchronize scattered read-only PDF directories into a local Markdown research library, search papers and saved conversations together, or save a user-selected conversation range when the user asks to remember or record research context.
---

# Research Library

Use this repository as the user's persistent research memory. Read `AGENTS.md`
for source protection, evidence labels, and model routing.

## Synchronize papers

Delegate sync and state management to `library_manager`. It scans metadata for
all configured roots but parses only new or changed PDFs. When its review queue
contains equations, tables, figures, or extraction failures, delegate those pages
to `paper_converter`; do not ask the user to change models.

## Search

Search `knowledge/documents/**/*.md` and
`knowledge/conversations/**/*.md` together. Use Korean and English technical
terms when the query crosses languages. Identify each result as paper evidence,
a user note, or a prior Codex explanation. For papers, include the Markdown path,
configured source path, and nearest `<!-- page: N -->` marker.

## Save a conversation

When the user asks to remember, record, or save conversation content, always ask
one scope question before writing. Offer concrete choices based on the visible
conversation:

1. The current topic, naming its inferred starting message.
2. The entire current conversation.
3. A range the user describes.

After the user chooses, do not ask for another confirmation. Delegate the save
to `library_manager`. Store both a search-oriented summary and the selected
messages verbatim. Preserve the distinction between user ideas, decisions,
unverified claims, and paper-backed evidence.

Read [references/conversation-payload.md](references/conversation-payload.md)
when preparing the save payload.
