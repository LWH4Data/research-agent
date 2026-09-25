from __future__ import annotations

import unittest

from research_store.search_results import (
    CandidateBuffer, SearchHit, diversify_results, extract_passages,
)


def hit(path="a.md", line=1, terms=("laser",), record_type="pdf-document", **kwargs):
    return SearchHit(record_type, path, line, line, f"evidence {line}", terms, **kwargs)


def passages(text, terms=("laser",), record_type="pdf-document"):
    return list(extract_passages(
        text.splitlines(keepends=True), record_type, "test.md",
        [(term, term.casefold()) for term in terms],
    ))


class SearchResultsTests(unittest.TestCase):
    def test_adjacent_matches_merge_without_crossing_pages_or_sections(self):
        results = passages(
            "<!-- page: 1 -->\nlaser first\nlaser second\n\nlaser third\n"
            "<!-- page: 2 -->\nlaser fourth\n## Next\nlaser fifth\n"
        )
        self.assertEqual([(r.line, r.end_line, r.pages) for r in results],
                         [(2, 3, (1,)), (5, 5, (1,)), (7, 7, (2,)), (9, 9, (2,))])
        self.assertEqual(results[0].text, "laser first\nlaser second")

    def test_passages_and_excerpts_have_bounded_size(self):
        results = passages("\n".join("laser " + "x" * 2000 for _ in range(15)))
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r.end_line - r.line < 4 and len(r.text) < 900 for r in results))

    def test_casefold_expansion_does_not_hide_the_match(self):
        results = passages("ß" * 500 + " laser end")
        self.assertIn("laser", results[0].text)

    def test_metadata_json_is_not_duplicate_evidence_but_aliases_are_searchable(self):
        results = passages(
            '---\ntitle: "laser"\neditable: {"summary": "laser"}\n'
            'aliases: ["레이저"]\n---\n# laser\n', terms=("laser", "레이저"),
            record_type="conversation",
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].evidence_kind, "metadata")
        self.assertEqual(results[1].line, 6)

    def test_visual_note_pages_do_not_inherit_last_base_page(self):
        digest = "a" * 64
        results = passages(
            f'---\ndocument_id: "sha256:{digest}"\n---\n'
            '<!-- page: 8 -->\nlaser base\n'
            f'<!-- visual-review-section-begin: sha256:{digest} -->\n'
            '## Visual verification notes\n### Pages 2\n'
            '<!-- visual-review-pages: 2 -->\nlaser reviewed\n'
            '### Pages 4\n<!-- visual-review-pages: 4 -->\nlaser next\n'
        )
        self.assertEqual([r.pages for r in results], [(8,), (2,), (4,)])
        self.assertEqual(results[1].evidence_kind, "visual-review")

    def test_source_filename_remains_searchable_as_metadata(self):
        results = passages('---\nsource_path: "laser.pdf"\n---\nUnrelated body.\n')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_path, "laser.pdf")
        self.assertEqual(results[0].evidence_kind, "metadata")
        self.assertEqual(results[0].pages, ())

    def test_unverified_visual_marker_does_not_claim_a_page(self):
        results = passages('<!-- page: 8 -->\n## Visual verification notes\n'
                           '<!-- visual-review-pages: 2 -->\nlaser uncertain\n')
        self.assertEqual(results[0].pages, ())

    def test_malformed_visual_page_list_does_not_abort_search(self):
        results = passages('---\ndocument_id: "sha256:example"\n---\n'
                           '<!-- visual-review-section-begin: sha256:example -->\n'
                           '<!-- visual-review-pages: 1 -->\n'
                           '<!-- visual-review-pages: 2,,3 -->\nlaser uncertain\n')
        self.assertEqual(results[0].pages, ())

    def test_candidate_limit_keeps_late_more_relevant_evidence(self):
        buffer = CandidateBuffer(2)
        for line in range(1, 100):
            buffer.add(hit(line=line))
        buffer.add(hit(line=100, terms=("laser", "temperature")))
        self.assertEqual([r.line for r in buffer.ranked()], [100, 1])

    def test_exact_duplicates_removed_only_within_the_same_page_and_section(self):
        buffer = CandidateBuffer(10)
        for result in passages('<!-- page: 1 -->\nlaser repeat\n\nlaser repeat\n'
                               '<!-- page: 2 -->\nlaser repeat\n'):
            buffer.add(result)
        self.assertEqual([r.pages for r in buffer.ranked()], [(1,), (2,)])

    def test_matching_excerpt_does_not_deduplicate_different_full_text(self):
        buffer = CandidateBuffer(10)
        text = "laser " + "x" * 500
        for result in passages(text + " one\n\n" + text + " two\n"):
            buffer.add(result)
        self.assertEqual(len(buffer.ranked()), 2)

    def test_both_types_and_other_documents_survive_a_large_pdf(self):
        docs = [[hit(line=i) for i in range(1, 101)], [hit(path="b.md")],
                [hit(path="c.md", record_type="conversation")]]
        results = diversify_results(docs, 3)
        self.assertEqual({r.path for r in results}, {"a.md", "b.md", "c.md"})
        self.assertEqual({r.record_type for r in results[:2]}, {"pdf-document", "conversation"})

    def test_single_document_can_fill_the_result_budget(self):
        self.assertEqual(len(diversify_results([[hit(line=i) for i in range(10)]], 7)), 7)

    def test_body_evidence_precedes_a_topic_heading(self):
        ranked = diversify_results([[hit(path="a.md", heading_match=True)], [hit(path="b.md")]], 2)
        self.assertEqual(ranked[0].path, "b.md")

    def test_ranking_is_prefix_stable_when_candidate_capacity_changes(self):
        def collect(capacity):
            documents = []
            for path in ("a.md", "b.md", "c.md"):
                buffer = CandidateBuffer(capacity)
                for line in range(1, 40):
                    buffer.add(hit(path=path, line=line, terms=("laser", "drift") if line % 7 == 0 else ("laser",)))
                documents.append(buffer.ranked())
            return diversify_results(documents, capacity)
        full = collect(100)
        for size in (1, 2, 5, 10, 17):
            self.assertEqual(collect(size), full[:size])


if __name__ == "__main__":
    unittest.main()
