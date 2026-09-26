# Retrieval evaluation: search-v1

[한국어](../../ko/experiments/search-evaluation.md) | [English](./search-evaluation.md)

Measured: 2026-09-22

This is the first reusable development benchmark for the retrieval tool. It uses
no vector model, LangChain, external API, or Codex model calls.

## Dataset and evaluation unit

- [dataset.json](../../../../evals/search/dataset.json) defines three synthetic PDFs
  covering optics, AI, and software, six synthetic memories, and twenty queries.
  It is not an accuracy study on published research papers.
- The runner generates real PDFs in temporary storage, invokes the base parser,
  and verifies unchanged original PDF hashes. Personal sources and installed
  agent settings are not modified.
- Categories cover exact terminology, Korean/English search, prior discussion,
  multiple sources, paraphrases, and unanswerable questions. Natural-language
  questions have fixed search terms and scopes.
- Ground truth combines a document ID with required evidence text. Returning
  the right document without that passage is not a hit; this measures whether
  the tool actually exposes the evidence in its excerpt.
- The set was used during development and tuning. It is not a held-out set and
  does not establish real-research performance, Codex query-generation quality,
  or final-answer quality.

## Persistent metrics

| Metric | Definition |
| --- | --- |
| Recall@10 | Distinct labeled evidence units found in the first ten results divided by all labeled units; duplicates count once |
| MRR@10 | Reciprocal of the first relevant rank within ten results, or zero |
| Precision@10 | Relevant results within the first ten divided by ten, even when fewer than ten results are returned |
| Unanswerable empty rate | Fraction of unanswerable queries returning no results |
| Scope violations | Results of the wrong type in PDF-only or conversation-only searches |
| Search latency | Mean of per-query median timings; PDF ingestion is excluded |
| Returned characters | Sum of returned `text` lengths; excludes JSON metadata, further reading, and model tokens |

Quality metrics average eighteen answerable queries. Two unanswerable queries
are reported separately. Most questions have only one or two labeled units, so
absolute Precision@10 is low by construction. It is not a pass rate or answer
accuracy. Duplicate relevant excerpts can count toward precision; review recall
and the deduplication/diversity regression tests alongside it.

Version changes to data or labels and remeasure the baseline. The runner rejects
comparisons with different dataset hashes. Review per-query and per-category
results so an overall average cannot conceal a regression in one query type.

## Results

Both versions used identical data, terms, and a ten-result limit, with five runs
per query. The old implementation did not support scope selection and searched
both types; resulting cross-type hits are counted as scope violations.

| Metric | Original | Improved |
| --- | ---: | ---: |
| Recall@10 | 0.944444 | 0.972222 |
| MRR@10 | 0.680556 | 1.000000 |
| Precision@10 | 0.150000 | 0.155556 |
| Unanswerable empty rate | 1.000000 | 1.000000 |
| Scope violations | 12 | 0 |
| Mean search latency | 2.599 ms | 4.706 ms |
| Mean returned characters | 124.4 | 148.3 |

No individual query regressed in recall, MRR, or precision. Query `q01` still
misses a particular thermal-drift PDF passage within ten results when searching
only `laser`. The conversation is now retrieved, but semantic recall is not
solved. Full-content hashing and candidate selection increase latency and the
returned text budget. These timings are small-fixture measurements on one Mac,
not a performance guarantee or load test. Large-library memory, latency, and
write-lock waiting remain to be measured.

Raw reports include per-query results, returned document IDs, and dataset and
search-code hashes:

- [Original report](../../../../evals/search/results/baseline-v1.json)
- [Improved report and comparison](../../../../evals/search/results/passages-v1.json)

## Reproduce

Run from the repository root. Synthetic sources are generated in temporary
storage and removed on exit.

```sh
.venv/bin/python -B scripts/evaluate-search.py \
  --repeat 5 \
  --compare evals/search/results/baseline-v1.json \
  --output /tmp/research-search-evaluation.json
```

Add `--code-root /path/to/checkout` to evaluate another checkout. Omit `--output`
to print JSON. The default evaluation makes no model calls.

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_search*.py'
```

Next, use a separate real-research validation set and evaluate Codex term/scope
selection independently. If different wording repeatedly causes misses, compare
hybrid keyword/vector retrieval with the same metrics.
