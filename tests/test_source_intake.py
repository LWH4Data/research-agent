from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_intake", PROJECT / "scripts/source_intake.py")
intake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intake)


class SourceIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "store"
        self.paths = [self.base / name for name in ("new 자료", "existing", "reenabled")]
        for path in self.paths:
            path.mkdir()
        self.rows = [{"id": f"source-{i}", "path": str(path), "access": "read-only"}
                     for i, path in enumerate(self.paths)]
        self.registration = {"added": [self.rows[0], self.rows[2]], "selected": self.rows, "cancelled": False}
        self.key = {"key": "vr2.9999999999." + "b" * 32, "key_expires_at": 9999999999}
        self.prepared = {"request_id": "a" * 32, "state": "intake", "links": {},
                         "items": {f"source-{i}": {"state": "pending"} for i in (1, 2, 3)}}
        self.submitted = {**self.prepared, "state": "held", "global_hold": True,
                          "items": {f"source-{i}": {"state": "complete"} for i in (1, 2, 3)},
                          "usage": {"page_attempts": 0}, "handoff": {"worker": "idle"}}
        self.error_output = self.enterContext(redirect_stderr(io.StringIO()))
        self.run = self.enterContext(mock.patch.object(intake.subprocess, "run"))
        self.responses(self.registration, self.key, self.prepared, self.submitted)

    def responses(self, *values):
        self.run.side_effect = [subprocess.CompletedProcess([], 0, json.dumps(value))
                               if isinstance(value, dict) else value for value in values]

    def connect(self, paths=None, **options):
        return intake.connect_sources(self.root, self.paths if paths is None else paths,
            codex=options.pop("codex", str(self.base / "codex")), sandbox_home=str(self.base / "profile"),
            **options)

    def test_exact_selected_sources_share_one_managed_request_and_fixed_commands(self):
        result, code = self.connect(paths=self.paths + [self.paths[0]])
        self.assertEqual(code, 0, result)
        self.assertEqual(result["selected"], self.rows)
        self.assertEqual(result["processing"]["request"]["state"], "held")
        self.assertEqual(result["processing"]["request"]["usage"]["page_attempts"], 0)
        calls = self.run.call_args_list
        self.assertEqual(calls[0].args[0], [str(self.base / "codex"), "sandbox", "-P", "research-store",
            "-C", str(self.base / "profile"), "--", str(self.root / "research-store"),
            "source-add", "--", *map(str, self.paths), str(self.paths[0])])
        public_review = str(self.root / "resources/skills/research-library/scripts/research-review")
        self.assertEqual(calls[1].args[0], [public_review, "key"])
        self.assertEqual([call.args[0][1] for call in calls[2:]], ["prepare", "submit"])
        expected = {"items": [{"item_id": f"source-{i + 1}", "source_id": row["id"]}
                              for i, row in enumerate(self.rows)]}
        for call in calls[2:]:
            self.assertEqual(call.args[0][0], public_review)
            self.assertEqual(call.kwargs["input"], json.dumps(expected, ensure_ascii=False)
                             + "\n__RESEARCH_STORE_STDIN_END__\n")
            self.assertIn(self.key["key"], call.args[0])
        self.assertEqual(result["processing"]["retry"]["specification"], expected)
        self.assertFalse(self.root.exists())
        self.assertTrue(all(not list(path.iterdir()) for path in self.paths))

    def test_empty_selection_does_nothing(self):
        result, code = self.connect(paths=[])
        self.assertEqual(code, 0)
        self.assertTrue(result["cancelled"])
        self.run.assert_not_called()

    def test_registration_failure_never_starts_intake(self):
        self.responses(subprocess.CompletedProcess([], 17, ""))
        result, code = self.connect()
        self.assertEqual(code, 1)
        self.assertEqual(result["registration"], "unknown")
        self.assertEqual(self.run.call_count, 1)

    def test_invalid_selection_receipts_cannot_expand_or_shrink_scope(self):
        invalid = [[], self.rows[:2], self.rows + [self.rows[0]], list(reversed(self.rows)),
                   [{**self.rows[0], "access": "writable"}, *self.rows[1:]],
                   [{**self.rows[0], "path": "/unselected"}, *self.rows[1:]],
                   [{**self.rows[0], "id": "--private"}, *self.rows[1:]],
                   [{**self.rows[0], "id": self.rows[1]["id"]}, *self.rows[1:]]]
        for rows in invalid:
            with self.subTest(rows=rows):
                self.run.reset_mock()
                self.responses({**self.registration, "selected": rows})
                result, code = self.connect()
                self.assertEqual(code, 1)
                self.assertEqual(result["processing"]["state"], "not_started")
                self.assertEqual(self.run.call_count, 1)

    def test_registration_only_does_not_mint_key_or_submit(self):
        result, code = self.connect(registration_only=True)
        self.assertEqual(code, 0)
        self.assertEqual(result["processing"], {"state": "not_started", "reason": "registration_only"})
        self.assertEqual(self.run.call_count, 1)

    def test_missing_codex_cannot_fall_back_during_runtime(self):
        result, code = self.connect(codex=None)
        self.assertEqual(code, 1)
        self.assertEqual(result["processing"]["reason"], "codex_unavailable")
        self.run.assert_not_called()

    def test_install_without_codex_registers_only_then_defers(self):
        result, code = self.connect(codex=None, installation=True)
        self.assertEqual(code, 0)
        self.assertEqual(result["registration"], "registered")
        self.assertEqual(result["processing"], {"state": "deferred", "reason": "codex_unavailable"})
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(self.run.call_args.args[0], [str(self.root / "research-store"),
                                                     "source-add", "--", *map(str, self.paths)])

    def test_submit_failure_preserves_registration_prepared_request_and_same_key(self):
        self.responses(self.registration, self.key, self.prepared, PermissionError("denied"))
        result, code = self.connect()
        self.assertEqual(code, 1)
        self.assertEqual(result["registration"], "registered")
        self.assertEqual(result["processing"]["state"], "deferred")
        self.assertEqual(result["processing"]["request"]["request_id"], self.prepared["request_id"])
        self.assertEqual(result["processing"]["retry"]["key"], self.key["key"])
        self.assertEqual(self.run.call_count, 4)

    def test_recovery_receipt_is_flushed_before_pdf_side_effects(self):
        responses = iter([self.registration, self.key, self.prepared, self.submitted])
        def run(command, **kwargs):
            if command[1] == "submit":
                self.assertIn(self.key["key"], self.error_output.getvalue())
                self.assertIn(self.prepared["request_id"], self.error_output.getvalue())
            return subprocess.CompletedProcess(command, 0, json.dumps(next(responses)))
        self.run.side_effect = run
        self.assertEqual(self.connect()[1], 0)

    def test_key_or_prepare_failure_does_not_submit_or_remove_registration(self):
        for responses in ((self.registration, {"key": "bad"}),
                          (self.registration, self.key, {"request_id": "bad"})):
            with self.subTest(responses=responses):
                self.run.reset_mock()
                self.responses(*responses)
                result, code = self.connect()
                self.assertEqual(code, 1)
                self.assertEqual(result["registration"], "registered")
                self.assertEqual(self.run.call_count, len(responses))

    def test_review_startup_failure_is_not_reported_as_running_or_queued(self):
        self.responses(self.registration, self.key, self.prepared,
                       {**self.submitted, "handoff": {"worker": "startup_failed"}})
        result, code = self.connect()
        self.assertEqual(code, 1)
        self.assertEqual(result["processing"]["state"], "deferred")
        self.assertEqual(result["processing"]["reason"], "review_startup_failed")

    def test_partial_storage_failure_preserves_request_details(self):
        receipt = {**self.submitted, "state": "partial_failure", "links": {"one": {}},
                   "items": {**self.submitted["items"], "source-1": {"state": "failed"}}}
        self.responses(self.registration, self.key, self.prepared, receipt)
        result, code = self.connect()
        self.assertEqual(code, 1)
        self.assertEqual(result["processing"]["state"], "partial_failure")
        self.assertEqual(result["processing"]["request"], receipt)

    def test_interrupt_during_submit_keeps_recovery_identity(self):
        self.responses(self.registration, self.key, self.prepared, KeyboardInterrupt())
        result, code = self.connect()
        self.assertEqual(code, 130)
        self.assertEqual(result["registration"], "registered")
        self.assertEqual(result["processing"]["request"]["request_id"], "a" * 32)


if __name__ == "__main__":
    unittest.main()
