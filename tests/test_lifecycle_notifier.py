from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from research_store.review_lifecycle import Lifecycle, _empty, _save, control_lock, read_record

PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lifecycle_notifier_test", PROJECT / "scripts/background_notifier.py")
NOTIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NOTIFY)


class LifecycleNotifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
        self.at = 1800000000.0
        self.state = _empty()
        self.state["requests"]["A"] = {
            "state": "running", "expires_at": None,
            "usage": {"execution_seconds": 400},
            "links": {"review": {"pages": [1, 2, 3, 4], "outcomes": {"1": "verified"}}},
        }
        self.save()
        self.engine = Lifecycle(self.root, clock=lambda: self.at, snapshot=self.forbidden_snapshot)

    def forbidden_snapshot(self):
        self.fail("Notification process must never read or recover document storage")

    def save(self):
        with control_lock(self.root):
            _save(self.root, self.state)

    def event(self, kind="progress"):
        self.state["events"] = [{"event_id": "A:1", "request_id": "A", "kind": kind,
            "sequence": 1, "created_at": self.at, "attempts": 0, "delivered": False}]
        self.save()

    def test_notifications_claim_and_deliver_without_storage_transaction(self):
        self.event()
        with patch.object(NOTIFY.legacy, "_macos_notification") as send:
            self.assertTrue(NOTIFY.deliver_one(self.engine))
        self.assertIn("1/4", send.call_args.args[0])
        self.assertTrue(read_record(self.root)["events"][0]["delivered"])

    def test_completion_failure_keeps_bounded_retry_alive_after_review_exits(self):
        self.state["requests"]["A"]["state"] = "evidence_ready"
        self.event("evidence_ready")
        with patch.object(NOTIFY.legacy, "_macos_notification", side_effect=RuntimeError("test delivery")) as send:
            for attempt in range(3):
                self.assertTrue(NOTIFY.deliver_one(self.engine))
                pending = NOTIFY.queue_due(self.root, now=self.at)
                self.assertEqual(pending, attempt < 2)
                self.at += 31
        self.assertEqual(send.call_count, 3)
        self.assertIsNone(self.engine.claim_event())
        self.assertEqual(read_record(self.root)["notification_watcher"]["error"], "delivery_failed")

    def test_short_review_does_not_replay_old_percentage_after_delay(self):
        self.state["requests"]["A"]["usage"]["execution_seconds"] = 10
        self.save()
        NOTIFY.queue_due(self.root, now=self.at)
        self.state = read_record(self.root)
        self.assertEqual([e["kind"] for e in self.state["events"]], ["started"])
        self.state["requests"]["A"]["usage"]["execution_seconds"] = 400
        self.save()
        NOTIFY.queue_due(self.root, now=self.at)
        self.assertFalse(any(e["kind"] == "progress" for e in read_record(self.root)["events"]))
        self.state["requests"]["A"]["links"]["review"]["outcomes"]["2"] = "verified"
        self.save()
        NOTIFY.queue_due(self.root, now=self.at)
        progress = [e for e in read_record(self.root)["events"] if e["kind"] == "progress"]
        self.assertEqual(len(progress), 1)
        self.assertEqual(progress[0]["counts"]["percent"], 50)

    def test_cancel_during_delivery_ack_does_not_restore_request(self):
        self.event()
        def send_and_cancel(message):
            with control_lock(self.root):
                current = read_record(self.root)
                current["requests"]["A"]["state"] = "cancelled"
                _save(self.root, current)
        with patch.object(NOTIFY.legacy, "_macos_notification", side_effect=send_and_cancel):
            NOTIFY.deliver_one(self.engine)
        self.assertEqual(read_record(self.root)["requests"]["A"]["state"], "cancelled")

    def test_expired_or_cancelled_request_never_sends_or_keeps_watcher_alive(self):
        for state, expires in (("cancelled", None), ("paused", self.at - 1)):
            with self.subTest(state=state):
                self.state["requests"]["A"].update(state=state, expires_at=expires)
                self.event()
                with patch.object(NOTIFY.legacy, "_macos_notification") as send:
                    self.assertFalse(NOTIFY.deliver_one(self.engine))
                send.assert_not_called()
                self.assertFalse(NOTIFY.queue_due(self.root, now=self.at))

    def test_warning_does_not_stop_and_has_no_source_names(self):
        self.event("budget_warning")
        with patch.object(NOTIFY.legacy, "_macos_notification") as send:
            NOTIFY.deliver_one(self.engine)
        self.assertIn("검토는 계속", send.call_args.args[0])
        self.assertEqual(read_record(self.root)["requests"]["A"]["state"], "running")
        self.assertNotIn(str(self.root), send.call_args.args[0])

    def test_host_preflight_failure_records_diagnostic_without_stopping_review(self):
        failed = subprocess.CompletedProcess([], 1, b"", b"sandbox_apply: Operation not permitted")
        with patch.dict("os.environ", {"RESEARCH_AGENT_NOTIFICATIONS": "1"}), \
             patch.object(NOTIFY.legacy, "_notifier_active", return_value=False), \
             patch.object(NOTIFY.subprocess, "run", return_value=failed), \
             patch.object(NOTIFY.subprocess, "Popen") as process:
            self.assertFalse(NOTIFY.launch(self.root))
        process.assert_not_called()
        stored = read_record(self.root)
        self.assertEqual(stored["requests"]["A"]["state"], "running")
        self.assertEqual(stored["notification_watcher"]["state"], "unavailable")

    def test_host_watcher_profile_stays_narrow(self):
        self.assertIn("(deny file-write*)", NOTIFY.legacy.NOTIFIER_PROFILE)
        self.assertIn("(deny network*)", NOTIFY.legacy.NOTIFIER_PROFILE)
        self.assertIn('param "RESEARCH_NOTIFY_DIR"', NOTIFY.legacy.NOTIFIER_PROFILE)


if __name__ == "__main__":
    unittest.main()
