"""Reproduce retrieval metrics using temporary, synthetic PDFs and memories."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time


def write_pdf(path: Path, pages: list[list[str]]) -> None:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for lines in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
        })
        commands = ["BT /F1 8 Tf 10 TL 40 750 Td"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.extend([f"({escaped}) Tj", "T*"])
        commands.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)


def summarize(rows: list[dict]) -> dict:
    answerable = [row for row in rows if row["recall_at_10"] is not None]
    absent = [row for row in rows if row["recall_at_10"] is None]
    return {
        "queries": len(rows),
        **{key: round(statistics.mean(row[key] for row in answerable), 6) if answerable else None
           for key in ("recall_at_10", "mrr_at_10", "precision_at_10")},
        "no_answer_empty_rate": (
            sum(row["returned"] == 0 for row in absent) / len(absent) if absent else None
        ),
        "scope_violations": sum(row["scope_violations"] for row in rows),
        "mean_search_ms": round(statistics.mean(row["search_ms"] for row in rows), 3),
        "mean_text_chars": round(statistics.mean(row["text_chars"] for row in rows), 1),
    }


def score_hits(hits: list[dict], gold: list[dict], names: dict[str, str]) -> dict:
    relevant = []
    covered = set()
    for position, hit in enumerate(hits[:10], 1):
        evidence = [index for index, item in enumerate(gold)
                    if names[hit["path"]] == item["document"]
                    and item["evidence_contains"].casefold() in hit["text"].casefold()]
        if evidence:
            relevant.append(position)
            covered.update(evidence)
    return {
        "recall_at_10": len(covered) / len(gold) if gold else None,
        "precision_at_10": len(relevant) / 10,
        "mrr_at_10": 1 / relevant[0] if relevant else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--code-root", type=Path, default=root)
    parser.add_argument("--dataset", type=Path, default=root / "evals/search/dataset.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path, help="Compare with a report using the same dataset")
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    sys.path.insert(0, str(args.code_root.resolve() / "src"))
    from research_store.config import load_config
    from research_store.conversations import save_conversation
    from research_store.safety import PROJECT_MARKER_CONTENT
    from research_store.search import search_library
    from research_store.sync import sync_library

    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    supports_scope = "scope" in inspect.signature(search_library).parameters
    with tempfile.TemporaryDirectory(prefix="research-search-eval-") as directory:
        temporary = Path(directory).resolve()
        source, project = temporary / "sources", temporary / "store"
        source.mkdir()
        project.mkdir()
        (project / ".research-agent-root").write_text(PROJECT_MARKER_CONTENT + "\n")
        for item in dataset["pdfs"]:
            write_pdf(source / item["filename"], item["pages"])
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        config_path = project / "config.toml"
        config_path.write_text(
            '[store]\ndocuments = "knowledge/documents"\n'
            'conversations = "knowledge/conversations"\nassets = "knowledge/assets"\n'
            'state = ".research-store/library.sqlite"\ntemporary = ".research-store/tmp"\n'
            '[[sources]]\nid = "papers"\npath = ' + json.dumps(str(source)) + '\nkind = "directory"\n'
        )
        config = load_config(config_path)
        sync_library(config)
        names = {}
        for path in config.documents.rglob("*.md"):
            text = path.read_text()
            item = next(item for item in dataset["pdfs"]
                        if 'source_path: ' + json.dumps(item["filename"]) in text)
            names[path.relative_to(project).as_posix()] = item["id"]
        for item in dataset["conversations"]:
            result = save_conversation(config, {
                "title": item["title"], "summary": item["summary"],
                "created_at": "2026-09-22T00:00:00+00:00",
                "scope": "current-topic", "capture_status": "complete",
                "transcript": [{"role": "user", "content": "이 주제를 정리해줘."}],
            })
            names[result.relative_to(project).as_posix()] = item["id"]
        rows = []
        for query in dataset["queries"]:
            times = []
            for _ in range(args.repeat):
                started = time.perf_counter()
                options = {"limit": 10}
                if supports_scope:
                    options["scope"] = query["scope"]
                result = search_library(config, query["terms"], **options)
                times.append((time.perf_counter() - started) * 1000)
            hits = result["matches"]
            expected_type = {"pdf": "pdf-document", "conversation": "conversation"}.get(query["scope"])
            rows.append({
                "id": query["id"], "category": query["category"],
                **score_hits(hits, query["gold"], names),
                "returned": len(hits),
                "documents": [names[hit["path"]] for hit in hits],
                "scope_violations": sum(hit["type"] != expected_type for hit in hits) if expected_type else 0,
                "search_ms": round(statistics.median(times), 3),
                "text_chars": sum(len(hit["text"]) for hit in hits),
            })
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        assert before == after, "Original PDF bytes changed"
    report = {
        "dataset_version": dataset["version"],
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "synthetic": True, "fixed_query_terms": True, "model_calls": 0,
        "supports_scope": supports_scope, "repeats": args.repeat,
        "code_sha256": {
            name: hashlib.sha256((args.code_root / "src/research_store" / name).read_bytes()).hexdigest()
            for name in ("search.py", "search_results.py")
            if (args.code_root / "src/research_store" / name).exists()
        },
        "originals_unchanged": True,
        "overall": summarize(rows),
        "by_category": {category: summarize([row for row in rows if row["category"] == category])
                        for category in sorted({row["category"] for row in rows})},
        "queries": rows,
    }
    if args.compare:
        baseline = json.loads(args.compare.read_text())
        if baseline["dataset_sha256"] != report["dataset_sha256"]:
            parser.error("Comparison requires the exact same dataset version and contents")
        prior = {row["id"]: row for row in baseline["queries"]}
        if set(prior) != {row["id"] for row in rows}:
            parser.error("Comparison query IDs differ")
        regressions = []
        for row in rows:
            before = prior[row["id"]]
            for key in ("recall_at_10", "mrr_at_10", "precision_at_10"):
                if row[key] is not None and before[key] is not None and row[key] < before[key]:
                    regressions.append({"id": row["id"], "metric": key,
                                        "before": before[key], "after": row[key]})
        report["comparison"] = {
            "baseline_code_sha256": baseline.get("code_sha256"),
            "quality_regressions": regressions,
            "overall_delta": {
                key: round(report["overall"][key] - baseline["overall"][key], 6)
                for key in ("recall_at_10", "mrr_at_10", "precision_at_10",
                            "scope_violations", "mean_search_ms", "mean_text_chars")
                if report["overall"][key] is not None and baseline["overall"][key] is not None
            },
        }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
