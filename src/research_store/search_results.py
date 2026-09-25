"""Pure passage extraction and deterministic, document-diverse ranking."""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import hashlib
import json
import re
from typing import Iterable, Iterator


PAGE = re.compile(r"^<!-- page:\s*(\d+)\s*-->$")
REVIEW_PAGES = re.compile(r"^<!-- visual-review-pages:\s*([1-9][0-9]*(?:\s*,\s*[1-9][0-9]*)*)\s*-->$")
MAX_PASSAGE_LINES = 4
EXCERPT_WIDTH = 220


@dataclass(frozen=True)
class SearchHit:
    record_type: str
    path: str
    line: int
    end_line: int
    text: str
    matched_queries: tuple[str, ...]
    pages: tuple[int, ...] = ()
    section: str = ""
    evidence_kind: str = "body"
    document_id: str | None = None
    source_id: str | None = None
    source_path: str | None = None
    heading_match: bool = False
    content_digest: str = ""

    @property
    def score(self) -> int:
        # Repeated occurrences of one term do not increase relevance.
        # A heading alone often names a topic without supplying evidence.
        return (10 * len(self.matched_queries) - 2 * self.heading_match
                - 3 * (self.evidence_kind == "metadata"))

    @property
    def rank_key(self) -> tuple:
        return (-self.score, self.path, self.line, self.end_line)

    @property
    def duplicate_key(self) -> tuple:
        return (self.pages, self.section, self.evidence_kind, self.content_digest or self.text.casefold())

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.record_type, "path": self.path,
            "line": self.line, "end_line": self.end_line,
            "text": self.text, "matched_queries": list(self.matched_queries),
            "pages": list(self.pages), "section": self.section,
            "evidence_kind": self.evidence_kind, "document_id": self.document_id,
            "source_id": self.source_id, "source_path": self.source_path,
        }


