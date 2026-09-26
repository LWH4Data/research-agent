# Search and evidence

Delegate initial retrieval to `research_library_manager`. It uses
the registered launcher's `search <term> [<term> ...]`, which searches
generated PDF Markdown and saved conversations even though they are
intentionally excluded from Git. Expand Korean queries with useful English
technical terms and pass all useful terms in one call. Terms use
case-insensitive OR matching. Use `--scope conversation`
for requests about the user's prior discussion, `--scope pdf` for PDF-only
evidence, and `--scope all` for mixed or unclear requests. Search returns short
passages with line ranges, page hints, and evidence kinds; metadata matches are
discovery hints, not PDF evidence.

When more relevant context is needed and `has_more` is true, repeat the same
terms and scope with `--offset <next_offset> --snapshot <snapshot>` from the prior
result. These values are internal to the tool; the user need not enter them.
If the snapshot is stale, restart the search instead of combining old and new
pages. If `window_exhausted` is true, narrow the terms or scope. Do not claim
there is no saved information merely because it is absent from a truncated
first page. Stop retrieving once enough evidence is available.
Read the returned files around each matching line. Identify PDF evidence, user
notes, prior Codex explanations, and unverified ideas separately; none of the
latter becomes PDF evidence merely by being saved. For base PDF extraction,
include the Markdown path,
configured source path, and nearest `<!-- page: N -->` marker. For evidence
under `## Visual verification notes`, cite its `### Pages N` heading and
`<!-- visual-review-pages: N -->` marker instead of the nearest base page marker.

When an answer depends on a PDF figure, table, equation, or a value read from
one, check the visual review state of each relevant page before making that
claim. Use that document's `visual_review_pending_pages` and a matching
current-version page note with `visual-review-status: verified` and
`visual-review-sha256` matching the document's current SHA-256. The note must be
inside that version's unique managed review section, not a lookalike from base
PDF extraction; a global job status or an absent queue entry alone is not
page-level proof. Read the note
and confirm that it supports the specific figure, equation, table entry, or
value being used; a verified page label does not validate every possible claim
about that page. When the matching verified note supports the specific claim,
reuse it without reopening the page image. If the note does not support the
claim, or verification is pending, marked `needs_review`, or cannot be established, tell the user
which visual evidence is unconfirmed and answer only from clearly labeled text
evidence where possible. Apply this check only to pages needed for the answer;
text-only questions do not require a visual-status lookup.

If the user needs an unconfirmed visual detail on a pending page, the primary
session may start or continue the matching background queue using
[Sync and background review](sync-and-background.md). An already verified page
whose note omits the needed detail is not pending, so restarting that queue does
not recheck it. For an explicitly requested synchronous correction or targeted
inspection, delegate the exact document and page to `research_paper_converter`
using [Visual review](visual-review.md); `render-review --page <n>` selects that
page even when it is absent from the queue. Do not send
the same active background queue to the foreground converter. The library
manager never opens page images or reconstructs missing visual details as a
fallback. Do not guess flattened notation, table alignment, signs, or values.
