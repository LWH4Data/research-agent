from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT = Path(__file__).resolve().parents[1]
HELPER = PROJECT / "scripts/review_intake_host.py"
SPEC = importlib.util.spec_from_file_location("review_host_intake_test", HELPER)
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)
SPEC = importlib.util.spec_from_file_location("review_host_attachment_test", PROJECT / "scripts/import_attachment.py")
transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transport)
REQUEST_ID = "a" * 32


class ReviewHostIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "store"
        self.root.mkdir()
        self.pdf = self.base / "paper.pdf"
        self.pdf.write_bytes(b"%PDF-1.7\nfixture\n%%EOF\n")
        self.args = ["--root", str(self.root), "--codex", str(self.base / "codex"),
                     "--sandbox-home", str(self.base / "profile"), "submit",
                     "--key", "vr2.1999999999.randomkey1234567", "--key-expires-at", "1999999999",
                     "--spec-stdin", "--warn-pages", "5", "--warn-seconds", "0.5", "--wait"]
        self.specification = {"items": [{"item_id": "attachment-1", "attachment": str(self.pdf)}]}

    def run_host(self, run, *, specification=None, args=None):
        payload = json.dumps(specification or self.specification).encode() + b"\n"
        stream = io.TextIOWrapper(io.BytesIO(payload + host.SENTINEL + b"\n"))
        with mock.patch.object(host.sys, "stdin", stream):
            with mock.patch.object(host.subprocess, "run", side_effect=run):
                return host.main(args or self.args)

    def prepared(self, states=None):
        receipt = {"request_id": REQUEST_ID, "items": states or {"attachment-1": {"state": "pending"}}}
        return subprocess.CompletedProcess([], 0, json.dumps(receipt).encode())

    def test_exact_intent_precedes_transport_then_same_specification_submitted(self):
        calls = []
        before = self.pdf.stat(), self.pdf.read_bytes()
        def run(command, **options):
            calls.append((command, options))
            if "prepare" in command:
                self.assertEqual(len(calls), 1)
                return self.prepared()
            return subprocess.CompletedProcess(command, 0)
        self.assertEqual(self.run_host(run), 0)
        self.assertEqual(len(calls), 3)
        prepare, transport_call, submit = calls
        self.assertEqual(prepare[0][1:7], ["sandbox", "-P", "research-review-worker", "-C", str(self.base / "profile"), "--"])
        self.assertNotIn("--wait", prepare[0])
        self.assertIn("--wait", submit[0])
        self.assertEqual(prepare[1]["input"], submit[1]["input"])
        self.assertEqual(prepare[0][prepare[0].index("prepare") + 1:], [arg for arg in self.args[self.args.index("submit") + 1:] if arg != "--wait"])
        self.assertEqual(submit[0][submit[0].index("submit") + 1:], self.args[self.args.index("submit") + 1:])
        self.assertIn(str(self.root / "scripts/import_attachment.py"), transport_call[0])
        self.assertIn("--request-id=" + REQUEST_ID, transport_call[0])
        self.assertIn("--item-id=attachment-1", transport_call[0])
        self.assertEqual(transport_call[1]["stdin"], subprocess.DEVNULL)
        self.assertNotIn("stdout", submit[1])
        self.assertTrue(all("shell" not in options for _, options in calls))
        self.assertTrue(all(options["env"]["CODEX_HOME"] == str(self.base / "profile") for _, options in calls))
        self.assertEqual(self.pdf.read_bytes(), before[1])
        self.assertEqual(self.pdf.stat().st_mtime_ns, before[0].st_mtime_ns)

    def test_prepare_failure_never_reads_or_transports_an_attachment(self):
        calls = []
        def run(command, **options):
            calls.append(command)
            return subprocess.CompletedProcess(command, 23)
        self.assertEqual(self.run_host(run), 23)
        self.assertEqual(len(calls), 1)
        self.assertIn("prepare", calls[0])

    def test_linked_attachments_and_document_items_need_no_host_transport(self):
        specification = {"items": [*self.specification["items"], {"item_id": "existing", "document_key": "papers:old.pdf"}]}
        calls = []
        def run(command, **options):
            calls.append(command)
            if "prepare" in command:
                return self.prepared({"attachment-1": {"state": "linked"}, "existing": {"state": "pending"}})
            return subprocess.CompletedProcess(command, 0)
        self.assertEqual(self.run_host(run, specification=specification), 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("submit", calls[-1])

    def test_deleted_item_retry_does_not_transport_it_while_other_item_remains(self):
        specification = {"items": [*self.specification["items"],
            {"item_id": "attachment-2", "attachment": str(self.base / "other.pdf")}]}
        calls = []
        def run(command, **options):
            calls.append(command)
            if "prepare" in command:
                return self.prepared({"attachment-1": {"state": "deleted"},
                                      "attachment-2": {"state": "linked"}})
            return subprocess.CompletedProcess(command, 0)
        self.assertEqual(self.run_host(run, specification=specification), 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("submit", calls[-1])

    def test_per_item_transport_failure_still_submits_for_receipt_recovery(self):
        specification = {"items": [*self.specification["items"], {"item_id": "attachment-2", "attachment": str(self.base / "gone.pdf")}]}
        calls = []
        def run(command, **options):
            calls.append(command)
            if "prepare" in command:
                return self.prepared({item["item_id"]: {"state": "pending"} for item in specification["items"]})
            if "--item-id=attachment-2" in command:
                return subprocess.CompletedProcess(command, 2)
            return subprocess.CompletedProcess(command, 0)
        self.assertEqual(self.run_host(run, specification=specification), 0)
        self.assertEqual(len(calls), 4)
        self.assertIn("submit", calls[-1])

    def test_start_alias_is_prepared_then_submitted_and_exit_status_preserved(self):
        args = ["start" if value == "submit" else value for value in self.args]
        calls = []
        def run(command, **options):
            calls.append(command)
            return self.prepared() if "prepare" in command else subprocess.CompletedProcess(command, -15 if "submit" in command else 0)
        self.assertEqual(self.run_host(run, args=args), 143)
        self.assertIn("submit", calls[-1])
        self.assertNotIn("start", calls[-1])

    def test_invalid_preparation_response_cannot_trigger_host_transport(self):
        for payload in (b"not json", b"[]", b'{"request_id":"--worker","items":{}}'):
            calls = []
            def run(command, **options):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, payload)
            with self.subTest(payload=payload), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.run_host(run), 2)
            self.assertEqual(len(calls), 1)

    def test_bounded_utf8_specification_and_sentinel(self):
        payload = json.dumps(self.specification).encode() + b"\n"
        stream = io.BytesIO(payload + host.SENTINEL + b"\nnext input")
        self.assertEqual(host.read_specification(stream), (payload, self.specification))
        self.assertEqual(stream.read(), b"next input")
        for invalid in (b"\xff", b"{}", b"[]", b'{"items":[null]}', b"x" * (host.MAX_SPEC_BYTES + 1)):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                host.read_specification(io.BytesIO(invalid))

    def test_private_controls_and_extra_commands_rejected_before_dispatch(self):
        for addition in (["--worker"], ["--codex", "/tmp/other"], ["--", "sh", "-c", "exit 0"], ["--exec", "anything"]):
            with self.subTest(addition=addition), mock.patch.object(host.subprocess, "run") as run:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    host.main(self.args + addition)
                run.assert_not_called()

    def test_attachment_transport_forwards_receipt_ids_without_shell_interpretation(self):
        args = ["--root", str(self.root), "--codex", str(self.base / "codex"),
                "--sandbox-home", str(self.base / "profile"), "--path", str(self.pdf),
                "--request-id=" + REQUEST_ID, "--item-id=--literal'$(not-a-command)"]
        with mock.patch.object(transport.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(transport.main(args), 0)
        self.assertEqual(run.call_args.args[0][-2:], ["--request-id=" + REQUEST_ID, "--item-id=--literal'$(not-a-command)"])
        self.assertEqual(run.call_args.kwargs["input"], self.pdf.read_bytes())
        with mock.patch.object(transport, "read_attachment") as read:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                transport.main(args[:-1])
            read.assert_not_called()

    def test_isolated_host_process_only_uses_two_existing_profiles(self):
        (self.root / ".venv/bin").mkdir(parents=True)
        (self.root / ".venv/bin/python").symlink_to(sys.executable)
        (self.root / "scripts").mkdir()
        shutil.copyfile(PROJECT / "scripts/import_attachment.py", self.root / "scripts/import_attachment.py")
        codex = self.base / "codex"
        log = self.base / "calls.jsonl"
        codex.write_text("#!" + sys.executable + "\n" + f'''
import hashlib, json, pathlib, sys
args = sys.argv[1:]
payload = sys.stdin.buffer.read()
profile = args[args.index('-P') + 1]
with pathlib.Path({str(log)!r}).open('a') as output:
    output.write(json.dumps({{'argv': args, 'profile': profile, 'sha256': hashlib.sha256(payload).hexdigest()}}) + '\\n')
if 'prepare' in args:
    specification = json.loads(payload)
    print(json.dumps({{'request_id': {REQUEST_ID!r}, 'items': {{i['item_id']: {{'state': 'pending'}} for i in specification['items']}}}}))
elif profile == 'research-store':
    print(json.dumps({{'stored': True}}))
else:
    print(json.dumps({{'request_id': {REQUEST_ID!r}, 'state': 'queued'}}))
''')
        codex.chmod(0o700)
        original = self.pdf.read_bytes()
        info = self.pdf.stat()
        payload = json.dumps(self.specification).encode()
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HELPER), *self.args], input=payload + b"\n" + host.SENTINEL + b"\n", capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"request_id": REQUEST_ID, "state": "queued"})
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual([call["profile"] for call in calls], ["research-review-worker", "research-store", "research-review-worker"])
        self.assertIn("prepare", calls[0]["argv"])
        self.assertEqual(calls[1]["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(calls[0]["sha256"], calls[2]["sha256"])
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(self.pdf.stat().st_ino, info.st_ino)
        self.assertEqual(self.pdf.stat().st_mtime_ns, info.st_mtime_ns)


if __name__ == "__main__":
    unittest.main()
