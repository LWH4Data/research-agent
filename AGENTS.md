# Research store

This project is a local research knowledge store used from Codex.

## Agent routing

- Delegate library synchronization, status, conversation saves, and broad
  retrieval to the project-scoped `library_manager` agent in
  `.codex/agents/library-manager.toml`. It runs on GPT-5.6 Luna at xhigh effort.
- Delegate only queued equation, table, figure, and layout pages to the
  project-scoped `paper_converter` agent in
  `.codex/agents/paper-converter.toml`. It runs on GPT-5.6 Sol at high effort.
- The user should never need to select either agent or change models manually.
- Use the project-local `research-library` skill for synchronization, retrieval,
  and conversation-memory requests.

## Safety boundary

- Treat every directory listed under `[[sources]]` in `config.toml` as read-only.
- Never create, edit, rename, move, or delete anything under a source directory.
- Generated files belong only under the configured store paths in this project.
- Run `research-store sync` to refresh parsed documents. Do not invoke a PDF converter directly against a source file.
- Directory scans may read file metadata. PDF content is read only for new or
  changed files identified by the SQLite ledger.

## Synchronizing

- `uv run research-store sync` parses new or changed PDFs and leaves unchanged
  files alone.
- `uv run research-store review-list` returns pages that need visual inspection.
- Send only those pages to `paper_converter`. It must render them through
  `research-store render-review`; it must never write beside the source PDF.
- Report new or changed documents, unchanged documents, missing originals,
  failures, and pending page reviews in plain language.

## Searching

- Search `knowledge/documents/` for paper content and `knowledge/conversations/` for the user's prior statements.
- For Korean questions about English papers, derive useful English technical terms and search both languages.
- State whether a result came from a paper or from a saved conversation.
- Cite the Markdown path, its `source_path` metadata, and the nearest `<!-- page: N -->` marker.
- Treat parsed Markdown as a discovery index. For equations, tables, figures, and numeric claims, open the original PDF at the identified page and verify the visual source before answering.
- Do not reconstruct a flattened equation or assign table values to columns unless the original PDF page confirms the notation and alignment.
- If the repository does not contain supporting material, say so clearly.

## Conversation memory

- When the user asks to remember, record, or save conversation content, ask one
  question to determine the range: the current named topic, the entire current
  conversation, or a range the user describes.
- Once the user chooses, save without another confirmation.
- Store one structured Markdown file per save under
  `knowledge/conversations/YYYY/MM/` by using
  `research-store save-conversation` and the payload schema in the
  `research-library` skill.
- Preserve every selected user message verbatim. Also include a search summary,
  bilingual aliases when helpful, decisions, unverified claims, open questions,
  and related paper/page links.
- Separate the user's statement from Codex's interpretation and from paper
  evidence. A prior assistant answer is not paper evidence.
- Do not write routine coding or repository-maintenance chat into research memory.
