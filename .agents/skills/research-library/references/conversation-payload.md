# Conversation payload

Construct the UTF-8 JSON object in memory, start `./research-store
save-conversation`, and send the JSON through the process stdin facility. Then
send a newline, the exact standalone line `__RESEARCH_STORE_STDIN_END__`, and a
final newline. The command consumes this line and finishes even if the process
stdin pipe remains open. Ordinary EOF is also accepted for compatibility. The
UTF-8 JSON may be sent in chunks but must not exceed 8 MiB. Never create an
intermediate payload file and never use shell redirection or a here-document.
The CLI validates the object and writes the final Markdown atomically.

Required fields:

```json
{
  "title": "PDF 수식 변환 설계",
  "scope": "current-topic",
  "capture_status": "complete",
  "summary": "검색을 위한 간결하고 사실적인 요약",
  "transcript": [
    {"role": "user", "content": "선택 범위의 정확한 사용자 발언"},
    {"role": "assistant", "content": "선택 범위의 정확한 Codex 답변"}
  ]
}
```

`scope` is one of `last-exchange`, `current-topic`, `entire-conversation`, or
`custom`.

`capture_status` is `complete` only when every message in the selected range is
available verbatim in the active context. If compaction or missing history means
any selected message is unavailable, use `partial` and add a factual
`capture_note` describing what could not be recovered. Never reconstruct missing
messages and label them as verbatim.

Useful optional fields:

```json
{
  "created_at": "2026-09-15T15:30:00+09:00",
  "capture_note": "",
  "language": ["ko", "en"],
  "tags": ["PDF", "수식"],
  "aliases": ["equation extraction"],
  "user_points": ["사용자가 제안한 내용"],
  "decisions": ["명시적으로 결정한 내용"],
  "unverified": ["논문으로 확인되지 않은 주장"],
  "open_questions": ["아직 답하지 못한 질문"],
  "status": ["design-decision"],
  "related_documents": [
    {"path": "../documents/source/paper.md", "pages": [4, 5]}
  ]
}
```

Do not summarize away selected user messages: the transcript exists so later
queries such as "내가 그때 뭐라고 했더라?" can return the exact wording.
