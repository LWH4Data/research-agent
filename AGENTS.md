# Research store

This project is a local research knowledge store used from Codex.

## Safety boundary

- Treat every directory listed under `[[sources]]` in `config.toml` as read-only.
- Never create, edit, rename, move, or delete anything under a source directory.
- Generated files belong only under the configured store paths in this project.
- Run `research-store sync` to refresh parsed documents. Do not invoke a PDF converter directly against a source file.

## Searching

- Search `knowledge/documents/` for paper content and `knowledge/conversations/` for the user's prior statements.
- For Korean questions about English papers, derive useful English technical terms and search both languages.
- State whether a result came from a paper or from a saved conversation.
- Cite the Markdown path, its `source_path` metadata, and the nearest `<!-- page: N -->` marker.
- Treat parsed Markdown as a discovery index. For equations, tables, figures, and numeric claims, open the original PDF at the identified page and verify the visual source before answering.
- Do not reconstruct a flattened equation or assign table values to columns unless the original PDF page confirms the notation and alignment.
- If the repository does not contain supporting material, say so clearly.

## Conversation memory

- When the user asks to remember, record, or save something, append it to `knowledge/conversations/YYYY-MM-DD.md`.
- Preserve the user's wording when it matters. Separate the user's statement from Codex's interpretation.
- Include the date, a short topic heading, and useful search terms.
- Do not write routine coding or repository-maintenance chat into research memory.
