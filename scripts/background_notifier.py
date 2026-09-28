#!/usr/bin/env python3
"""Deliver v2 review notices with writes limited to the lifecycle directory.

The host entry point launches this watcher outside the nested review sandbox.
It never reads PDFs, recovers document journals, or launches a review model.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from research_store.review_lifecycle import (  # noqa: E402
    DIRECTORY, STATE_FILE, MAX_EVENTS, Lifecycle, _live, _save, control_lock, read_record,
)

spec = importlib.util.spec_from_file_location("research_review_notification_helpers", ROOT / "scripts/background_review.py")
assert spec is not None and spec.loader is not None
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

ACTIVE = {"intake", "queued", "running", "starting"}


def counts(request: dict[str, Any]) -> dict[str, int]:
    pages = {}
    for review_id, link in request.get("links", {}).items():
        for page in link.get("pages", []):
            pages[(review_id, page)] = link.get("outcomes", {}).get(str(page))
    verified = sum(value == "verified" for value in pages.values())
    uncertain = sum(value == "needs_review" for value in pages.values())
    total = len(pages)
    return {"processed": verified + uncertain, "total": total, "needs_review": uncertain,
            "percent": (verified + uncertain) * 100 // total if total else 0}


def queue_due(root: Path, *, now: float | None = None) -> bool:
    """Record notification cursors/outbox only; never repair the library."""
    now = time.time() if now is None else now
    with control_lock(root):
        state = read_record(root)
        active = False
        for rid, request in state["requests"].items():
            if not _live(request, now) or request["state"] in {"cancelled", "expired"}:
                continue
            active |= request["state"] in ACTIVE
            value = counts(request)
            execution = state.get("execution")
            elapsed = request.get("usage", {}).get("execution_seconds", 0)
            if (execution and rid in execution.get("sponsors", [])
                    and execution.get("state") in {"running", "committing", "stopping"}
                    and execution.get("started_at") is not None):
                elapsed += max(0, now - execution["started_at"])
            cursor = request.setdefault("notification_cursor", {"milestone": 0, "started": False})
            milestone = min(75, value["percent"] // 25 * 25)
            prior = cursor["milestone"]
            cursor["milestone"] = max(prior, milestone)
            kind = None
            if request["state"] == "running" and not cursor["started"]:
                cursor["started"] = True
                kind = "started"
            if (milestone > prior and value["processed"] < value["total"]
                    and elapsed >= legacy.NOTIFICATION_DELAY_SECONDS
                    and request["state"] in ACTIVE):
                kind = "progress"
            if kind:
                state["sequence"] += 1
                state["events"] = [e for e in state["events"]
                                   if not (e["request_id"] == rid and e["kind"] == kind)]
                state["events"].append({"event_id": f"{rid}:{state['sequence']}",
                    "request_id": rid, "kind": kind, "sequence": state["sequence"],
                    "attempts": 0, "delivered": False, "created_at": now,
                    "counts": value})
                state["events"] = state["events"][-MAX_EVENTS:]
        _save(root, state)
        # Keep the host watcher alive through bounded delivery retry leases,
        # including a completion notice after the model has already exited.
        retry_pending = any(
            not event["delivered"] and event["attempts"] < 3
            and event["request_id"] in state["requests"]
            and _live(state["requests"][event["request_id"]], now)
            and state["requests"][event["request_id"]]["state"] not in {"cancelled", "expired"}
            for event in state["events"])
        return active or retry_pending or bool(state.get("execution") and state["execution"]["state"] != "exited")


def message(event: dict[str, Any], request: dict[str, Any]) -> str | None:
    kind = event["kind"]
    value = counts(request)
    if kind == "progress":
        value = event.get("counts", value)
        return legacy._notification_message("progress", **value)
    if kind == "started":
        return f"시각 자료 확인을 시작했습니다 · {value['total']}쪽 대상. 중단하려면 Codex에 요청하세요."
    if kind == "evidence_ready":
        return legacy._notification_message("completed", **value)
    if kind == "unresolved":
        return legacy._notification_message("completed_with_uncertainty", **value)
    if kind in {"failed", "partial_failure", "version_changed"}:
        return "시각 자료 확인 중 처리하지 못한 항목이 있습니다. 저장된 결과와 상태를 확인해 주세요."
    if kind in {"paused", "document_paused", "held"}:
        return "시각 자료 확인의 중단 요청을 받았습니다. 저장된 결과는 유지됩니다."
    if kind == "budget_warning":
        return "시각 자료 확인이 안내 기준에 도달했습니다. 검토는 계속됩니다. 중단하려면 Codex에 요청하세요."
    return None


def record_watcher(root: Path, status: str, error: str | None = None) -> None:
    with control_lock(root):
        state = read_record(root)
        state["notification_watcher"] = {"state": status, "error": error, "checked_at": time.time()}
        _save(root, state)


def deliver_one(engine: Lifecycle) -> bool:
    event = engine.claim_event()
    if event is None:
        return False
    # Reload after claiming. Cancellation/expiration may have raced the claim.
    with control_lock(engine.root):
        state = read_record(engine.root)
        request = state["requests"].get(event["request_id"])
        current = next((e for e in state["events"] if e["event_id"] == event["event_id"]), None)
        if (not request or not current or not _live(request, engine.clock())
                or request["state"] in {"cancelled", "expired"}):
            return True
        if request["state"] not in ACTIVE and event["kind"] in {"started", "progress", "budget_warning"}:
            text = None
        else:
            text = message(event, request)
    try:
        if text:
            legacy._macos_notification(text)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        engine.delivered(event["event_id"], success=False)
        record_watcher(engine.root, "active", "delivery_failed")
    else:
        engine.delivered(event["event_id"], success=True)
    return True


def watch(root: Path) -> None:
    root = legacy._project_root(root)
    jobs = legacy._job_dir(root, create=False)
    if jobs is None:
        return
    descriptor = legacy._open_lock(jobs / "notifier.lock")
    acquired = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            return
        engine = Lifecycle(root)
        record_watcher(root, "active")
        idle_since = None
        while (jobs / STATE_FILE).is_file():
            active = queue_due(root)
            delivered = deliver_one(engine)
            if active or delivered:
                idle_since = None
            else:
                idle_since = idle_since or time.monotonic()
                if time.monotonic() - idle_since >= legacy.NOTIFIER_IDLE_SECONDS:
                    return
            time.sleep(legacy.NOTIFIER_POLL_SECONDS)
    finally:
        if acquired and (jobs / STATE_FILE).is_file() and (root / ".research-agent-root").is_file():
            # Patch only watcher metadata, preserving any last delivery error.
            with control_lock(root):
                state = read_record(root)
                previous = state.get("notification_watcher", {})
                state["notification_watcher"] = {"state": "idle", "error": previous.get("error"),
                                                 "checked_at": time.time()}
                _save(root, state)
        os.close(descriptor)


def launch(root: Path) -> bool:
    """Called by the host launcher; the watcher uses the existing narrow profile."""
    root = legacy._project_root(root)
    jobs = legacy._job_dir(root, create=False)
    if jobs is None or not legacy._regular(jobs / STATE_FILE, "시각 검토 상태"):
        return False
    if os.environ.get("RESEARCH_AGENT_NOTIFICATIONS") == "0":
        record_watcher(root, "disabled")
        return False
    if legacy._notifier_active(jobs):
        record_watcher(root, "active")
        return True
    descriptor = None
    try:
        descriptor = legacy._notifier_error_file(jobs)
        command = ["/usr/bin/sandbox-exec", "-D", f"RESEARCH_NOTIFY_DIR={jobs}", "-p", legacy.NOTIFIER_PROFILE]
        probe = subprocess.run([*command, "/usr/bin/true"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=legacy.NOTIFIER_READY_SECONDS, check=False)
        if probe.stderr:
            os.write(descriptor, probe.stderr[:4096])
        if probe.returncode:
            record_watcher(root, "unavailable", legacy._notifier_failure_code(probe.stderr, "sandbox_preflight_failed"))
            return False
        child = subprocess.Popen([*command, sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                                  "--root", str(root), "--watch"], cwd=root,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=descriptor,
                                 start_new_session=True, close_fds=True)
        deadline = time.monotonic() + legacy.NOTIFIER_READY_SECONDS
        while time.monotonic() < deadline:
            if legacy._notifier_active(jobs):
                record_watcher(root, "active")
                return True
            if child.poll() is not None:
                break
            time.sleep(0.1)
        record_watcher(root, "unavailable", "notifier_start_unconfirmed")
        return False
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        record_watcher(root, "unavailable", "notifier_launch_failed")
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def main() -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--root", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--launch", action="store_true")
    group.add_argument("--watch", action="store_true")
    arguments = parser.parse_args()
    if arguments.watch:
        watch(arguments.root)
    elif not launch(arguments.root) and os.environ.get("RESEARCH_AGENT_NOTIFICATIONS") != "0":
        print("안내: macOS 알림 시작을 확인하지 못했습니다. 검토는 계속되며 저장된 알림 상태를 확인할 수 있습니다.", file=sys.stderr)


if __name__ == "__main__":
    main()
