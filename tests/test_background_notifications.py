from __future__ import annotations

from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
import fcntl
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/background_review.py"
SPEC = importlib.util.spec_from_file_location("background_review_notifications", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def notification_root(base: Path) -> tuple[Path, Path]:
    root = (base / "research-agent").resolve()
    root.mkdir()
    (root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
    jobs = root / ".research-store/visual-review"
    jobs.mkdir(parents=True)
    review._atomic_json(jobs / "job.json", {
        "version": 1, "job_id": "job-1", "state": "running",
    })
    return root, jobs


def job(total: int, processed: int = 0, *, uncertain: int = 0,
        age_seconds: int = 301) -> dict:
    return {
        "started_at": (NOW - timedelta(seconds=age_seconds)).isoformat(),
        "seen_pages": [["paper:a", page] for page in range(1, total + 1)],
        "confirmed_pages": [
            ["paper:a", page, "needs_review" if page <= uncertain else "verified"]
            for page in range(1, processed + 1)
        ],
        "notification_milestone": 0,
    }


class BackgroundNotificationTests(TestCase):
    def test_short_job_records_crossed_quarter_without_alert(self) -> None:
        current = job(4, 1, age_seconds=299)
        self.assertIsNone(review._notification_milestone(current, now=NOW))
        self.assertEqual(current["notification_milestone"], 25)
        self.assertIsNone(review._notification_milestone(
            current, now=NOW + timedelta(seconds=2)))
        current["confirmed_pages"].append(["paper:a", 2, "verified"])
        self.assertEqual(
            review._notification_milestone(current, now=NOW + timedelta(seconds=2)),
            (50, 2, 4, 0),
        )
        self.assertEqual(current["notification_milestone"], 50)

    def test_long_job_reports_one_actual_percentage_per_new_quarter(self) -> None:
        current = job(10, 6, uncertain=1)
        self.assertEqual(review._notification_milestone(current, now=NOW), (60, 6, 10, 1))
        self.assertEqual(current["notification_milestone"], 50)
        self.assertIsNone(review._notification_milestone(current, now=NOW))
        current["confirmed_pages"].append(["paper:a", 7, "verified"])
        self.assertIsNone(review._notification_milestone(current, now=NOW))
        current["confirmed_pages"].append(["paper:a", 8, "verified"])
        self.assertEqual(review._notification_milestone(current, now=NOW), (80, 8, 10, 1))
        current["confirmed_pages"].extend([
            ["paper:a", 9, "verified"], ["paper:a", 10, "verified"],
        ])
        self.assertIsNone(review._notification_milestone(current, now=NOW))

    def test_added_pages_do_not_repeat_a_milestone(self) -> None:
        current = job(4, 2)
        self.assertEqual(review._notification_milestone(current, now=NOW), (50, 2, 4, 0))
        current["seen_pages"].extend([["paper:b", page] for page in range(1, 5)])
        self.assertIsNone(review._notification_milestone(current, now=NOW))
        current["confirmed_pages"].extend([
            ["paper:b", 1, "verified"], ["paper:b", 2, "verified"],
        ])
        self.assertIsNone(review._notification_milestone(current, now=NOW))
        current["confirmed_pages"].extend([
            ["paper:b", 3, "verified"], ["paper:b", 4, "verified"],
        ])
        self.assertEqual(review._notification_milestone(current, now=NOW), (75, 6, 8, 0))

    def test_current_pending_page_invalidates_old_confirmation(self) -> None:
        current = job(4, 2)
        queue = [{"document_key": "paper:a", "page_number": 1, "status": "pending"}]
        self.assertEqual(
            review._notification_milestone(current, now=NOW, queue=queue),
            (25, 1, 4, 0),
        )

    def test_uncertain_page_is_processed_but_not_called_verified(self) -> None:
        current = job(4, 1, uncertain=1)
        queue = [{"document_key": "paper:a", "page_number": 1,
                  "status": "needs_review"}]
        self.assertEqual(review._notification_milestone(current, now=NOW, queue=queue),
                         (25, 1, 4, 1))
        message = review._notification_message(
            "progress", percent=25, processed=1, total=4, needs_review=1,
        )
        self.assertIn("1/4", message)
        self.assertIn("추가 확인 1쪽", message)
        self.assertNotIn("검증 완료", message)

    def test_duplicate_confirmations_and_empty_job_do_not_inflate_progress(self) -> None:
        current = job(4, 1)
        current["confirmed_pages"].append(["paper:a", 1, "verified"])
        self.assertEqual(review._notification_milestone(current, now=NOW), (25, 1, 4, 0))
        self.assertIsNone(review._notification_milestone(job(0), now=NOW))

    def test_terminal_messages_are_generic_and_distinguish_uncertainty(self) -> None:
        complete = review._notification_message("completed", processed=4, total=4)
        uncertain = review._notification_message(
            "completed_with_uncertainty", processed=4, total=4, needs_review=1,
        )
        failed = review._notification_message("failed")
        interrupted = review._notification_message("interrupted")
        self.assertIn("4/4쪽 검증", complete)
        self.assertIn("3쪽 검증", uncertain)
        self.assertIn("1쪽 추가 확인 필요", uncertain)
        self.assertIn("저장된 결과", failed)
        self.assertIn("저장된 결과", interrupted)
        for message in (complete, uncertain, failed, interrupted):
            self.assertNotIn("paper:a", message)
            self.assertNotIn("/Users/", message)

    def test_inactive_worker_is_marked_interrupted_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            jobs = Path(directory)
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "job-1", "state": "running",
            })
            self.assertTrue(review._mark_interrupted_if_inactive(jobs))
            saved = review._read_json(jobs / "job.json")
            self.assertEqual(saved["state"], "interrupted")
            self.assertEqual(saved["notification_terminal"], "interrupted")
            self.assertIn("남은 페이지", saved["last_error"])
            self.assertFalse(review._mark_interrupted_if_inactive(jobs))
            self.assertEqual(
                (jobs / "worker.log").read_text(encoding="utf-8").count("interrupted job="), 1,
            )

    def test_active_worker_is_not_marked_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            jobs = Path(directory)
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "job-1", "state": "running",
            })
            lock = review._open_lock(jobs / "worker.lock")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertFalse(review._mark_interrupted_if_inactive(jobs))
                self.assertEqual(review._read_json(jobs / "job.json")["state"], "running")
            finally:
                os.close(lock)
            self.assertTrue(review._mark_interrupted_if_inactive(jobs))

    def test_status_marks_lost_worker_and_preserves_one_interruption_notice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            jobs = Path(directory)
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "job-1", "state": "running",
                "seen_pages": [], "confirmed_pages": [],
            })
            with patch.object(review, "_review_queue", return_value=[]):
                with review._control_lock(jobs):
                    reported = review._status_locked(Path(directory), jobs)
            self.assertEqual(reported["state"], "interrupted")
            self.assertEqual(review._claim_notification(jobs)[0], "interrupted")
            self.assertIsNone(review._claim_notification(jobs))
            self.assertFalse(review._mark_interrupted_if_inactive(jobs))

    def test_notification_failure_never_raises_into_review(self) -> None:
        with patch.object(review, "_queue_notification", side_effect=OSError("denied")):
            with patch.object(review, "_append_log") as log:
                review._notify_best_effort(Path("/unused"), "job-1", "failed")
        self.assertIn("notification failed", log.call_args.args[1])

    def test_notifier_claims_each_saved_event_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = (Path(directory) / "research-agent").resolve()
            root.mkdir()
            (root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
            jobs = root / ".research-store/visual-review"
            jobs.mkdir(parents=True)
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "job-1", "state": "completed",
            })
            review._queue_notification(
                jobs, "job-1", "completed", processed=4, total=4,
            )
            with patch.object(review, "NOTIFIER_IDLE_SECONDS", 0):
                with patch.object(review, "_macos_notification") as send:
                    review._notifier(root)
                    review._notifier(root)
            send.assert_called_once_with("시각 자료 확인 완료 · 4/4쪽 검증")
            state = review._read_json(jobs / "notifications.json")
            self.assertTrue(state["events"][0]["claimed"])

    def test_notifier_started_after_terminal_job_without_an_event_stays_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = (Path(directory) / "research-agent").resolve()
            root.mkdir()
            (root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
            jobs = root / ".research-store/visual-review"
            jobs.mkdir(parents=True)
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "job-1", "state": "completed",
            })
            with patch.object(review, "NOTIFIER_IDLE_SECONDS", 0):
                with patch.object(review, "_macos_notification") as send:
                    review._notifier(root)
            send.assert_not_called()

    def test_restart_drops_old_progress_but_preserves_old_terminal_notice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            jobs = Path(directory)
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "old", "state": "running",
            })
            review._queue_notification(jobs, "old", "progress", percent=25,
                                       processed=1, total=4)
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "old", "state": "failed",
            })
            review._queue_notification(jobs, "old", "failed")
            review._atomic_json(jobs / "job.json", {
                "version": 1, "job_id": "new", "state": "running",
            })
            review._queue_notification(jobs, "new", "progress", percent=25,
                                       processed=1, total=4)
            previous = review._claim_notification(jobs)
            self.assertEqual(previous[0], "failed")
            self.assertIn("이전 작업", previous[1])
            current = review._claim_notification(jobs)
            self.assertEqual(current[0], "progress")
            self.assertIn("1/4쪽", current[1])
            self.assertIsNone(review._claim_notification(jobs))

    def test_macos_notice_uses_fixed_system_command_without_document_data(self) -> None:
        message = review._notification_message(
            "progress", percent=50, processed=5, total=10,
        )
        with patch.object(review.sys, "platform", "darwin"):
            with patch.dict(review.os.environ, {"RESEARCH_AGENT_NOTIFICATIONS": "1"}):
                with patch.object(
                    review.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 0),
                ) as run:
                    review._macos_notification(message)
        self.assertEqual(run.call_args.args[0][:2], ["/usr/bin/osascript", "-e"])
        self.assertIn("Research Agent", run.call_args.args[0][2])
        self.assertIn("5/10쪽", run.call_args.args[0][2])
        self.assertNotIn("paper:a", run.call_args.args[0][2])
        self.assertIs(run.call_args.kwargs["stdout"], subprocess.PIPE)

    def test_notification_can_be_disabled_without_running_osascript(self) -> None:
        with patch.object(review.sys, "platform", "darwin"):
            with patch.dict(review.os.environ, {"RESEARCH_AGENT_NOTIFICATIONS": "0"}):
                with patch.object(review.subprocess, "run") as run:
                    review._macos_notification("시각 자료 확인 완료")
        run.assert_not_called()

    def test_macos_service_error_is_detected_even_with_zero_exit_code(self) -> None:
        result = subprocess.CompletedProcess([], 0, stderr=b"NSNotificationCenter connection invalid")
        with patch.object(review.sys, "platform", "darwin"):
            with patch.dict(review.os.environ, {"RESEARCH_AGENT_NOTIFICATIONS": "1"}):
                with patch.object(review.subprocess, "run", return_value=result):
                    with self.assertRaisesRegex(RuntimeError, "알림 서비스"):
                        review._macos_notification("시각 자료 확인 완료")

    def test_macos_notifier_profile_writes_only_owned_job_area(self) -> None:
        if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
            self.skipTest("macOS Seatbelt integration is unavailable")
        profile = review.NOTIFIER_PROFILE
        self.assertIn("(deny file-write*)", profile)
        self.assertIn("(deny network*)", profile)
        self.assertIn('(subpath (param "RESEARCH_NOTIFY_DIR"))', profile)
        with tempfile.TemporaryDirectory() as directory:
            # macOS reports TMPDIR through /var, which is a symlink to
            # /private/var. Seatbelt subpath parameters need the real path.
            base = Path(directory).resolve()
            jobs = base / "research-agent/.research-store/visual-review"
            source = base / "original-pdfs"
            jobs.mkdir(parents=True)
            source.mkdir()

            def confined_touch(target: Path) -> subprocess.CompletedProcess[bytes]:
                return subprocess.run(
                    ["/usr/bin/sandbox-exec", "-D", f"RESEARCH_NOTIFY_DIR={jobs}",
                     "-p", profile, "/usr/bin/touch", str(target)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                )

            owned_file = jobs / "notice.lock"
            owned_result = confined_touch(owned_file)
            if b"sandbox_apply" in owned_result.stderr and owned_result.returncode:
                self.skipTest("outer sandbox prevents nested Seatbelt integration")
            self.assertEqual(owned_result.returncode, 0, owned_result.stderr.decode())
            self.assertTrue(owned_file.exists())
            original = source / "paper.pdf"
            original.write_bytes(b"unchanged PDF placeholder")
            before = original.stat().st_mtime_ns
            denied_result = confined_touch(original)
            self.assertNotEqual(denied_result.returncode, 0)
            self.assertEqual(original.read_bytes(), b"unchanged PDF placeholder")
            self.assertEqual(original.stat().st_mtime_ns, before)
            self.assertNotEqual(confined_touch(source / "notice.lock").returncode, 0)
            self.assertFalse((source / "notice.lock").exists())
            linked_original = jobs / "linked-paper.pdf"
            linked_original.symlink_to(original)
            self.assertNotEqual(confined_touch(linked_original).returncode, 0)
            self.assertEqual(original.stat().st_mtime_ns, before)
            linked_source = jobs / "linked-source"
            linked_source.symlink_to(source, target_is_directory=True)
            self.assertNotEqual(
                confined_touch(linked_source / "notice.lock").returncode, 0,
            )
            self.assertFalse((source / "notice.lock").exists())


class NotifierSupervisorTests(TestCase):
    def test_readiness_requires_an_actually_held_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, jobs = notification_root(Path(directory))
            self.assertFalse(review._notifier_active(jobs))
            descriptor = review._open_lock(jobs / "notifier.lock")
            try:
                self.assertFalse(review._notifier_active(jobs))
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertTrue(review._notifier_active(jobs))
            finally:
                os.close(descriptor)
            self.assertFalse(review._notifier_active(jobs))

    def test_existing_watcher_is_recorded_active_without_a_second_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, jobs = notification_root(Path(directory))
            with patch.object(review, "_notifier_active", return_value=True):
                with patch.object(review.subprocess, "run") as probe:
                    with patch.object(review.subprocess, "Popen") as spawn:
                        self.assertTrue(review._launch_notifier(root))
            probe.assert_not_called()
            spawn.assert_not_called()
            saved = review._read_json(jobs / "job.json")
            self.assertEqual(saved["notification_watcher"], "active")
            self.assertIsNone(saved["notification_error"])

    def test_new_watcher_must_hold_lock_before_reported_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, jobs = notification_root(Path(directory))
            child = Mock()
            child.pid = 12345
            child.poll.return_value = None
            with patch.object(review, "_notifier_active", side_effect=[False, True]):
                with patch.object(review.subprocess, "run", return_value=
                                  subprocess.CompletedProcess([], 0, stderr=b"")) as probe:
                    with patch.object(review.subprocess, "Popen", return_value=child) as spawn:
                        self.assertTrue(review._launch_notifier(root))
            self.assertIn("RESEARCH_NOTIFY_DIR=", probe.call_args.args[0][2])
            self.assertIn(review.NOTIFIER_PROFILE, probe.call_args.args[0])
            self.assertTrue(spawn.call_args.kwargs["start_new_session"])
            self.assertEqual(review._read_json(jobs / "job.json")["notification_watcher"],
                             "active")

    def test_sandbox_apply_denial_is_recorded_and_warned_without_spawning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, jobs = notification_root(Path(directory))
            warning = io.StringIO()
            with redirect_stderr(warning):
                with patch.object(review, "_notifier_active", return_value=False):
                    with patch.object(review.subprocess, "run", return_value=
                                      subprocess.CompletedProcess(
                                          [], 1, stderr=b"sandbox_apply: Operation not permitted"
                                      )):
                        with patch.object(review.subprocess, "Popen") as spawn:
                            self.assertFalse(review._launch_notifier(root))
            spawn.assert_not_called()
            saved = review._read_json(jobs / "job.json")
            self.assertEqual(saved["state"], "running")
            self.assertEqual(saved["notification_watcher"], "unavailable")
            self.assertEqual(saved["notification_error"], "sandbox_apply_denied")
            self.assertIn("알림", warning.getvalue())
            self.assertNotIn(str(root), warning.getvalue())
            self.assertIn("sandbox_apply", (jobs / "notifier.stderr.log").read_text())

    def test_child_immediate_exit_is_not_reported_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, jobs = notification_root(Path(directory))
            child = Mock()
            child.pid = 12345
            child.poll.return_value = 1
            warning = io.StringIO()
            with redirect_stderr(warning):
                with patch.object(review, "_notifier_active", return_value=False):
                    with patch.object(review.subprocess, "run", return_value=
                                      subprocess.CompletedProcess([], 0, stderr=b"")):
                        with patch.object(review.subprocess, "Popen", return_value=child):
                            self.assertFalse(review._launch_notifier(root))
            saved = review._read_json(jobs / "job.json")
            self.assertEqual(saved["state"], "running")
            self.assertEqual(saved["notification_watcher"], "unavailable")
            self.assertEqual(saved["notification_error"], "notifier_exited")
            self.assertIn("알림", warning.getvalue())
