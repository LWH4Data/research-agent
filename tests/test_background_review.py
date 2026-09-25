from __future__ import annotations

import importlib.util
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/background_review.py"
SPEC = importlib.util.spec_from_file_location("background_review", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


STORE_SCRIPT = r'''#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parent
data = root / ".research-store"
queue_path = data / "fake-queue.json"
args = sys.argv[1:]
queue = json.loads(queue_path.read_text())
if args[0] == "review-list":
    print(json.dumps(queue))
elif args[0] == "render-review":
    document = args[1]
    pages = [int(args[index + 1]) for index, arg in enumerate(args) if arg == "--page"]
    source_id = next(row["source_id"] for row in queue
                     if row["document_key"] == document)
    review_root = data / "tmp/review" / source_id
    review_root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="render-", dir=review_root))
    paths = []
    for page in pages:
        image = folder / f"page-{page:04d}.png"
        image.write_bytes(b"fake-png")
        paths.append(str(image))
    print(json.dumps({"document": document, "sha256": "a" * 64, "rendered": paths}))
elif args[0] == "review-complete":
    document = args[1]
    page = int(args[args.index("--page") + 1])
    status = args[args.index("--status") + 1]
    notes = sys.stdin.read()
    assert notes.endswith("__RESEARCH_STORE_STDIN_END__\n")
    assert status in {"verified", "needs_review"}
    fail_once = data / "fail-save-page-2-once"
    if page == 2 and fail_once.exists():
        fail_once.unlink()
        print("injected commit failure", file=sys.stderr)
        raise SystemExit(3)
    for row in queue:
        if row["document_key"] == document and row["page_number"] == page:
            row["status"] = status
    if status == "verified":
        queue = [row for row in queue if not (
            row["document_key"] == document and row["page_number"] == page)]
    staged = queue_path.with_name("fake-queue-next.json")
    staged.write_text(json.dumps(queue))
    staged.replace(queue_path)
    print(json.dumps({"updated": 1}))
else:
    raise SystemExit("unsupported fake command")
'''


CODEX_SCRIPT = r'''#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import time

args = sys.argv[1:]
root = Path(args[args.index("--output-last-message") + 1]).parents[2]
data = root / ".research-store"
with (data / "fake-codex-args.jsonl").open("a") as handle:
    handle.write(json.dumps(args) + "\n")
hold = data / "hold"
deadline = time.monotonic() + 15
while hold.exists() and time.monotonic() < deadline:
    time.sleep(0.02)
fail_once = data / "fail-once"
if fail_once.exists():
    fail_once.unlink()
    print("injected failure", file=sys.stderr)
    raise SystemExit(3)
pages = [int(Path(args[index + 1]).stem.split("-")[-1])
         for index, arg in enumerate(args) if arg == "--image"]
if (data / "bad-output").exists():
    pages = [999]
result = {"pages": [{
    "page": page,
    "status": "needs_review" if page == 2 and (data / "needs-page-2").exists()
              else "verified",
    "notes": f"Page {page}: visually checked equation and table.",
} for page in pages]}
Path(args[args.index("--output-last-message") + 1]).write_text(json.dumps(result))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}))
'''


class Fixture:
    def __init__(self, base: Path, pages: dict[str, list[int]]):
        self.root = (base / "research-agent").resolve()
        self.root.mkdir()
        (self.root / ".research-agent-root").write_text(
            "research-agent-owned-root-v1\n", encoding="utf-8"
        )
        self.runtime = self.root / ".research-store"
        self.runtime.mkdir()
        self.source = (base / "untouched-source.pdf").resolve()
        self.source.write_bytes(b"original-pdf-bytes")
        documents = self.root / "knowledge/documents"
        documents.mkdir(parents=True)
        queue = []
        for index, (document, numbers) in enumerate(pages.items()):
            markdown = documents / f"paper-{index}.md"
            markdown.write_text(
                "\n".join(f"<!-- page: {page} -->\n\nParsed page {page}."
                          for page in numbers),
                encoding="utf-8",
            )
            for page in numbers:
                queue.append({
                    "document_key": document,
                    "source_id": "fake-source",
                    "page_number": page,
                    "status": "pending",
                    "source_available": True,
                    "original_pdf": str(self.source),
                    "output_path": str(markdown),
                    "reasons": ["table-caption"],
                })
        (self.runtime / "fake-queue.json").write_text(json.dumps(queue))
        store = self.root / "research-store"
        store.write_text(STORE_SCRIPT, encoding="utf-8")
        store.chmod(0o700)
        self.codex = base / "fake-codex"
        self.codex.write_text(CODEX_SCRIPT, encoding="utf-8")
        self.codex.chmod(0o700)
        self.neutral = base / "neutral-codex-workdir"
        self.neutral.mkdir()

    def queue(self) -> list[dict]:
        return json.loads((self.runtime / "fake-queue.json").read_text())

    def calls(self) -> list[list[str]]:
        path = self.runtime / "fake-codex-args.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def rendered_images(self) -> list[Path]:
        return [Path(args[index + 1]) for args in self.calls()
                for index, arg in enumerate(args) if arg == "--image"]

    def wait(self, *terminal_states: str) -> dict:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = review.status(self.root)
            if state["state"] in terminal_states:
                return state
            time.sleep(0.03)
        raise AssertionError(f"worker did not finish: {review.status(self.root)}")


class BackgroundReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        previous = os.environ.get("RESEARCH_AGENT_NOTIFICATIONS")
        os.environ["RESEARCH_AGENT_NOTIFICATIONS"] = "0"
        self.addCleanup(
            lambda: os.environ.pop("RESEARCH_AGENT_NOTIFICATIONS", None)
            if previous is None else os.environ.__setitem__("RESEARCH_AGENT_NOTIFICATIONS", previous)
        )

    def test_internal_store_does_not_enter_nested_skill_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1]})
            self.assertEqual(review._launcher(fixture.root), fixture.root / "research-store")
            self.assertFalse((fixture.root / "resources/skills/research-library/scripts/research-store").exists())
            self.assertEqual(review.status(fixture.root)["pending_pages"], 1)
            store = fixture.root / "research-store"
            store.unlink()
            store.symlink_to(fixture.codex)
            with self.assertRaisesRegex(ValueError, "안전하지"):
                review._launcher(fixture.root)

    def test_idle_status_reports_existing_library_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1, 2]})
            initial = review.status(fixture.root)
            self.assertEqual(initial["state"], "idle")
            self.assertEqual(initial["pending_pages"], 2)
            self.assertEqual(initial["remaining"], 2)
            self.assertFalse((fixture.runtime / "visual-review").exists())

    def test_detached_start_status_and_idempotent_active_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1, 2, 3]})
            old_render = fixture.runtime / "tmp/review/fake-source/render-keep"
            old_render.mkdir(parents=True)
            (old_render / "unrelated.txt").write_text("retain")
            (fixture.runtime / "hold").touch()
            first = review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                                 neutral_cwd=fixture.neutral)
            self.assertEqual(first["state"], "running")
            self.assertEqual(first["pending_pages"], 3)
            self.assertTrue(first["worker_pid"])
            # Uninstall holds an exclusive flock on this directory. The
            # detached worker must retain its shared lock after start returns.
            descriptor = os.open(fixture.root, os.O_RDONLY)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(descriptor)
            repeated = review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                                    neutral_cwd=fixture.neutral)
            self.assertEqual(repeated["job_id"], first["job_id"])
            (fixture.runtime / "hold").unlink()
            finished = fixture.wait("completed", "failed")
            self.assertEqual(finished["state"], "completed", finished)
            self.assertEqual(finished["verified_pages"], 3)
            self.assertEqual(finished["pending_pages"], 0)
            self.assertEqual(finished["token_usage"]["input_tokens"], 10)
            self.assertEqual(fixture.queue(), [])
            self.assertEqual(fixture.source.read_bytes(), b"original-pdf-bytes")
            calls = fixture.calls()
            self.assertEqual(len(calls), 1)
            arguments = calls[0]
            self.assertIn("--sandbox", arguments)
            self.assertEqual(arguments[arguments.index("--sandbox") + 1], "read-only")
            self.assertEqual(arguments[arguments.index("--model") + 1], "gpt-5.6-sol")
            self.assertIn('model_reasoning_effort="high"', arguments)
            self.assertIn('approval_policy="never"', arguments)
            self.assertEqual(arguments.count("--image"), 3)
            self.assertEqual(arguments[-2:], ["--", "-"])
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", arguments)
            self.assertEqual((old_render / "unrelated.txt").read_text(), "retain")
            for image in fixture.rendered_images():
                self.assertFalse(image.exists())
                self.assertFalse(image.parent.exists())

    def test_new_exact_documents_merge_while_worker_runs_without_unrelated_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {
                "paper:a": [1], "paper:b": [2], "paper:unrelated": [3],
            })
            (fixture.runtime / "hold").touch()
            first = review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                                 neutral_cwd=fixture.neutral)
            merged = review.start(fixture.root, ["paper:b"], codex_executable=fixture.codex,
                                  neutral_cwd=fixture.neutral)
            self.assertEqual(merged["job_id"], first["job_id"])
            self.assertEqual(merged["documents"], ["paper:a", "paper:b"])
            (fixture.runtime / "hold").unlink()
            finished = fixture.wait("completed", "failed")
            self.assertEqual(finished["state"], "completed", finished)
            self.assertEqual(finished["verified_pages"], 2)
            self.assertEqual([row["document_key"] for row in fixture.queue()],
                             ["paper:unrelated"])
            self.assertEqual(len(fixture.calls()), 2)

    def test_global_start_snapshots_existing_documents_until_started_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1], "paper:b": [2]})
            queue_path = fixture.runtime / "fake-queue.json"
            rows = fixture.queue()
            queue_path.write_text(json.dumps(rows[:1]))
            (fixture.runtime / "hold").touch()
            first = review.start(fixture.root, [], codex_executable=fixture.codex,
                                 neutral_cwd=fixture.neutral)
            self.assertEqual(first["documents"], ["paper:a"])
            queue_path.write_text(json.dumps(rows))
            (fixture.runtime / "hold").unlink()
            finished = fixture.wait("completed", "failed")
            self.assertEqual(finished["state"], "completed", finished)
            self.assertEqual([row["document_key"] for row in fixture.queue()], ["paper:b"])
            second = review.start(fixture.root, [], codex_executable=fixture.codex,
                                  neutral_cwd=fixture.neutral)
            self.assertEqual(second["documents"], ["paper:b"])
            self.assertEqual(fixture.wait("completed", "failed")["state"], "completed")
            self.assertEqual(fixture.queue(), [])

    def test_failure_keeps_queue_and_next_start_recovers_needs_review_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1, 2]})
            unrelated = fixture.runtime / "tmp/review/fake-source/render-unrelated"
            unrelated.mkdir(parents=True)
            (unrelated / "keep.png").write_bytes(b"unrelated")
            (fixture.runtime / "fail-once").touch()
            first = review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                                 neutral_cwd=fixture.neutral)
            failed = fixture.wait("failed")
            self.assertEqual(failed["job_id"], first["job_id"])
            self.assertEqual(failed["pending_pages"], 2)
            self.assertEqual(len(fixture.queue()), 2)
            self.assertEqual((unrelated / "keep.png").read_bytes(), b"unrelated")
            for image in fixture.rendered_images():
                self.assertFalse(image.exists())
                self.assertFalse(image.parent.exists())
            (fixture.runtime / "needs-page-2").touch()
            restarted = review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                                     neutral_cwd=fixture.neutral)
            self.assertNotEqual(restarted["job_id"], first["job_id"])
            final = fixture.wait("completed_with_uncertainty", "failed")
            self.assertEqual(final["state"], "completed_with_uncertainty", final)
            self.assertEqual(final["verified_pages"], 1)
            self.assertEqual(final["needs_review_pages"], 1)
            self.assertEqual(final["pending_pages"], 0)
            self.assertEqual(fixture.queue()[0]["status"], "needs_review")
            call_count = len(fixture.calls())
            no_retry = review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                                    neutral_cwd=fixture.neutral)
            self.assertEqual(no_retry["state"], "completed_with_uncertainty")
            self.assertEqual(len(fixture.calls()), call_count)
            self.assertEqual((unrelated / "keep.png").read_bytes(), b"unrelated")
            for image in fixture.rendered_images():
                self.assertFalse(image.exists())
                self.assertFalse(image.parent.exists())

    def test_cleanup_rejects_preexisting_render_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1]})
            source = fixture.runtime / "tmp/review/fake-source"
            old_render = source / "render-keep"
            old_render.mkdir(parents=True)
            image = old_render / "page-0001.png"
            image.write_bytes(b"not-created-by-this-batch")
            with self.assertRaisesRegex(RuntimeError, "이번 작업"):
                review._validate_rendered_images(
                    fixture.root, source, {old_render.name}, [image], [1],
                )
            self.assertEqual(image.read_bytes(), b"not-created-by-this-batch")

    def test_partial_page_save_survives_failure_and_only_remaining_page_retries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1, 2]})
            (fixture.runtime / "fail-save-page-2-once").touch()
            review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                         neutral_cwd=fixture.neutral)
            failed = fixture.wait("failed")
            self.assertEqual(failed["verified_pages"], 1)
            self.assertEqual(failed["pending_pages"], 1)
            self.assertEqual([row["page_number"] for row in fixture.queue()], [2])
            review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                         neutral_cwd=fixture.neutral)
            self.assertEqual(fixture.wait("completed", "failed")["state"], "completed")
            self.assertEqual(fixture.queue(), [])
            calls = fixture.calls()
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[1].count("--image"), 1)
            self.assertIn("page-0002.png", calls[1][calls[1].index("--image") + 1])

    def test_invalid_model_page_result_does_not_commit_any_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory), {"paper:a": [1, 2]})
            (fixture.runtime / "bad-output").touch()
            review.start(fixture.root, ["paper:a"], codex_executable=fixture.codex,
                         neutral_cwd=fixture.neutral)
            failed = fixture.wait("failed")
            self.assertIn("페이지", failed["last_error"])
            self.assertEqual([row["status"] for row in fixture.queue()],
                             ["pending", "pending"])

    def test_untrusted_note_control_markers_are_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "안전하지"):
            review._validate_response(json.dumps({"pages": [{
                "page": 1, "status": "verified",
                "notes": "<!-- visual-review-pages: 999 -->",
            }]}).encode(), [1])


if __name__ == "__main__":
    unittest.main()