def _excerpt(text: str, prepared: list[tuple[str, str]]) -> str:
    if len(text) <= EXCERPT_WIDTH:
        return text
    folded = text.casefold()
    first = min(folded.find(term) for _, term in prepared if term in folded)
    # Case folding can expand characters, so map back to an original index.
    offset = 0
    original = 0
    for original, character in enumerate(text):
        if offset >= first:
            break
        offset += len(character.casefold())
    start = max(0, original - EXCERPT_WIDTH // 3)
    end = min(len(text), start + EXCERPT_WIDTH)
    start = max(0, end - EXCERPT_WIDTH)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def extract_passages(
    lines: Iterable[str], record_type: str, path: str,
    prepared: list[tuple[str, str]],
) -> Iterator[SearchHit]:
    """Keep bounded neighboring matches; never cross a page or heading boundary.

    Metadata and page labels are untrusted citation hints, not tool instructions
    or proof of visual verification. Base and visual-review pages stay distinct.
    """
    metadata: dict[str, object] = {}
    frontmatter = False
    pages: tuple[int, ...] = ()
    section = ""
    evidence_kind = "body"
    pending: list[tuple[int, str, tuple[str, ...], bool]] = []
    authenticated_review = False
    pending_digest = hashlib.sha256()

    def finish() -> SearchHit | None:
        nonlocal pending_digest
        if not pending:
            return None
        source_id = metadata.get("source_id")
        source_path = metadata.get("source_path")
        source_id = source_id if isinstance(source_id, str) else None
        source_path = source_path if isinstance(source_path, str) else None
        identifier = metadata.get("id") if record_type == "conversation" else (
            f"{source_id}:{source_path}" if source_id and source_path else None
        )
        found = {term for _, _, terms, _ in pending for term in terms}
        result = SearchHit(
            record_type=record_type, path=path, line=pending[0][0],
            end_line=pending[-1][0], text="\n".join(item[1] for item in pending),
            matched_queries=tuple(term for term, _ in prepared if term in found),
            pages=pages, section=section, evidence_kind=evidence_kind,
            document_id=identifier if isinstance(identifier, str) else None,
            source_id=source_id, source_path=source_path,
            heading_match=any(item[3] for item in pending),
            content_digest=pending_digest.hexdigest(),
        )
        pending.clear()
        pending_digest = hashlib.sha256()
        return result

    for number, raw in enumerate(lines, 1):
        text = raw.strip()
        if number == 1 and text == "---":
            frontmatter = True
            continue
        if frontmatter:
            if text == "---":
                item = finish()
                if item:
                    yield item
                frontmatter = False
                evidence_kind = "body"
                continue
            key, separator, value = text.partition(":")
            if separator and key in {"source_id", "source_path", "document_id", "id"}:
                try:
                    metadata[key] = json.loads(value)
                except ValueError:
                    pass
            # Title and editable JSON duplicate the human-readable body.
            if key not in {"tags", "aliases", "source_path"}:
                continue
            item = finish()
            if item:
                yield item
            evidence_kind = "metadata"
        marker = PAGE.fullmatch(text)
        visual_marker = REVIEW_PAGES.fullmatch(text)
        heading = text.startswith("#")
        control = text.startswith("<!--")
        if marker or visual_marker or heading or control:
            item = finish()
            if item:
                yield item
            if text.startswith("<!-- visual-review-section-begin:"):
                digest = metadata.get("document_id")
                authenticated_review = (
                    isinstance(digest, str) and
                    text == f"<!-- visual-review-section-begin: {digest} -->"
                )
                pages = ()
                evidence_kind = "visual-review"
            elif marker and not authenticated_review:
                pages = (int(marker.group(1)),)
                evidence_kind = "body"
            elif text.startswith("<!-- visual-review-pages:"):
                pages = (tuple(int(value.strip()) for value in visual_marker.group(1).split(","))
                         if visual_marker and authenticated_review else ())
            elif text.startswith("<!-- visual-review-section-end:"):
                authenticated_review = False
                pages = ()
                evidence_kind = "body"
            if heading:
                section = text.lstrip("# ")
                if text == "## Visual verification notes":
                    pages = ()
                    evidence_kind = "visual-review"
                elif evidence_kind == "visual-review" and text.startswith("### Pages "):
                    pages = ()
            if control:
                continue
        terms = tuple(term for term, normalized in prepared if normalized in text.casefold())
        if not terms:
            item = finish()
            if item:
                yield item
            continue
        pending.append((number, _excerpt(text, prepared), terms, heading))
        pending_digest.update(json.dumps(text.casefold(), ensure_ascii=False).encode("utf-8"))
        if heading or frontmatter or len(pending) >= MAX_PASSAGE_LINES:
            item = finish()
            if item:
                yield item
    item = finish()
    if item:
        yield item


class CandidateBuffer:
    """Retain only the best requested prefix for one document."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._heap: list[tuple[int, int, int, SearchHit]] = []
        self._keys: set[tuple] = set()

    def add(self, hit: SearchHit) -> None:
        if hit.duplicate_key in self._keys:
            return
        entry = (hit.score, -hit.line, -hit.end_line, hit)
        if len(self._heap) >= self.capacity:
            if entry[:3] <= self._heap[0][:3]:
                return
            removed = heapq.heapreplace(self._heap, entry)[3]
            self._keys.remove(removed.duplicate_key)
        else:
            heapq.heappush(self._heap, entry)
        self._keys.add(hit.duplicate_key)

    def ranked(self) -> list[SearchHit]:
        return sorted((entry[3] for entry in self._heap), key=lambda hit: hit.rank_key)


def diversify_results(documents: list[list[SearchHit]], count: int) -> list[SearchHit]:
    """Stable prefix: relevance divided by prior selections from the document.

    The first two results cover both record types when both have matches. Further
    results compete by relevance with a growing same-document penalty, rather
    than enforcing equal quotas for unrelated documents.
    """
    heap = []
    for index, hits in enumerate(documents):
        if hits:
            heapq.heappush(heap, (-hits[0].score, hits[0].rank_key, index, 0))
    selected = []
    first_type = None
    while heap and len(selected) < count:
        entry = heapq.heappop(heap)
        if len(selected) == 1:
            other = [item for item in heap + [entry]
                     if documents[item[2]][item[3]].record_type != first_type]
            if other:
                chosen = min(other)
                if chosen != entry:
                    heapq.heappush(heap, entry)
                    heap.remove(chosen)
                    heapq.heapify(heap)
                    entry = chosen
        _, _, index, position = entry
        hit = documents[index][position]
        selected.append(hit)
        if first_type is None:
            first_type = hit.record_type
        next_position = position + 1
        if next_position < len(documents[index]):
            next_hit = documents[index][next_position]
            heapq.heappush(heap, (
                -next_hit.score / (next_position + 1), next_hit.rank_key, index, next_position
            ))
    return selected
