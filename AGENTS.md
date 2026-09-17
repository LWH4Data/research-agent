# Research store

This project is a self-contained local research knowledge store used from Codex.

## Non-negotiable source boundary

- Every configured source is read-only. Never create, edit, replace, rename,
  move, chmod, chown, or delete a source file or anything beside it.
- Never place sidecar Markdown, indexes, hidden files, locks, or caches in a
  source. All generated data belongs under this project root.
- Never add a source path to Codex writable roots or request broader filesystem
  access. If the sandbox blocks an operation, stop and report it.
- Never use a source directory inside this project, and never register a source
  that contains this project. `research-store` enforces both directions.
- Use `./research-store` for source, sync, render, review-state, and conversation
  operations. Do not invoke converters directly on an original PDF. During
  library operation, never create or edit generated Markdown, assets, config, or
  payload files directly; pass content to the CLI through process stdin so its
  hard-link and atomic-write checks always run.
- Removing a source disables future scans while retaining its source mapping. It
  never deletes the original or generated Markdown, so the existing snapshot
  remains searchable and traceable.

## Agent routing

- Delegate source management, synchronization, status, saved-conversation
  creation, and broad retrieval to `research_library_manager` in
  `resources/agents/research-library-manager.toml`.
- Delegate only queued equation, table, figure, and layout pages to
  `research_paper_converter` in
  `resources/agents/research-paper-converter.toml`.
- The user never needs to select an agent or model manually.
- Use the personal skill registered from
  `resources/skills/research-library/SKILL.md`.

## Commands

- `./research-store source-list` lists registered read-only locations.
- `bash ./add-source.sh` opens the native folder picker from a normal terminal.
- `./research-store source-add <path>` registers an explicitly supplied folder
  or PDF. It only changes this project's `.research-store/config.toml`.
- `./research-store source-remove <id>` stops scanning a location without
  deleting any file.
- `./research-store sync` parses new or changed PDFs.
- `./research-store search <term> [<term> ...]` searches generated PDF
  Markdown and saved conversations together. Use this command instead of plain
  `rg` because generated knowledge is intentionally excluded from Git.
- `./research-store review-list` lists pages requiring visual inspection.
- `./research-store render-review <document-key>` renders only queued pages into
  the project-owned temporary directory and returns their document SHA-256.
- `./research-store review-complete <document-key> --page <n> --sha256 <hash>`
  with `--visual-notes-stdin` records stdin notes only if the database and current
  original still match the rendered version.
- `./research-store save-conversation` accepts the structured conversation JSON
  only through process stdin and writes the searchable Markdown atomically.

For either stdin command, send the UTF-8 body, a newline, the exact standalone
line `__RESEARCH_STORE_STDIN_END__`, and a final newline. The command consumes
that line and can finish while the caller's pipe remains open. Plain EOF remains
supported for compatibility. Conversation JSON is limited to 8 MiB and visual
review notes to 1 MiB.

Report new or changed documents, unchanged documents, missing originals,
failures, and pending page reviews in plain language.

If no source is registered, say so and direct the user to `bash
./add-source.sh`. If a source is disconnected or unreadable, report its path and
error. Do not mark that source's earlier documents missing, and do not present an
incomplete scan as an empty successful result.

## Searching

- Use `./research-store search` for initial retrieval so Git ignore rules cannot
  hide generated knowledge. Pass multiple Korean and English terms in one call;
  terms are matched case-insensitively with OR semantics.
- Read the returned Markdown files around the matching lines and inspect their
  frontmatter and page markers before answering.
- For Korean questions about English documents, search useful Korean and English
  technical terms.
- Label PDF evidence, user notes, prior Codex explanations, and unverified ideas
  separately.
- For evidence in the base PDF extraction, cite the Markdown path, its
  `source_path` metadata, and the nearest `<!-- page: N -->` marker.
- For evidence under `## Visual verification notes`, cite that note's
  `### Pages N` heading and `<!-- visual-review-pages: N -->` marker. Do not
  attribute a visual note to the nearest base `<!-- page: N -->` marker.
- Treat Markdown as a discovery index. Verify equations, tables, figures, and
  numeric claims against the original page image before answering.
- Do not reconstruct flattened notation or table alignment without visual
  confirmation.

## Conversation memory

- When the user asks to save or remember conversation content, ask one question
  for the range: current named topic, entire conversation, or a described range.
- After the user chooses, save without another confirmation.
- Construct the JSON payload in memory and send it to `save-conversation` through
  the process stdin facility. Finish it with the exact standalone
  `__RESEARCH_STORE_STDIN_END__` line so the command does not wait for EOF.
  Never create a payload file, use shell redirection or a here-document, or edit
  the saved Markdown directly.
- Preserve selected user messages verbatim and separate user ideas, decisions,
  unverified claims, open questions, and PDF evidence.
- Mark `capture_status` as `complete` only when every selected message is
  available verbatim. For compacted or unavailable history, save only available
  exact text as `partial`, describe omissions in `capture_note`, and never
  reconstruct missing messages.
- Do not save routine repository-maintenance conversation as research memory.

## Removal

This project installs only one personal skill link, two custom-agent files, one
exact launcher rule, and one isolated permission profile outside the project.
Run `bash ./uninstall.sh` to remove those five owned registrations before moving
this project folder to Trash. It never writes into sources. Never include a
configured source in a deletion command.
