# Conversation payload

Pass a UTF-8 JSON object to
`uv run research-store save-conversation --payload <file>`.

Required fields:

```json
{
  "title": "PDF 수식 변환 설계",
  "scope": "current-topic",
  "summary": "검색을 위한 간결하고 사실적인 요약",
  "transcript": [
    {"role": "user", "content": "선택 범위의 정확한 사용자 발언"},
    {"role": "assistant", "content": "선택 범위의 정확한 Codex 답변"}
  ]
}
```

`scope` is one of `last-exchange`, `current-topic`, `entire-conversation`, or
`custom`.

Useful optional fields:

```json
{
  "created_at": "2026-09-15T15:30:00+09:00",
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
