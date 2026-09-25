from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("search_evaluation", ROOT / "scripts/evaluate-search.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class SearchEvaluationTests(unittest.TestCase):
    def test_recall_does_not_count_duplicate_evidence_twice(self):
        gold = [{"document": "a", "evidence_contains": "right"},
                {"document": "b", "evidence_contains": "other"}]
        hits = [{"path": "a.md", "text": "wrong"},
                {"path": "a.md", "text": "right"},
                {"path": "a.md", "text": "right"}]
        result = evaluation.score_hits(hits, gold, {"a.md": "a"})
        self.assertEqual(result, {"recall_at_10": 0.5, "precision_at_10": 0.2, "mrr_at_10": 0.5})

    def test_correct_document_without_the_required_evidence_is_not_a_hit(self):
        result = evaluation.score_hits([{"path": "a.md", "text": "topic heading"}],
                                       [{"document": "a", "evidence_contains": "actual finding"}],
                                       {"a.md": "a"})
        self.assertEqual(result["recall_at_10"], 0)
        self.assertEqual(result["mrr_at_10"], 0)
        self.assertIsNone(evaluation.score_hits([], [], {})["recall_at_10"])

    def test_versioned_dataset_has_valid_ground_truth(self):
        data = json.loads((ROOT / "evals/search/dataset.json").read_text())
        documents = {item["id"]: "\n".join(line for page in item["pages"] for line in page)
                     for item in data["pdfs"]}
        documents.update({item["id"]: item["title"] + "\n" + item["summary"]
                          for item in data["conversations"]})
        self.assertEqual(len(data["queries"]), len({query["id"] for query in data["queries"]}))
        for query in data["queries"]:
            self.assertIn(query["scope"], {"all", "pdf", "conversation"})
            self.assertTrue(query["terms"])
            for gold in query["gold"]:
                self.assertIn(gold["evidence_contains"].casefold(), documents[gold["document"]].casefold())


if __name__ == "__main__":
    unittest.main()
