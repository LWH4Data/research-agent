"""Durable visual-review authorization, separate from the model executor.

Lock order is always control -> project storage. The document writer reads the
same record without acquiring control; callers of fenced writes already own it.
One atomic record contains transitions and their notification outbox. Committed
document/page snapshots remain the evidence authority, never this work ledger.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import time
from typing import Any, Callable, Iterator

from .locking import conversation_lock
from .safety import atomic_text, ensure_owned_directory, reject_linked_file

DIRECTORY = Path(".research-store/visual-review")
STATE_FILE = "lifecycle.json"
TERMINAL = {"cancelled", "expired", "failed", "partial_failure", "evidence_ready", "unresolved", "version_changed"}
INACTIVE = TERMINAL | {"paused", "held", "document_paused"}
MAX_EVENTS = 256
MAX_KEY_VALIDITY = 366 * 86400


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _finite(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} is out of range")
    return float(value)


@dataclass(frozen=True)
class Limits:
    execution_seconds: float | None = None
    page_attempts: int | None = None
    warning_ratio: float = 0.8
    retention_seconds: float = 30 * 86400

    def validate(self) -> None:
        if self.execution_seconds is not None:
            _finite(self.execution_seconds, "execution_seconds")
        if self.page_attempts is not None:
            if type(self.page_attempts) is not int or self.page_attempts < 0:
                raise ValueError("page_attempts must be a nonnegative integer")
        if not 0 < _finite(self.warning_ratio, "warning_ratio") < 1:
            raise ValueError("warning_ratio must be between zero and one")
        _finite(self.retention_seconds, "retention_seconds", positive=True)


@dataclass(frozen=True)
class ResultFence:
    review_id: str
    generation: int
    incarnation: str
    sha256: str
    page: int
    execution_id: str
    document_key: str

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "ResultFence":
        if not isinstance(raw, dict) or set(raw) != set(cls.__dataclass_fields__):
            raise ValueError("Incomplete visual result authority")
        if any(not isinstance(raw[k], str) or not raw[k] for k in
               ("review_id", "incarnation", "sha256", "execution_id", "document_key")):
            raise ValueError("Invalid visual result identity")
        if type(raw["generation"]) is not int or raw["generation"] < 1:
            raise ValueError("Invalid visual result generation")
        if type(raw["page"]) is not int or raw["page"] < 1:
            raise ValueError("Invalid visual result page")
        if len(raw["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in raw["sha256"]):
            raise ValueError("Invalid visual result digest")
        return cls(**raw)


def _empty() -> dict[str, Any]:
    return {"version": 2, "sequence": 0, "requests": {}, "keys": {}, "reviews": {},
            "policy": {"global_hold": False, "documents": {}}, "events": [],
            "execution": None, "library_usage": {"page_attempts": 0,
            "execution_seconds": 0.0, "tokens": None, "unknown_token_executions": 0}, "controller": None}


def read_record(root: Path) -> dict[str, Any]:
    path = reject_linked_file(root / DIRECTORY / STATE_FILE, root, label="review lifecycle")
    if not path.exists():
        return _empty()
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Review lifecycle record is too large")
    record = json.loads(path.read_text())
    if not isinstance(record, dict) or record.get("version") != 2:
        raise ValueError("Unsupported visual-review lifecycle; explicit migration required")
    return record


@contextmanager
def control_lock(root: Path) -> Iterator[None]:
    for attempt in range(3):
        try:
            folder = ensure_owned_directory(root / DIRECTORY, root, label="review lifecycle")
            break
        except FileExistsError:
            if attempt == 2:
                raise
    path = reject_linked_file(folder / "control.lock", root, label="review control lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Unsafe review control lock")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _save(root: Path, state: dict[str, Any]) -> None:
    atomic_text(root / DIRECTORY / STATE_FILE,
                json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n", root)


def _live(request: dict[str, Any], at: float) -> bool:
    return request.get("expires_at") is None or request["expires_at"] > at


def _active_links(state: dict[str, Any], review_id: str, page: int | None,
                  at: float) -> list[tuple[str, dict[str, Any]]]:
    if state["policy"]["global_hold"]:
        return []
    review = state["reviews"].get(review_id)
    if not review or state["policy"]["documents"].get(review["document_key"], {}).get("hold"):
        return []
    result = []
    for rid, request in state["requests"].items():
        link = request["links"].get(review_id)
        if (_live(request, at) and request["state"] not in {"cancelled", "expired"}
                and link and link["state"] in {"active", "queued", "running"}
                and (page is None or page in link["pages"])):
            result.append((rid, request))
    return result


def validate_result(root: Path, raw: dict[str, Any] | None, document: dict[str, Any] | None,
                    *, at: float | None = None) -> None:
    """Called immediately before durable journal prepare, under storage lock.

    Never acquires control: the fenced writer's parent owns it. Stop operations
    take control then storage, recover accepted journals, and revoke authority.
    """
    if raw is None and not (root / DIRECTORY / STATE_FILE).exists():
        return  # pre-lifecycle synchronous API; v2 never permits an unfenced write
    fence = ResultFence.parse(raw)
    at = time.time() if at is None else at
    state = read_record(root)
    review = state["reviews"].get(fence.review_id)
    execution = state["execution"]
    if not document or any(document.get(k) != getattr(fence, k) for k in
                           ("document_key", "sha256", "incarnation")):
        raise ValueError("Visual result belongs to a different document version")
    if not review or any(review.get(k) != getattr(fence, k) for k in
                         ("document_key", "sha256", "incarnation", "generation")):
        raise ValueError("Visual result authority was revoked")
    if (not execution or execution["execution_id"] != fence.execution_id
            or execution["review_id"] != fence.review_id
            or execution["generation"] != fence.generation
            or execution["state"] not in {"running", "committing"}
            or fence.page not in execution["pages"]
            ):
        raise ValueError("Visual execution is no longer authorized")
    if not _active_links(state, fence.review_id, fence.page, at):
        raise ValueError("No unexpired active request authorizes this page")


def storage_snapshot(root: Path) -> list[dict[str, Any]]:
    """Caller owns storage lock; recover only previously accepted writes."""
    from .config import load_config
    from .sync import review_snapshot_locked
    config_path = root / ".research-store/config.toml"
    if not config_path.exists():
        return []
    config = load_config(config_path)
    return review_snapshot_locked(config)


class Lifecycle:
    def __init__(self, root: Path, *, clock: Callable[[], float] = time.time,
                 snapshot: Callable[[], list[dict[str, Any]]] | None = None):
        self.root = root
        self.clock = clock
        self.snapshot = snapshot or (lambda: storage_snapshot(root))

    @contextmanager
    def transaction(self, *, reconcile: bool = True) -> Iterator[dict[str, Any]]:
        with control_lock(self.root), conversation_lock(self.root):
            self._check_legacy()
            state = read_record(self.root)
            if reconcile:
                self._reconcile(state, self.snapshot())
            yield state
            _save(self.root, state)

    def _check_legacy(self) -> None:
        if (self.root / DIRECTORY / STATE_FILE).exists():
            return
        path = reject_linked_file(self.root / DIRECTORY / "job.json", self.root,
                                  label="legacy review")
        if path.exists():
            raise ValueError("Legacy review state requires explicit migrate after confirmed worker exit")

    def _event(self, state: dict[str, Any], rid: str, kind: str) -> None:
        state["sequence"] += 1
        # Coalescing cannot fail or prevent a stop even with a full outbox.
        category = "advisory" if kind == "budget_warning" else "transition"
        state["events"] = [e for e in state["events"] if not (
            e["request_id"] == rid and e.get("category", "transition") == category)]
        state["events"].append({"event_id": f"{rid}:{state['sequence']}",
                                "request_id": rid, "kind": kind,
                                "category": category,
                                "sequence": state["sequence"], "attempts": 0,
                                "delivered": False, "created_at": self.clock()})
        state["events"] = state["events"][-MAX_EVENTS:]

    def _transition(self, state: dict[str, Any], request: dict[str, Any], status: str) -> None:
        if request["state"] == status:
            return
        request.update(state=status, updated_at=self.clock())
        if status in INACTIVE:
            request["expires_at"] = self.clock() + request["limits"]["retention_seconds"]
        elif status not in {"stopping"}:
            request["expires_at"] = None
        if status in {"cancelled", "expired"}:
            state["events"] = [e for e in state["events"] if e["request_id"] != request["request_id"]]
        else:
            self._event(state, request["request_id"], status)

    def _reconcile(self, state: dict[str, Any], documents: list[dict[str, Any]]) -> None:
        at = self.clock()
        current = {row["document_key"]: row for row in documents}
        for request in state["requests"].values():
            if not _live(request, at) and request["state"] != "expired":
                for link in request["links"].values():
                    link["state"] = "expired"
                self._transition(state, request, "expired")
                request["expires_at"] = at  # lookup must not extend expired retention
            if request["state"] in {"cancelled", "expired"}:
                continue
            for review_id, link in request["links"].items():
                review = state["reviews"].get(review_id)
                if not review:
                    continue
                doc = current.get(review["document_key"])
                if not doc or any(doc.get(k) != review[k] for k in ("sha256", "incarnation")):
                    link["state"] = "version_changed"
                    link["outcomes"] = {}
                    continue
                outcomes = {str(p): doc.get("pages", {}).get(str(p), "unknown") for p in link["pages"]}
                if link.get("rereview"):
                    fences = doc.get("page_fences", {})
                    for page in link["pages"]:
                        name = str(page)
                        if page in link.get("rereview_pages", []) and fences.get(name) == link["baseline_fences"].get(name):
                            outcomes[name] = "pending"
                link["outcomes"] = outcomes
                if link["state"] == "evidence_ready" and any(s != "verified" for s in outcomes.values()):
                    link["state"] = "failed"
                    link["error"] = "Committed evidence is no longer available"
                if link["state"] in INACTIVE:
                    continue
                if outcomes and all(s in {"verified", "needs_review"} for s in outcomes.values()):
                    link["state"] = "unresolved" if "needs_review" in outcomes.values() else "evidence_ready"
            self._derive(state, request)
        execution = state["execution"]
        if execution and execution["state"] not in {"exited", "stopping"}:
            if not any(_active_links(state, execution["review_id"], p, at) for p in execution["pages"]):
                execution["state"] = "stopping"

    def _derive(self, state: dict[str, Any], request: dict[str, Any]) -> None:
        links = list(request["links"].values())
        states = {l["state"] for l in links}
        if request.get("paused"):
            self._transition(state, request, "paused")
            return
        pending_intake = any(i.get("state") == "pending" for i in request["items"].values())
        if pending_intake and states <= TERMINAL:
            status = "intake"
        elif not links:
            item_states = {i.get("state") for i in request["items"].values()}
            status = ("failed" if item_states and item_states <= {"failed"}
                      else "evidence_ready" if item_states and item_states <= {"complete"}
                      else "partial_failure" if item_states and item_states <= {"complete", "failed"}
                      else "intake")
        elif states <= {"evidence_ready"}:
            status = "partial_failure" if any(i.get("state") == "failed" for i in request["items"].values()) else "evidence_ready"
        elif states <= TERMINAL:
            status = "unresolved" if "unresolved" in states else "failed"
        elif states <= INACTIVE:
            status = "paused"
        elif "running" in states:
            status = "running"
        else:
            status = "held" if state["policy"]["global_hold"] else "queued"
        self._transition(state, request, status)

    def _receipt(self, state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        receipt = json.loads(json.dumps(request))
        receipt.pop("spec", None)
        receipt.pop("key_hash", None)
        receipt.pop("spec_hash", None)
        receipt["global_hold"] = state["policy"]["global_hold"]
        receipt["evidence_lookup"] = {"command": "research-review status", "request_id": request["request_id"]}
        receipt["answered"] = False
        receipt["token_usage"] = request.get("token_usage")
        receipt["token_measurement_scope"] = "sponsored_calls_only; shared library totals counted once; no plan quota conversion"
        receipt["notification_watcher"] = state.get("notification_watcher")
        receipt["usage_policy"] = "advisory_only_user_decides_stopping"
        execution = state["execution"]
        if (execution and execution["review_id"] in request["links"] and execution["state"] == "stopping"
                and request["state"] in {"paused", "cancelled", "expired", "held"}):
            receipt["requested_state"] = receipt["state"]
            receipt["state"] = "stopping"
            receipt["process_exit_confirmed"] = False
        receipt["remaining"] = {
            "page_attempts": None if request["limits"]["page_attempts"] is None else max(
                0, request["limits"]["page_attempts"] - request["usage"]["page_attempts"]),
            "execution_seconds": None if request["limits"]["execution_seconds"] is None else max(
                0, request["limits"]["execution_seconds"] - request["usage"]["execution_seconds"])}
        return receipt

    def begin(self, key: str, key_expires_at: float, specification: dict[str, Any],
              *, limits: Limits | None = None, origin: dict[str, str] | None = None) -> dict[str, Any]:
        limits = limits or Limits()
        limits.validate()
        at = self.clock()
        _finite(key_expires_at, "key_expires_at", positive=True)
        envelope = re.fullmatch(r"vr2\.([0-9]{10,13})\.([A-Za-z0-9_-]{16,128})", key) if isinstance(key, str) else None
        if not envelope or int(envelope[1]) != key_expires_at:
            raise ValueError("Use a caller-persisted vr2.<expiry-epoch>.<random-key> with its immutable expiry")
        if key_expires_at <= at or key_expires_at > at + MAX_KEY_VALIDITY:
            raise ValueError("Intake key expired or validity exceeds one year")
        if not isinstance(specification, dict) or not isinstance(specification.get("items"), list) or not specification["items"]:
            raise ValueError("Exact intake items are required")
        if not all(isinstance(i, dict) for i in specification["items"]):
            raise ValueError("Each intake item must be an object")
        item_ids = [i.get("item_id") for i in specification["items"]]
        if any(not isinstance(i, str) or not i for i in item_ids) or len(set(item_ids)) != len(item_ids):
            raise ValueError("Intake items require unique item_id values")
        allowed = {"item_id", "attachment", "document_key", "source_id", "sha256", "incarnation", "pages", "rereview"}
        if set(specification) != {"items"}:
            raise ValueError("Intake metadata contains unsupported fields")
        for item in specification["items"]:
            if set(item) - allowed or sum(k in item for k in ("attachment", "document_key", "source_id")) != 1:
                raise ValueError("Each intake item needs exactly one attachment, document_key, or source_id")
            for field in ("item_id", "attachment", "document_key", "source_id", "sha256", "incarnation"):
                if field in item and (not isinstance(item[field], str) or not item[field] or len(item[field]) > 4096):
                    raise ValueError(f"Invalid intake {field}")
            if "pages" in item and (not isinstance(item["pages"], list) or any(type(p) is not int or p < 1 for p in item["pages"])):
                raise ValueError("Intake pages must be positive integers")
            if "rereview" in item and type(item["rereview"]) is not bool:
                raise ValueError("rereview must be a boolean")
        if origin and (set(origin) - {"task_id", "message_id"} or any(not isinstance(v, str) for v in origin.values())):
            raise ValueError("Origin metadata accepts task_id/message_id only")
        spec = {"scope": specification, "limits": asdict(limits), "origin": origin or {}, "key_expires_at": key_expires_at}
        khash, shash = _digest(key), _digest(spec)
        with self.transaction() as state:
            existing = state["keys"].get(khash)
            if existing:
                if existing.get("denied") or existing["request_id"] not in state["requests"]:
                    raise ValueError("This intake key was deleted or expired; it cannot create new work")
                if existing["spec_hash"] != shash:
                    raise ValueError("Idempotency key conflicts with the original intake specification")
                return self._receipt(state, self._get(state, existing["request_id"], terminal=True))
            rid = secrets.token_hex(16)
            versions = {d["document_key"]: {k: d[k] for k in ("document_key", "sha256", "incarnation")}
                        for d in self.snapshot()}
            request = {"request_id": rid, "state": "intake", "key_hash": khash,
                       "spec_hash": shash, "spec": specification, "origin": origin or {},
                       "created_at": at, "updated_at": at, "expires_at": None,
                       "key_expires_at": key_expires_at, "limits": asdict(limits),
                       "usage": {"page_attempts": 0, "execution_seconds": 0.0},
                       "input_versions": {i["item_id"]: versions.get(i["document_key"])
                                          for i in specification["items"] if "document_key" in i},
                       "links": {}, "items": {i: {"state": "pending"} for i in item_ids}}
            state["requests"][rid] = request
            state["keys"][khash] = {"request_id": rid, "spec_hash": shash, "expires_at": key_expires_at}
            self._event(state, rid, "intake")
            return self._receipt(state, request)

    def attach(self, request_id: str, item_id: str, document: dict[str, Any] | None,
               *, error: str | None = None, explicit: bool = True,
               parent_item_id: str | None = None) -> dict[str, Any]:
        with self.transaction() as state:
            request = self._get(state, request_id)
            if item_id not in request["items"]:
                parent = next((i for i in request["spec"]["items"] if i["item_id"] == parent_item_id), None)
                if (not parent or "source_id" not in parent or document is None
                        or item_id != parent_item_id + "#" + hashlib.sha256(document["document_key"].encode()).hexdigest()
                        or not document["document_key"].startswith(parent["source_id"] + ":")):
                    raise ValueError("Item is outside the recorded intake")
                request["items"][item_id] = {"state": "pending", "parent_item_id": parent_item_id}
            item = request["items"][item_id]
            if item["state"] == "linked":
                return self._receipt(state, request)
            if error is not None:
                item.update(state="failed", error=error[:500])
            else:
                assert document is not None
                for name in ("document_key", "sha256", "incarnation"):
                    if not isinstance(document.get(name), str) or not document[name]:
                        raise ValueError(f"Committed document {name} is required")
                intent = next(i for i in request["spec"]["items"] if i["item_id"] == (parent_item_id or item_id))
                if "document_key" in intent:
                    frozen = request.get("input_versions", {}).get(item_id)
                    if not frozen or any(frozen[n] != document[n] for n in ("document_key", "sha256", "incarnation")):
                        raise ValueError("Requested stored document version changed since intake")
                for name in ("document_key", "sha256", "incarnation"):
                    if name in intent and intent[name] != document[name]:
                        raise ValueError("Committed item differs from the authorized input version")
                selected = intent.get("pages")
                pages = sorted(int(p) for p in document["pages"]) if selected is None else selected
                if any(type(p) is not int or p < 1 or str(p) not in document["pages"] for p in pages):
                    raise ValueError("Requested pages are not committed review candidates")
                review = next((r for r in state["reviews"].values() if all(
                    r[n] == document[n] for n in ("document_key", "sha256", "incarnation"))), None)
                if review is None:
                    review = {"review_id": secrets.token_hex(16), "generation": 1,
                              **{n: document[n] for n in ("document_key", "sha256", "incarnation")},
                              "created_at": self.clock(), "turn": state["sequence"]}
                    state["reviews"][review["review_id"]] = review
                policy = state["policy"]["documents"].setdefault(document["document_key"], {})
                if explicit:
                    policy["hold"] = False
                held = policy.get("hold") or (policy.get("automatic_suppressed") and not explicit)
                prior = request["links"].get(review["review_id"])
                previous_pages = prior["pages"] if prior else []
                rereview_pages = set(prior.get("rereview_pages", [])) if prior else set()
                if intent.get("rereview") is True:
                    rereview_pages.update(pages)
                baseline = dict(prior.get("baseline_fences", {})) if prior else {}
                baseline.update({str(p): document.get("page_fences", {}).get(str(p)) for p in pages if p in rereview_pages})
                prior_state = prior["state"] if prior else "active"
                if prior_state in {"evidence_ready", "unresolved"} and set(pages) - set(previous_pages):
                    prior_state = "active"
                request["links"][review["review_id"]] = {"pages": sorted(set(pages) | set(previous_pages)),
                    "state": "paused" if request.get("paused") else "document_paused" if held else prior_state,
                    "outcomes": prior.get("outcomes", {}) if prior else {},
                    "rereview": bool(rereview_pages), "rereview_pages": sorted(rereview_pages),
                    "baseline_fences": baseline}
                item.update(state="linked", review_id=review["review_id"],
                            document_key=document["document_key"], sha256=document["sha256"],
                            incarnation=document["incarnation"])
                if not pages:
                    request["links"][review["review_id"]]["state"] = "evidence_ready"
            self._reconcile(state, self.snapshot())
            return self._receipt(state, request)

    def _get(self, state: dict[str, Any], rid: str, *, terminal: bool = False) -> dict[str, Any]:
        request = state["requests"].get(rid)
        if not request or not _live(request, self.clock()) or request["state"] == "expired":
            raise ValueError("Request expired or invalid")
        if not terminal and request["state"] == "cancelled":
            raise ValueError("Request was cancelled")
        return request

    def status(self, request_id: str | None = None) -> dict[str, Any]:
        with self.transaction() as state:
            if request_id:
                return self._receipt(state, self._get(state, request_id, terminal=True))
            return {"version": 2, "global_hold": state["policy"]["global_hold"],
                    "requests": [self._receipt(state, r) for r in state["requests"].values()
                                 if r["state"] != "expired"],
                    "execution": state["execution"], "library_usage": state["library_usage"],
                    "notification_watcher": state.get("notification_watcher")}

    def control(self, action: str, *, request_id: str | None = None,
                document_key: str | None = None, library: bool = False) -> dict[str, Any]:
        if sum((request_id is not None, document_key is not None, library)) != 1:
            raise ValueError("Choose exactly one request, document, or library scope")
        if action not in {"pause", "cancel", "resume"}:
            raise ValueError("Unknown lifecycle control")
        with self.transaction() as state:
            if library:
                state["policy"]["global_hold"] = action != "resume"
            if document_key is not None:
                policy = state["policy"]["documents"].setdefault(document_key, {})
                policy["hold"] = action != "resume"
                if action == "cancel":
                    policy["automatic_suppressed"] = True
            selected = [self._get(state, request_id, terminal=action != "resume")] if request_id else list(state["requests"].values())
            for request in selected:
                if request["state"] in {"cancelled", "expired"}:
                    continue
                if request_id and action == "resume":
                    request["paused"] = False
                elif request_id and action == "pause":
                    request["paused"] = True
                for review_id, link in request["links"].items():
                    if document_key and state["reviews"][review_id]["document_key"] != document_key:
                        continue
                    if library:
                        continue  # persistent hold never rewrites independent link decisions
                    if action == "resume":
                        if link["state"] in {"cancelled", "expired", "version_changed", "evidence_ready", "unresolved"}:
                            continue
                        if request_id or link["state"] == "document_paused":
                            link["state"] = "active"
                    elif link["state"] not in {"evidence_ready", "unresolved", "version_changed"}:
                        link["state"] = "cancelled" if action == "cancel" else ("document_paused" if document_key else "paused")
                if request_id and action == "cancel":
                    self._transition(state, request, "cancelled")
                else:
                    self._derive(state, request)
            execution = state["execution"]
            if execution and execution["state"] != "exited":
                active = any(_active_links(state, execution["review_id"], p, self.clock()) for p in execution["pages"])
                if not active:
                    execution["state"] = "stopping"
                    state["reviews"][execution["review_id"]]["generation"] += 1
            stopping = bool(execution and execution["state"] == "stopping")
            return {"action": action, "state": "stopping" if stopping else "applied",
                    "global_hold": state["policy"]["global_hold"],
                    "request": self._receipt(state, selected[0]) if request_id else None,
                    "process_exit_confirmed": not stopping}

    def reserve(self, *, max_pages: int = 4, on_idle: Callable[[], None] | None = None) -> dict[str, Any] | None:
        with self.transaction() as state:
            if state["execution"] is not None or state["policy"]["global_hold"]:
                if on_idle:
                    on_idle()
                return None  # exit, commit reconciliation and artifact cleanup must finish first
            for review in sorted(state["reviews"].values(), key=lambda r: (r["turn"], r["created_at"])):
                links = _active_links(state, review["review_id"], None, self.clock())
                pages = sorted({p for _, r in links for p in r["links"][review["review_id"]]["pages"]
                                if r["links"][review["review_id"]]["outcomes"].get(str(p)) == "pending"})
                if not pages:
                    continue
                sponsors = {rid: r for rid, r in links if any(p in r["links"][review["review_id"]]["pages"] for p in pages[:max_pages])}
                pages = pages[:max_pages]
                if not pages:
                    continue
                sponsors = {rid: r for rid, r in sponsors.items() if set(pages) & set(r["links"][review["review_id"]]["pages"])}
                remaining = [r["limits"]["execution_seconds"] - r["usage"]["execution_seconds"]
                             for r in sponsors.values() if r["limits"]["execution_seconds"] is not None]
                budget = max(0.0, min(remaining)) if remaining else None
                execution = {"execution_id": secrets.token_hex(16), "review_id": review["review_id"],
                    "generation": review["generation"], "document_key": review["document_key"],
                    "incarnation": review["incarnation"], "sha256": review["sha256"],
                    "pages": pages, "sponsors": list(sponsors), "state": "reserved",
                    "reserved_at": self.clock(), "started_at": None, "deadline": None,
                    "seconds_allowance": budget, "warning_ratio": min(r["limits"]["warning_ratio"] for r in sponsors.values()),
                    "warning_sent": False, "owner": None, "artifacts": [], "tokens": None}
                for request in sponsors.values():
                    request["usage"]["page_attempts"] += len(set(pages) & set(request["links"][review["review_id"]]["pages"]))
                    if (request["limits"]["page_attempts"] is not None and request["usage"]["page_attempts"] >=
                            request["limits"]["page_attempts"] * request["limits"]["warning_ratio"]):
                        self._event(state, request["request_id"], "budget_warning")
                state["library_usage"]["page_attempts"] += len(pages)
                state["execution"] = execution
                review["turn"] = state["sequence"] + 1
                state["sequence"] += 1
                return json.loads(json.dumps(execution))
            if on_idle:
                on_idle()
            return None

    def acknowledge(self, execution_id: str, owner: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as state:
            execution = self._execution(state, execution_id)
            if execution["state"] != "reserved":
                raise ValueError("Execution handoff is no longer authorized")
            execution.update(state="running", owner=owner, started_at=self.clock())
            if execution["seconds_allowance"] is not None:
                execution["deadline"] = self.clock() + execution["seconds_allowance"]
            for rid in execution["sponsors"]:
                request = state["requests"].get(rid)
                if request and request["links"][execution["review_id"]]["state"] == "active":
                    request["links"][execution["review_id"]]["state"] = "running"
                    self._derive(state, request)
            return json.loads(json.dumps(execution))

    @staticmethod
    def _execution(state: dict[str, Any], eid: str) -> dict[str, Any]:
        execution = state["execution"]
        if not execution or execution["execution_id"] != eid:
            raise ValueError("Execution identity is no longer current")
        return execution

    def check_execution(self, execution_id: str) -> dict[str, Any]:
        with self.transaction() as state:
            execution = self._execution(state, execution_id)
            deadline = execution.get("deadline")
            if deadline is not None:
                duration = self.clock() - execution["started_at"]
                if duration >= execution["seconds_allowance"] * execution["warning_ratio"] and not execution["warning_sent"]:
                    execution["warning_sent"] = True
                    for rid in execution["sponsors"]:
                        if rid in state["requests"] and _live(state["requests"][rid], self.clock()):
                            self._event(state, rid, "budget_warning")
                # Advisory threshold only: the user decides whether to stop.
            return json.loads(json.dumps(execution))

    def finish(self, execution_id: str, *, error: str | None = None,
               tokens: dict[str, int] | None = None) -> None:
        """Only after owned descendants have exited and accepted writes reconciled."""
        with self.transaction() as state:
            execution = self._execution(state, execution_id)
            elapsed = 0.0 if execution["started_at"] is None else max(0.0, self.clock() - execution["started_at"])
            state["library_usage"]["execution_seconds"] += elapsed
            if tokens is not None:
                totals = state["library_usage"]["tokens"] or {}
                for field, count in tokens.items():
                    totals[field] = totals.get(field, 0) + count
                state["library_usage"]["tokens"] = totals
            else:
                state["library_usage"]["unknown_token_executions"] = state["library_usage"].get("unknown_token_executions", 0) + 1
            for rid in execution["sponsors"]:
                request = state["requests"].get(rid)
                if request:
                    request["usage"]["execution_seconds"] += elapsed
                    if tokens is not None:
                        measured = request.setdefault("token_usage", {})
                        for field, count in tokens.items():
                            measured[field] = measured.get(field, 0) + count
                    else:
                        request["unknown_token_executions"] = request.get("unknown_token_executions", 0) + 1

            for request in state["requests"].values():
                link = request["links"].get(execution["review_id"])
                if link and link["state"] in {"active", "queued", "running"}:
                    link["state"] = "failed" if error else "active"
                    if error:
                        link["error"] = error[:500]
                    self._derive(state, request)
            execution.update(state="exited", ended_at=self.clock(), error=error, tokens=tokens)

    def release_execution(self, execution_id: str) -> None:
        with self.transaction() as state:
            execution = self._execution(state, execution_id)
            if execution["state"] != "exited" or execution["artifacts"]:
                raise ValueError("Execution exit and owned artifact cleanup are not confirmed")
            state["execution"] = None

    def claim_event(self) -> dict[str, Any] | None:
        # The notification-only process may write this directory, not document
        # state. Never enter transaction(), which reconciles storage journals.
        with control_lock(self.root):
            state = read_record(self.root)
            for event in state["events"]:
                request = state["requests"].get(event["request_id"])
                if (not request or not _live(request, self.clock())
                        or request["state"] in {"cancelled", "expired"}
                        or event["delivered"] or event["attempts"] >= 3
                        or event.get("claimed_until", 0) > self.clock()):
                    continue
                event["attempts"] += 1
                event["claimed_until"] = self.clock() + 30
                _save(self.root, state)
                return dict(event)
            return None

    def delivered(self, event_id: str, *, success: bool) -> None:
        # Reload and patch only one event. An OS send is not an acknowledgement.
        with control_lock(self.root):
            state = read_record(self.root)
            for event in state["events"]:
                if event["event_id"] == event_id:
                    event["delivered"] = success
                    event["claimed_until"] = self.clock() + (0 if success else 30)
            _save(self.root, state)

    def cleanup(self) -> dict[str, Any]:
        with self.transaction() as state:
            at = self.clock()
            removed = []
            execution = state["execution"]
            for rid, request in list(state["requests"].items()):
                if _live(request, at):
                    continue
                # Keep identity/accounting until the attempt and accepted writes end.
                if execution and execution["state"] != "exited" and (rid in execution["sponsors"] or execution["review_id"] in request["links"]):
                    continue
                khash = request["key_hash"]
                state["keys"][khash] = {"denied": True, "expires_at": request["key_expires_at"]}
                del state["requests"][rid]
                config_path = self.root / ".research-store/config.toml"
                if config_path.exists():
                    from .config import load_config
                    from .sync import delete_intake_receipts_locked
                    delete_intake_receipts_locked(load_config(config_path), rid)
                state["events"] = [e for e in state["events"] if e["request_id"] != rid]
                removed.append(rid)
            state["keys"] = {k: v for k, v in state["keys"].items() if v["expires_at"] > at}
            referenced = {key for r in state["requests"].values() for key in r["links"]}
            if execution:
                referenced.add(execution["review_id"])
            state["reviews"] = {k: v for k, v in state["reviews"].items() if k in referenced}
            return {"removed_requests": removed, "cleanup_pending": bool(execution and execution["state"] != "exited")}

    def forget(self, request_id: str) -> None:
        self.control("cancel", request_id=request_id)
        with self.transaction() as state:
            request = state["requests"][request_id]
            request["expires_at"] = self.clock()
        self.cleanup()

    def delete_document(self, document_key: str) -> dict[str, Any]:
        self.control("cancel", document_key=document_key)
        with self.transaction() as state:
            execution = state["execution"]
            if execution and execution["document_key"] == document_key:
                return {"document_key": document_key, "deleted": False,
                        "state": "stopping", "cleanup_pending": True}
            from .config import load_config
            from .sync import delete_document_locked, delete_intake_receipts_locked, intake_receipts_locked
            config = load_config(self.root / ".research-store/config.toml")
            # A crash after text commit can leave the lifecycle item pending.
            # Durable storage receipts, not only already-created links, revoke
            # that exact item before document deletion removes those receipts.
            committed_items = {rid: {r["item_id"] for r in intake_receipts_locked(config, rid)
                                     if r["document_key"] == document_key}
                               for rid in state["requests"]}
            review_ids = {k for k, r in state["reviews"].items() if r["document_key"] == document_key}
            forgotten = []
            for rid, request in list(state["requests"].items()):
                request["links"] = {k: v for k, v in request["links"].items() if k not in review_ids}
                request["items"] = {k: ({"state": "deleted"} if v.get("document_key") == document_key
                                       or k in committed_items[rid] else v)
                                    for k, v in request["items"].items()}
                if not request["links"] and all(i["state"] == "deleted" for i in request["items"].values()):
                    state["keys"][request["key_hash"]] = {"denied": True, "expires_at": request["key_expires_at"]}
                    state["events"] = [e for e in state["events"] if e["request_id"] != rid]
                    forgotten.append(rid)
                    del state["requests"][rid]
            state["reviews"] = {k: v for k, v in state["reviews"].items() if k not in review_ids}
            # Persist denial before storage deletion removes the durable item
            # receipts. A crash at either side cannot revive a stale prepared
            # attachment transfer or accept an old document's visual result.
            _save(self.root, state)
            result = delete_document_locked(config, document_key)
            for rid in forgotten:
                delete_intake_receipts_locked(config, rid)
            return result
