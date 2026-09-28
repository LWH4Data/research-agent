from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from research_store.review_lifecycle import (DIRECTORY, Lifecycle, Limits,
    ResultFence, control_lock, read_record, validate_result)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
        self.at = 1_800_000_000.0
        self.docs = [{"document_key": "s:one.pdf", "sha256": "a" * 64, "incarnation": "i1",
                      "pages": {"1": "pending", "2": "pending", "3": "pending"}, "output_path": "knowledge/one.md"},
                     {"document_key": "s:two.pdf", "sha256": "b" * 64, "incarnation": "i2",
                      "pages": {"1": "pending"}, "output_path": "knowledge/two.md"}]
        self.engine = Lifecycle(self.root, clock=lambda: self.at, snapshot=lambda: self.docs)

    def create(self, key="a", pages=None, *, doc=0, limits=None):
        scope = {"items": [{"item_id": "input", "document_key": self.docs[doc]["document_key"],
                            "sha256": self.docs[doc]["sha256"], "pages": pages or [1, 2]}]}
        receipt = self.engine.begin(f"vr2.{int(self.at + 10000)}.{key * 16}", self.at + 10000, scope, limits=limits)
        return self.engine.attach(receipt["request_id"], "input", self.docs[doc])

    def execution(self):
        execution = self.engine.reserve()
        self.assertIsNotNone(execution)
        return self.engine.acknowledge(execution["execution_id"], {"pid": 99, "birth": "test", "group": 99})

    def fence(self, execution, page=1):
        return {k: page if k == "page" else execution[k] for k in ResultFence.__dataclass_fields__}

    def test_01_distinct_documents_keep_scopes_and_counts(self):
        a = self.create()
        execution = self.execution()
        b = self.create("b", [1], doc=1)
        self.assertNotEqual(next(iter(a["links"])), next(iter(b["links"])))
        self.assertEqual(self.engine.status(b["request_id"])["usage"]["page_attempts"], 0)
        self.assertEqual(read_record(self.root)["execution"]["execution_id"], execution["execution_id"])

    def test_02_concurrent_partial_overlap_receives_distinct_request_identity(self):
        with ThreadPoolExecutor(4) as pool:
            requests = list(pool.map(lambda key: self.create(key, [1] if key == "a" else [1, 2]), "abcd"))
        self.assertEqual(len({r["request_id"] for r in requests}), 4)
        self.assertEqual(len({next(iter(r["links"])) for r in requests}), 1)
        self.assertIsNotNone(self.engine.reserve())
        self.assertIsNone(self.engine.reserve())

    def test_03_retry_same_key_and_partial_failure(self):
        spec = {"items": [{"item_id": "ok", "document_key": "s:one.pdf"}, {"item_id": "bad", "attachment": "/missing.pdf"}]}
        first = self.engine.begin(f"vr2.{int(self.at + 100)}.stable-caller-key", self.at + 100, spec)
        self.engine.attach(first["request_id"], "ok", self.docs[0])
        self.engine.attach(first["request_id"], "bad", None, error="attachment missing")
        again = self.engine.begin(f"vr2.{int(self.at + 100)}.stable-caller-key", self.at + 100, spec)
        self.assertEqual(first["request_id"], again["request_id"])
        self.assertEqual(again["items"]["bad"]["state"], "failed")
        self.assertEqual(len(again["links"]), 1)

    def test_04_reservation_is_not_running_until_exact_acknowledgement(self):
        a = self.create()
        reservation = self.engine.reserve()
        self.assertEqual(self.engine.status(a["request_id"])["state"], "queued")
        with self.assertRaises(ValueError):
            self.engine.acknowledge("wrong", {})
        self.engine.acknowledge(reservation["execution_id"], {"pid": 1})
        self.assertEqual(self.engine.status(a["request_id"])["state"], "running")

    def test_05_cancel_A_preserves_B_and_page_specific_authority(self):
        a = self.create()
        ex = self.execution()
        b = self.create("b", [2])
        self.engine.control("cancel", request_id=a["request_id"])
        validate_result(self.root, self.fence(ex, 2), self.docs[0], at=self.at)
        with self.assertRaises(ValueError):
            validate_result(self.root, self.fence(ex, 1), self.docs[0], at=self.at)
        self.assertEqual(self.engine.status(b["request_id"])["state"], "queued")
        self.assertFalse(self.engine.status(b["request_id"])["answered"])

    def test_06_stale_generation_version_incarnation_and_expiry_rejected(self):
        a = self.create(limits=Limits(retention_seconds=2))
        ex = self.execution()
        for field, value in (("generation", 4), ("incarnation", "another"), ("sha256", "c" * 64)):
            fence = self.fence(ex)
            fence[field] = value
            with self.assertRaises(ValueError):
                validate_result(self.root, fence, self.docs[0], at=self.at)
        self.engine.control("pause", request_id=a["request_id"])
        with self.assertRaises(ValueError):
            validate_result(self.root, self.fence(ex), self.docs[0], at=self.at)
        self.at += 3
        with self.assertRaises(ValueError):
            self.engine.status(a["request_id"])

    def test_07_thresholds_warn_but_never_stop_or_trim(self):
        a = self.create(pages=[1, 2, 3], limits=Limits(execution_seconds=1, page_attempts=1))
        ex = self.execution()
        self.assertEqual(ex["pages"], [1, 2, 3])
        self.at += 20
        self.assertEqual(self.engine.check_execution(ex["execution_id"])["state"], "running")
        validate_result(self.root, self.fence(ex), self.docs[0], at=self.at)
        self.assertTrue(any(e["kind"] == "budget_warning" for e in read_record(self.root)["events"]))
        self.assertIsNone(self.engine.status(a["request_id"])["token_usage"])

    def test_08_event_acknowledgement_does_not_revert_concurrent_cancel(self):
        a = self.create()
        event = self.engine.claim_event()
        self.engine.control("cancel", request_id=a["request_id"])
        self.engine.delivered(event["event_id"], success=True)
        self.assertEqual(self.engine.status(a["request_id"])["state"], "cancelled")
        self.assertIsNone(self.engine.claim_event())

    def test_09_expiry_does_not_delete_live_reservation_or_shared_job(self):
        a = self.create(limits=Limits(retention_seconds=1))
        ex = self.execution()
        b = self.create("b")
        self.engine.control("cancel", request_id=a["request_id"])
        self.at += 2
        result = self.engine.cleanup()
        self.assertTrue(result["cleanup_pending"])
        self.assertIn(a["request_id"], read_record(self.root)["requests"])
        validate_result(self.root, self.fence(ex), self.docs[0], at=self.at)
        self.engine.finish(ex["execution_id"])
        self.engine.release_execution(ex["execution_id"])
        self.engine.cleanup()
        state = read_record(self.root)
        self.assertNotIn(a["request_id"], state["requests"])
        self.assertIn(b["request_id"], state["requests"])
        self.assertEqual(len(state["reviews"]), 1)

    def test_10_legacy_state_requires_explicit_migration(self):
        folder = self.root / DIRECTORY
        folder.mkdir(parents=True)
        (folder / "job.json").write_text('{"version":1,"state":"running"}')
        with self.assertRaisesRegex(ValueError, "migration|migrate"):
            self.create()

    def test_11_key_conflict_early_deletion_and_expired_key_cannot_resurrect(self):
        a = self.create()
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.create(pages=[3])
        self.engine.forget(a["request_id"])
        with self.assertRaisesRegex(ValueError, "deleted|expired"):
            self.create()
        with self.assertRaisesRegex(ValueError, "expired"):
            self.engine.begin(f"vr2.{int(self.at - 1)}.expired-key-12345", self.at - 1, {"items": [{"item_id": "x"}]})

    def test_12_committed_evidence_repairs_requests_after_callback_loss(self):
        a = self.create()
        ex = self.execution()
        b = self.create("b")
        self.engine.control("cancel", request_id=a["request_id"])
        self.docs[0]["pages"].update({"1": "verified", "2": "needs_review"})
        # No callback/update after durable page result. Status reconciles it.
        status = self.engine.status(b["request_id"])
        self.assertEqual(status["state"], "unresolved")
        self.assertEqual(self.engine.status(a["request_id"])["requested_state"], "cancelled")

    def test_13_unknown_execution_never_allows_second_reservation(self):
        self.create()
        ex = self.execution()
        with self.engine.transaction() as state:
            state["execution"].update(state="stopping", termination_error="unknown child exit")
        self.assertIsNone(self.engine.reserve())
        with self.assertRaises(ValueError):
            self.engine.release_execution(ex["execution_id"])

    def test_14_late_joiner_has_no_retroactive_attempt_or_time_charge(self):
        a = self.create()
        ex = self.execution()
        self.at += 5
        b = self.create("b", limits=Limits(execution_seconds=0, page_attempts=0))
        self.at += 5
        self.engine.finish(ex["execution_id"])
        self.engine.release_execution(ex["execution_id"])
        self.assertEqual(self.engine.status(a["request_id"])["usage"], {"execution_seconds": 10.0, "page_attempts": 2})
        self.assertEqual(self.engine.status(b["request_id"])["usage"], {"execution_seconds": 0.0, "page_attempts": 0})
        self.assertIsNotNone(self.engine.reserve())  # zero advisory threshold grants normal user-authorized work

    def test_15_departed_sponsor_remains_accounted_without_cost_transfer(self):
        a = self.create(limits=Limits(execution_seconds=3))
        ex = self.execution()
        b = self.create("b")
        self.engine.control("cancel", request_id=a["request_id"])
        self.at += 4
        running = self.engine.check_execution(ex["execution_id"])
        self.assertEqual(running["sponsors"], [a["request_id"]])
        self.assertEqual(running["state"], "running")
        self.assertEqual(self.engine.status(b["request_id"])["usage"]["execution_seconds"], 0)

    def test_16_global_hold_survives_late_intake_and_document_resume(self):
        a = self.create()
        self.engine.control("pause", request_id=a["request_id"])
        self.engine.control("pause", library=True)
        b = self.create("b")
        self.engine.control("resume", document_key="s:one.pdf")
        self.assertIsNone(self.engine.reserve())
        restarted = Lifecycle(self.root, clock=lambda: self.at, snapshot=lambda: self.docs)
        restarted.control("resume", library=True)
        self.assertEqual(restarted.status(a["request_id"])["state"], "paused")
        self.assertIsNotNone(restarted.reserve())
        self.assertEqual(restarted.status(b["request_id"])["usage"]["page_attempts"], 2)

    def test_same_request_multiple_items_union_scope(self):
        spec = {"items": [{"item_id": "one", "document_key": "s:one.pdf", "pages": [1]},
                          {"item_id": "two", "document_key": "s:one.pdf", "pages": [2]}]}
        request = self.engine.begin(f"vr2.{int(self.at + 100)}.multiple-items-key", self.at + 100, spec)
        self.engine.attach(request["request_id"], "one", self.docs[0])
        result = self.engine.attach(request["request_id"], "two", self.docs[0])
        self.assertEqual(next(iter(result["links"].values()))["pages"], [1, 2])

    def test_pending_second_input_never_sends_whole_request_completion(self):
        self.docs[0]["pages"]["1"] = "verified"
        spec = {"items": [{"item_id": "one", "document_key": "s:one.pdf", "pages": [1]},
                          {"item_id": "two", "document_key": "s:two.pdf", "pages": [1]}]}
        request = self.engine.begin(f"vr2.{int(self.at + 100)}.multiple-items-key", self.at + 100, spec,
                                    limits=Limits(retention_seconds=1))
        first = self.engine.attach(request["request_id"], "one", self.docs[0])
        self.assertEqual(first["state"], "intake")
        self.assertIsNone(first["expires_at"])
        self.at += 2
        second = self.engine.attach(request["request_id"], "two", self.docs[1])
        self.assertEqual(second["state"], "queued")

    def test_pause_before_first_link_persists(self):
        spec = {"items": [{"item_id": "one", "document_key": "s:one.pdf"}]}
        request = self.engine.begin(f"vr2.{int(self.at + 100)}.pause-before-link", self.at + 100, spec)
        self.engine.control("pause", request_id=request["request_id"])
        result = self.engine.attach(request["request_id"], "one", self.docs[0])
        self.assertEqual(result["state"], "paused")
        self.assertIsNone(self.engine.reserve())

    def test_key_expiry_cannot_be_extended_after_denial_marker_cleanup(self):
        expires = int(self.at + 10)
        key = f"vr2.{expires}.immutable-key-123"
        spec = {"items": [{"item_id": "one", "document_key": "s:one.pdf"}]}
        request = self.engine.begin(key, expires, spec)
        self.engine.forget(request["request_id"])
        self.at += 20
        self.engine.cleanup()
        self.assertEqual(read_record(self.root)["keys"], {})
        with self.assertRaisesRegex(ValueError, "immutable expiry"):
            self.engine.begin(key, int(self.at + 100), spec)

    def test_explicit_rereview_waits_for_new_fence_and_ordinary_unresolved_does_not_retry(self):
        self.docs[0]["pages"]["1"] = "needs_review"
        ordinary = self.create(pages=[1])
        self.assertEqual(ordinary["state"], "unresolved")
        self.assertIsNone(self.engine.reserve())
        expires = int(self.at + 100)
        request = self.engine.begin(f"vr2.{expires}.explicit-rereview", expires,
            {"items": [{"item_id": "one", "document_key": "s:one.pdf", "pages": [1], "rereview": True}]})
        self.engine.attach(request["request_id"], "one", self.docs[0])
        execution = self.execution()
        self.docs[0]["page_fences"] = {"1": self.fence(execution)}
        self.assertEqual(self.engine.status(request["request_id"])["state"], "unresolved")

    def test_library_held_request_expires_but_persistent_hold_remains(self):
        self.engine.control("pause", library=True)
        request = self.create(limits=Limits(retention_seconds=1))
        self.assertEqual(request["state"], "held")
        self.assertEqual(request["expires_at"], self.at + 1)
        self.at += 2
        self.engine.cleanup()
        self.assertTrue(read_record(self.root)["policy"]["global_hold"])
        self.engine.control("resume", library=True)
        self.assertIsNone(self.engine.reserve())
        with self.assertRaises(ValueError):
            self.engine.status(request["request_id"])

    def test_resume_of_already_ready_request_keeps_bounded_retention(self):
        self.docs[0]["pages"]["1"] = "verified"
        request = self.create(pages=[1], limits=Limits(retention_seconds=10))
        deadline = request["expires_at"]
        self.at += 2
        self.engine.control("resume", request_id=request["request_id"])
        status = self.engine.status(request["request_id"])
        self.assertEqual(status["state"], "evidence_ready")
        self.assertEqual(status["expires_at"], deadline)


if __name__ == "__main__":
    unittest.main()
