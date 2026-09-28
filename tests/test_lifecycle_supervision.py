"""Real local processes, temporary stores, and fake model responses only."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from research_store.config import load_config
from research_store.review_lifecycle import Lifecycle, read_record
from research_store.sources import add_sources, initialize_config
from research_store.sync import ConversionResult, sync_library
from test_sync import make_project, write_text_pdf

PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("background_lifecycle", PROJECT / "scripts/background_lifecycle.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        if runner.process_identity(os.getpid()) is None:
            self.skipTest("OS process ownership inspection is unavailable in this sandbox")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        from unittest.mock import patch
        temporary_home = self.base / "home"
        temporary_home.mkdir()
        environment = patch.dict(os.environ, {"HOME": str(temporary_home), "RESEARCH_AGENT_NOTIFICATIONS": "0"})
        environment.start()
        self.addCleanup(environment.stop)
        self.root = make_project(self.base / "store")
        self.config_path = initialize_config(self.root / ".research-store/config.toml")
        self.source = self.base / "source"
        self.source.mkdir()
        write_text_pdf(self.source / "one.pdf", "table and equation evidence")
        add_sources(self.config_path, [self.source])
        self.config = load_config(self.config_path)
        self.document = sync_library(self.config, lambda path: ConversionResult(
            "<!-- page: 1 -->\n\nTable evidence", {1: ["table"]})).committed_documents[0]
        executable = self.root / "research-store"
        executable.write_text(f"#!{sys.executable}\nimport sys\nsys.argv[1:1]=['--config',{str(self.config_path)!r}]\nfrom research_store.cli import main\nmain()\n")
        executable.chmod(0o700)
        self.codex = self.base / "fake-codex"
        self.codex.write_text(f'''#!{sys.executable}
import json,os,sys,time
from pathlib import Path
args=sys.argv[1:]
answer=Path(args[args.index("--output-last-message")+1])
root=answer.parent.parent.parent
(root/"model-started").write_text(str(os.getpid()))
with (root/"calls").open("a") as f: f.write("call\\n")
while (root/"hold").exists(): time.sleep(.02)
pages=[int(Path(args[i+1]).stem.split("-")[-1]) for i,a in enumerate(args) if a=="--image"]
answer.write_text(json.dumps({{"pages":[{{"page":p,"status":"verified","notes":"Confirmed table evidence"}} for p in pages]}}))
print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":12}}}}))
''')
        self.codex.chmod(0o700)
        self.neutral = self.base / "neutral"
        self.neutral.mkdir()
        self.engine = Lifecycle(self.root)
        self.addCleanup(self.stop_all)

    def stop_all(self):
        (self.root / "hold").unlink(missing_ok=True)
        if (self.root / ".research-store/visual-review/lifecycle.json").exists():
            self.engine.control("pause", library=True)
            self.until(lambda: read_record(self.root)["execution"] is None, timeout=7, fail=False)

    def until(self, predicate, timeout=15, fail=True):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if predicate():
                return True
            time.sleep(.03)
        if fail:
            self.fail(f"Timed out; state={self.engine.status()}")
        return False

    def request(self, key="a", pages=None, rereview=False):
        item = {"item_id": "input", "document_key": self.document["document_key"], "rereview": rereview}
        if pages:
            item["pages"] = pages
        expires = int(time.time()) + 500
        receipt = self.engine.begin(f"vr2.{expires}.{key * 16}", expires, {"items": [item]})
        self.engine.attach(receipt["request_id"], "input", self.document)
        return receipt["request_id"]

    def test_fake_model_commits_fenced_result_and_cleans_owned_images(self):
        rid = self.request()
        result = runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        self.assertIn(result["worker"], {"acknowledged", "starting_unconfirmed", "idle"})
        self.until(lambda: read_record(self.root)["execution"] is None and (self.root / "calls").exists())
        status = self.engine.status(rid)
        self.assertEqual(status["state"], "evidence_ready")
        self.assertEqual(list((self.root / ".research-store/tmp/review").rglob("*.png")), [])
        self.assertTrue((self.source / "one.pdf").exists())

    def test_controller_crash_keeps_independent_supervisor_and_no_overlap(self):
        rid = self.request()
        (self.root / "hold").write_text("hold")
        runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        self.until(lambda: (self.root / "model-started").exists())
        controller = runner.legacy._LOCAL_CHILDREN[-1]
        controller.kill()
        controller.wait(timeout=5)
        self.request("b")
        runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        time.sleep(.2)
        self.assertEqual((self.root / "calls").read_text().count("call"), 1)
        (self.root / "hold").unlink()
        self.until(lambda: read_record(self.root)["execution"] is None)
        self.assertEqual(self.engine.status(rid)["state"], "evidence_ready")

    def test_explicit_stop_waits_for_owned_process_and_preserves_original(self):
        rid = self.request()
        original = (self.source / "one.pdf").read_bytes()
        (self.root / "hold").write_text("hold")
        runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        self.until(lambda: (self.root / "model-started").exists())
        result = self.engine.control("pause", request_id=rid)
        self.assertEqual(result["state"], "stopping")
        self.until(lambda: read_record(self.root)["execution"] is None)
        self.assertEqual(self.engine.status(rid)["state"], "paused")
        self.assertEqual((self.source / "one.pdf").read_bytes(), original)

    def test_pid_birth_mismatch_does_not_signal_other_process(self):
        child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(20)"], start_new_session=True)
        try:
            identity = runner.process_identity(child.pid)
            identity["birth"] = "wrong-start-time"
            self.assertFalse(runner.stop_owned(child, identity))
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=5)

    def test_revoked_first_page_does_not_discard_B_second_page(self):
        from pypdf import PdfReader, PdfWriter
        path = self.source / "one.pdf"
        reader = PdfReader(path)
        writer = PdfWriter()
        writer.add_page(reader.pages[0])
        writer.add_page(reader.pages[0])
        with path.open("wb") as handle:
            writer.write(handle)
        self.document = sync_library(self.config, lambda path: ConversionResult(
            "<!-- page: 1 -->\n\nOne\n<!-- page: 2 -->\n\nTwo", {1: ["table"], 2: ["table"]})).committed_documents[0]
        a = self.request("a", [1])
        b = self.request("b", [2])
        (self.root / "hold").write_text("hold")
        runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        self.until(lambda: (self.root / "model-started").exists())
        self.engine.control("cancel", request_id=a)
        (self.root / "hold").unlink()
        self.until(lambda: read_record(self.root)["execution"] is None)
        self.assertEqual(self.engine.status(a)["state"], "cancelled")
        self.assertEqual(self.engine.status(b)["state"], "evidence_ready")

    def test_user_cancel_terminates_verified_orphan_after_supervisor_death(self):
        rid = self.request()
        (self.root / "hold").write_text("hold")
        runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        self.until(lambda: (self.root / "model-started").exists())
        execution = read_record(self.root)["execution"]
        os.kill(execution["owner"]["pid"], signal.SIGKILL)
        self.until(lambda: runner.process_identity(execution["owner"]["pid"]) is None)
        self.engine.control("cancel", request_id=rid)
        runner._recover_execution(self.engine)
        self.until(lambda: runner.process_identity(execution["model_owner"]["pid"]) is None)
        (self.root / "hold").unlink()
        self.until(lambda: runner._recover_execution(self.engine))
        self.assertEqual(self.engine.status(rid)["state"], "cancelled")

    def test_explicit_rereview_of_verified_page_is_new_fenced_execution(self):
        a = self.request()
        runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        self.until(lambda: read_record(self.root)["execution"] is None and (self.root / "calls").exists())
        self.assertEqual(self.engine.status(a)["state"], "evidence_ready")
        from research_store.sync import review_snapshot
        self.document = review_snapshot(self.config)[0]
        b = self.request("b", [1], rereview=True)
        runner.launch(self.root, codex=self.codex, workdir=self.neutral)
        self.until(lambda: read_record(self.root)["execution"] is None and (self.root / "calls").read_text().count("call") == 2)
        self.assertEqual(self.engine.status(b)["state"], "evidence_ready")

    def test_source_retry_keeps_frozen_inventory_and_exact_receipts(self):
        from unittest.mock import patch
        source_id = self.document["document_key"].split(":", 1)[0]
        item = {"item_id": "source-input", "source_id": source_id}
        expires = int(time.time()) + 500
        request = self.engine.begin(f"vr2.{expires}.source-intake-key", expires, {"items": [item]})
        with patch.object(runner.legacy, "_store", side_effect=RuntimeError("crash before text sync")):
            with self.assertRaises(RuntimeError):
                runner._source_intake(self.engine, request["request_id"], item)
        write_text_pdf(self.source / "late.pdf", "Table 2 late arrival")
        result = runner._source_intake(self.engine, request["request_id"], item)
        linked = [i["document_key"] for i in result["items"].values() if i["state"] == "linked"]
        self.assertEqual(linked, [self.document["document_key"]])
        self.assertEqual(len(result["links"]), 1)


if __name__ == "__main__":
    unittest.main()
