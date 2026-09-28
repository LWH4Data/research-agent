#!/usr/bin/env python3
"""Constrained entry point for request-scoped review and owned supervision."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import errno
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

# Public launchers use -I -S; only these installation-owned code paths are loaded.
SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT / "src"))
from research_store.review_lifecycle import (DIRECTORY, Lifecycle, Limits, ResultFence,
    _active_links, _save, control_lock, read_record, storage_snapshot)
from research_store.locking import conversation_lock
from research_store.safety import reject_linked_file, unlink_owned_file

spec = importlib.util.spec_from_file_location("review_utilities", SOURCE_ROOT / "scripts/background_review.py")
assert spec and spec.loader
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


def _lock(root: Path, name: str) -> int | None:
    jobs = legacy._job_dir(root, create=True)
    fd = legacy._open_lock(jobs / name)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def _validate_fd(root: Path, fd: int, name: str) -> None:
    info = os.fstat(fd)
    current = (root / DIRECTORY / name).stat(follow_symlinks=False)
    if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
        raise ValueError("Owned execution lock identity changed")


class ProcessInspectionError(RuntimeError):
    """Ownership is unknown, which must never be interpreted as process exit."""


class _DarwinProcBsdInfo(ctypes.Structure):
    # SDK sys/proc_info.h: proc_bsdinfo. Fixed-width fields give the same offsets
    # on 32- and 64-bit ABIs; c_long/time_t would change the layout on LP64.
    _fields_ = [
        ("pbi_flags", ctypes.c_uint32), ("pbi_status", ctypes.c_uint32),
        ("pbi_xstatus", ctypes.c_uint32), ("pbi_pid", ctypes.c_uint32),
        ("pbi_ppid", ctypes.c_uint32), ("pbi_uid", ctypes.c_uint32),
        ("pbi_gid", ctypes.c_uint32), ("pbi_ruid", ctypes.c_uint32),
        ("pbi_rgid", ctypes.c_uint32), ("pbi_svuid", ctypes.c_uint32),
        ("pbi_svgid", ctypes.c_uint32), ("rfu_1", ctypes.c_uint32),
        ("pbi_comm", ctypes.c_char * 16), ("pbi_name", ctypes.c_char * 32),
        ("pbi_nfiles", ctypes.c_uint32), ("pbi_pgid", ctypes.c_uint32),
        ("pbi_pjobc", ctypes.c_uint32), ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32), ("pbi_nice", ctypes.c_int32),
        ("pbi_start_tvsec", ctypes.c_uint64), ("pbi_start_tvusec", ctypes.c_uint64),
    ]


def _darwin_process_identity(pid: int) -> dict[str, Any] | None:
    size = ctypes.sizeof(_DarwinProcBsdInfo)
    if (size != 136 or _DarwinProcBsdInfo.pbi_pid.offset != 12
            or _DarwinProcBsdInfo.pbi_pgid.offset != 100
            or _DarwinProcBsdInfo.pbi_start_tvsec.offset != 120
            or _DarwinProcBsdInfo.pbi_start_tvusec.offset != 128):
        raise ProcessInspectionError("Darwin process identity ABI is unsupported")
    try:
        # Direct libproc calls retain this sandbox's process-info boundary.
        # macOS /bin/ps is setuid and its execution can be denied by the sandbox.
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        inspect = library.proc_pidinfo
        inspect.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                           ctypes.c_void_p, ctypes.c_int]
        inspect.restype = ctypes.c_int
        info = _DarwinProcBsdInfo()
        ctypes.set_errno(0)
        returned = inspect(pid, 3, 0, ctypes.byref(info), size)  # PROC_PIDTBSDINFO
        error = ctypes.get_errno()
    except (OSError, AttributeError, ctypes.ArgumentError) as exc:
        raise ProcessInspectionError("Darwin process identity API is unavailable") from exc
    if returned <= 0:
        if error == errno.ESRCH:
            return None
        if error in (errno.EPERM, errno.EACCES):
            raise ProcessInspectionError("Darwin process identity inspection was denied")
        raise ProcessInspectionError(f"Darwin process identity lookup failed (errno {error})")
    if returned != size:
        raise ProcessInspectionError("Darwin process identity record is incomplete or incompatible")
    if info.pbi_pid != pid:
        raise ProcessInspectionError("Darwin process identity PID did not match")
    if info.pbi_status == 5:  # SZOMB, sys/proc.h: exited, awaiting collection
        return None
    if (info.pbi_status not in (1, 2, 3, 4) or not 0 < info.pbi_pgid <= 0x7fffffff
            or info.pbi_start_tvsec == 0 or info.pbi_start_tvusec >= 1_000_000):
        raise ProcessInspectionError("Darwin process identity record is invalid")
    return {"pid": pid, "group": info.pbi_pgid,
            "birth": f"darwin:{info.pbi_start_tvsec}.{info.pbi_start_tvusec:06d}"}


def process_identity(pid: int) -> dict[str, Any] | None:
    """PID alone never authorizes a signal. None means confirmed absent/zombie."""
    if type(pid) is not int or not 0 < pid <= 0x7fffffff:
        raise ProcessInspectionError("Process identity requires a valid positive PID")
    if sys.platform == "darwin":
        return _darwin_process_identity(pid)
    try:
        if Path("/proc").is_dir():
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            if fields[0] == "Z":
                return None
            group, birth = int(fields[2]), fields[19]
            if group <= 0 or not birth.isdecimal() or int(birth) <= 0:
                raise ValueError("Invalid process identity")
            return {"pid": pid, "group": group, "birth": birth}
        output = subprocess.check_output(["/bin/ps", "-p", str(pid), "-o", "pgid=,lstart="],
            text=True, stderr=subprocess.PIPE).strip().split(None, 1)
        if len(output) != 2 or int(output[0]) <= 0:
            raise ValueError("Incomplete process identity")
        return {"pid": pid, "group": int(output[0]), "birth": output[1]}
    except (FileNotFoundError, ProcessLookupError) as exc:
        # A missing ps executable is an inspection failure, not a missing PID.
        if Path("/proc").is_dir():
            return None
        raise ProcessInspectionError("Process identity inspection is unavailable") from exc
    except (OSError, ValueError, IndexError, subprocess.SubprocessError) as exc:
        # On unsupported platforms ps has no portable absent/denied exit code.
        # Confirm absence independently before returning the exit sentinel.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None
        except OSError:
            pass
        raise ProcessInspectionError("Process identity inspection failed or was denied") from exc


def _group_alive(group: int) -> bool:
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def stop_owned(child: subprocess.Popen, identity: dict[str, Any]) -> bool:
    """Only this live supervisor's child with an unchanged birth/group is signalled."""
    if child.poll() is not None:
        return not _group_alive(identity["group"])
    try:
        if process_identity(child.pid) != identity or identity["group"] != child.pid:
            return False
    except ProcessInspectionError:
        return False
    for sig, interval in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(identity["group"], sig)
        except ProcessLookupError:
            return True
        until = time.monotonic() + interval
        while time.monotonic() < until:
            child.poll()
            if not _group_alive(identity["group"]):
                return True
            time.sleep(0.05)
        # Never signal a reused leader identity.
        try:
            current = process_identity(child.pid)
        except ProcessInspectionError:
            return False
        if current is not None and current != identity:
            return False
    return not _group_alive(identity["group"])


def _owned_artifact(path: Path, root: Path) -> dict[str, Any]:
    reject_linked_file(path, root, label="execution artifact")
    info = path.stat(follow_symlinks=False)
    return {"path": str(path.relative_to(root)), "device": info.st_dev, "inode": info.st_ino}


def _record_artifacts(engine: Lifecycle, eid: str, paths: list[Path]) -> None:
    with engine.transaction() as state:
        execution = engine._execution(state, eid)
        execution["artifacts"].extend(_owned_artifact(p, engine.root) for p in paths)


def _cleanup_artifacts(engine: Lifecycle, eid: str) -> None:
    with engine.transaction() as state:
        execution = engine._execution(state, eid)
        if execution["state"] != "exited":
            raise ValueError("Cannot remove temporary files while process exit is unconfirmed")
        manifest_path = execution.get("render_manifest")
        owned_directory = None
        manifest_identity = None
        if manifest_path:
            manifest = engine.root / manifest_path
            reject_linked_file(manifest, engine.root, label="render ownership manifest")
            if manifest.exists():
                manifest_identity = _owned_artifact(manifest, engine.root)
                ownership = json.loads(manifest.read_text())
                owned_directory = ownership["directory"]
                directory = engine.root / owned_directory["path"]
                if (ownership.get("execution_id") != eid or directory != manifest.parent
                        or directory.name != f"render-{eid}" or directory.is_symlink()):
                    raise ValueError("Render ownership manifest does not match this execution")
                info = directory.stat(follow_symlinks=False)
                if (info.st_dev, info.st_ino) != (owned_directory["device"], owned_directory["inode"]):
                    raise ValueError("Render directory was replaced; cleanup requires attention")
                known = {a["path"] for a in execution["artifacts"]}
                for owned in ownership["files"]:
                    path = engine.root / owned["path"]
                    if path.parent != directory or path.name not in {f"page-{p:04d}.png" for p in execution["pages"]}:
                        raise ValueError("Render manifest contains an out-of-scope file")
                    if owned["path"] not in known:
                        execution["artifacts"].append(owned)
        remaining = []
        for owned in execution["artifacts"]:
            path = engine.root / owned["path"]
            try:
                reject_linked_file(path, engine.root, label="execution artifact")
                if not path.exists():
                    continue
                current = path.stat(follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (owned["device"], owned["inode"]):
                    remaining.append(owned)
                    continue
                unlink_owned_file(path, engine.root, label="execution artifact")
            except (OSError, ValueError):
                remaining.append(owned)
        execution["artifacts"] = remaining
        if not remaining and owned_directory and manifest_identity:
            manifest = engine.root / manifest_path
            info = manifest.stat(follow_symlinks=False)
            if (info.st_dev, info.st_ino) != (manifest_identity["device"], manifest_identity["inode"]):
                raise ValueError("Render manifest was replaced during cleanup")
            unlink_owned_file(manifest, engine.root, label="render ownership manifest")
            (engine.root / owned_directory["path"]).rmdir()
            execution.pop("render_manifest", None)


def _model(engine: Lifecycle, execution: dict[str, Any], codex: Path, workdir: Path,
           lock_fd: int) -> None:
    root, eid = engine.root, execution["execution_id"]
    jobs = root / DIRECTORY
    queue = legacy._review_queue(root)
    batch = [row for row in queue if row["document_key"] == execution["document_key"]
             and row["page_number"] in execution["pages"]]
    if len(batch) != len(execution["pages"]):
        snapshots = legacy._store(root, "review-snapshot")
        doc = next((row for row in snapshots if all(row.get(k) == execution[k] for k in
                    ("document_key", "sha256", "incarnation"))), None)
        if not doc or any(str(p) not in doc["pages"] for p in execution["pages"]):
            raise ValueError("Reserved page scope changed before rendering")
        # Explicit rereview may render a previously verified candidate.
        batch = [{"document_key": execution["document_key"], "page_number": p,
                  "source_id": execution["document_key"].split(":", 1)[0],
                  "output_path": doc["output_path"], "reasons": []} for p in execution["pages"]]
    source, old_names = legacy._render_source_directory(root, batch)
    with engine.transaction() as state:
        engine._execution(state, eid)["render_manifest"] = str(
            (source / f"render-{eid}" / "owned-manifest.json").relative_to(root))
    arguments = ["render-review", execution["document_key"], "--execution-id", eid]
    for page in execution["pages"]:
        arguments.extend(["--page", str(page)])
    rendered = legacy._store(root, *arguments)
    if rendered.get("sha256") != execution["sha256"]:
        raise ValueError("Document changed before model execution")
    images = [Path(p) for p in rendered["rendered"]]
    output, identities, source_identity, output_identity = legacy._validate_rendered_images(
        root, source, old_names, images, execution["pages"])
    _record_artifacts(engine, eid, images)
    schema = jobs / f"schema-{eid}.json"
    answer = jobs / f"answer-{eid}.json"
    events = jobs / f"events-{eid}.jsonl"
    errors = jobs / f"errors-{eid}.log"
    prompt_path = jobs / f"prompt-{eid}.txt"
    legacy._atomic_json(schema, legacy.RESPONSE_SCHEMA)
    base = legacy._read_base_pages(root, batch[0], execution["pages"], execution["sha256"])
    prompt = legacy._prompt(execution["pages"], {row["page_number"]: row.get("reasons", []) for row in batch}, base)
    from research_store.safety import atomic_text
    for path, text in ((answer, ""), (events, ""), (errors, ""), (prompt_path, prompt)):
        atomic_text(path, text, root)
    _record_artifacts(engine, eid, [schema, answer, events, errors, prompt_path])
    command = [str(codex), "exec", "--json", "--ephemeral", "--skip-git-repo-check",
        "--ignore-user-config", "--ignore-rules", "--model", legacy.MODEL,
        "--config", 'model_reasoning_effort="high"', "--config", 'approval_policy="never"',
        "--sandbox", "read-only", "--cd", str(workdir), "--output-schema", str(schema),
        "--output-last-message", str(answer)]
    for image in images:
        command.extend(["--image", str(image)])
    command.extend(["--", "-"])
    env = dict(os.environ)
    env["CODEX_HOME"] = str(Path.home().resolve() / ".codex")
    private_tmp = jobs / "tmp"
    legacy._directory(private_tmp, "execution temporary folder", create=True)
    env.update(TMPDIR=str(private_tmp), TMP=str(private_tmp), TEMP=str(private_tmp))
    child = None
    model_owner = None
    confirmed = False
    try:
        # Gate the new process until its ownership is durable. EOF before GO
        # exits without a model call, closing the spawn-before-record window.
        gate_read, gate_write = os.pipe()
        gate_code = ("import os,sys; f=int(sys.argv[1]); b=os.read(f,1); os.close(f); "
                     "b==b'G' or sys.exit(125); os.execvpe(sys.argv[2],sys.argv[2:],os.environ)")
        with prompt_path.open("rb") as stdin, events.open("ab") as stdout, errors.open("ab") as stderr:
            child = subprocess.Popen([sys.executable, "-I", "-S", "-B", "-c", gate_code,
                str(gate_read), *command], cwd=workdir, env=env, stdin=stdin, stdout=stdout,
                stderr=stderr, start_new_session=True, pass_fds=(gate_read, lock_fd))
        os.close(gate_read)
        try:
            model_owner = process_identity(child.pid)
        except ProcessInspectionError as exc:
            os.close(gate_write)
            child.wait(timeout=5)
            confirmed = not _group_alive(child.pid)
            raise RuntimeError(f"Cannot verify model process ownership: {exc}") from exc
        if not model_owner or model_owner["group"] != child.pid:
            os.close(gate_write)
            child.wait(timeout=5)
            confirmed = not _group_alive(child.pid)
            raise RuntimeError("Cannot verify model process ownership")
        with engine.transaction() as state:
            current = engine._execution(state, eid)
            if current["state"] != "running":
                os.close(gate_write)
                child.wait(timeout=5)
                raise RuntimeError("Review was stopped before model dispatch")
            current["model_owner"] = model_owner
        os.write(gate_write, b"G")
        os.close(gate_write)
        while child.poll() is None:
            current = engine.check_execution(eid)
            if current["state"] == "stopping":
                confirmed = stop_owned(child, model_owner)
                if not confirmed:
                    raise RuntimeError("Stop requested; owned process exit remains unconfirmed")
                raise RuntimeError("Review stopped by request or authorization expiry")
            time.sleep(0.1)
        confirmed = not _group_alive(model_owner["group"])
        if not confirmed:
            raise RuntimeError("Model leader exited but descendant process exit remains unconfirmed")
        if child.returncode:
            raise RuntimeError("Visual model execution failed; inspect saved request status")
        if not legacy._regular(answer, "review answer") or answer.stat().st_size > legacy.MAX_NOTE_BYTES:
            raise RuntimeError("Invalid model result file")
        reviewed = legacy._validate_response(answer.read_bytes(), execution["pages"])
        # Codex may publish its designated answer by atomic replacement. Only
        # this validated, regular output receives a new ownership identity;
        # rendered inputs and other replaced paths remain cleanup conflicts.
        answer_identity = _owned_artifact(answer, root)
        with engine.transaction() as state:
            current = engine._execution(state, eid)
            current["artifacts"] = [a for a in current["artifacts"] if a["path"] != answer_identity["path"]]
            current["artifacts"].append(answer_identity)
        for item in reviewed:
            fence = as_fence(execution, item["page"])
            body = item["notes"].strip() + "\n" + legacy.SENTINEL + "\n"
            # The storage command acquires storage only. Control stays held
            # from this authority decision through durable journal preparation.
            with control_lock(root):
                current = read_record(root)
                live = current["execution"]
                if not live or live["execution_id"] != eid or live["state"] != "running":
                    continue
                if not _active_links(current, execution["review_id"], item["page"], time.time()):
                    continue  # detaching A must not discard B's later batch page
                try:
                    legacy._store(root, "review-complete", execution["document_key"],
                        "--page", str(item["page"]), "--sha256", execution["sha256"],
                        "--status", item["status"], "--model", legacy.MODEL,
                        "--fence", json.dumps(fence, separators=(",", ":")),
                        "--visual-notes-stdin", input_data=body.encode())
                except RuntimeError:
                    if not _active_links(read_record(root), execution["review_id"], item["page"], time.time()):
                        continue  # expiry may happen during storage validation
                    raise
            # Reconcile from committed page records, including a crash between
            # the prior line and this one and requests that joined concurrently.
            engine.status()
    finally:
        if child is not None and child.poll() is None and model_owner:
            confirmed = stop_owned(child, model_owner)
        if child is not None and not confirmed:
            with engine.transaction() as state:
                current = engine._execution(state, eid)
                current.update(state="stopping", termination_error="owned_process_exit_unconfirmed")
            # No cleanup and no release: a living child inherits execution.lock.
            raise RuntimeError("Owned process exit unconfirmed; temporary files retained")


def as_fence(execution: dict[str, Any], page: int) -> dict[str, Any]:
    return {name: (page if name == "page" else execution[name]) for name in ResultFence.__dataclass_fields__}


def _usage(path: Path) -> dict[str, int] | None:
    if not legacy._regular(path, "execution usage"):
        return None
    measured = None
    for line in path.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        usage = event.get("usage") if isinstance(event, dict) and event.get("type") == "turn.completed" else None
        if isinstance(usage, dict):
            measured = {key: value for key, value in usage.items()
                        if key in legacy.USAGE_FIELDS and type(value) is int and value >= 0} or None
    return measured


def supervise(root: Path, eid: str, fd: int, codex: Path, workdir: Path) -> None:
    _validate_fd(root, fd, "execution.lock")
    engine = Lifecycle(root)
    error = None
    try:
        try:
            owner = process_identity(os.getpid())
        except ProcessInspectionError as exc:
            raise RuntimeError(f"Cannot verify execution supervisor: {exc}") from exc
        if not owner:
            raise RuntimeError("Cannot verify execution supervisor")
        execution = engine.acknowledge(eid, owner)
        _model(engine, execution, codex, workdir, fd)
    except Exception as exc:
        error = str(exc)
    finally:
        current = read_record(root)["execution"]
        if current and current["execution_id"] == eid and not current.get("termination_error"):
            engine.finish(eid, error=error, tokens=_usage(root / DIRECTORY / f"events-{eid}.jsonl"))
            _cleanup_artifacts(engine, eid)
            engine.release_execution(eid)
        os.close(fd)


def _recover_execution(engine: Lifecycle) -> bool:
    """Return true only when dispatch is safe; a free worker lock is insufficient."""
    fd = _lock(engine.root, "execution.lock")
    if fd is None:
        current = read_record(engine.root)["execution"]
        if current and current["state"] == "stopping":
            supervisor, model = current.get("owner"), current.get("model_owner")
            # An orphan model retains the lock after its supervisor dies. A
            # user stop still acts on verified ownership; busy never means
            # "ignore cancellation". An unverifiable process remains stopping.
            try:
                if (supervisor and process_identity(supervisor["pid"]) is None
                        and model and model["group"] == model["pid"]
                        and process_identity(model["pid"]) == model):
                    for sig in (signal.SIGTERM, signal.SIGKILL):
                        if process_identity(model["pid"]) != model:
                            break
                        try:
                            os.killpg(model["group"], sig)
                        except ProcessLookupError:
                            break
                        until = time.monotonic() + 1.0
                        while time.monotonic() < until and process_identity(model["pid"]) == model:
                            time.sleep(0.05)
            except ProcessInspectionError:
                return False
        return False
    try:
        current = read_record(engine.root)["execution"]
        if current is None:
            return True
        for field in ("owner", "model_owner"):
            owner = current.get(field)
            if owner and process_identity(owner["pid"]) == owner:
                return False
            if owner and _group_alive(owner["group"]):
                # A leader may be gone while its descendants still live. Never
                # kill by stale PID or assume that lock release proves exit.
                return False
        if current["state"] != "exited":
            engine.finish(current["execution_id"], error="interrupted_before_confirmed_result")
        _cleanup_artifacts(engine, current["execution_id"])
        engine.release_execution(current["execution_id"])
        return True
    except ProcessInspectionError:
        return False
    finally:
        os.close(fd)


def worker(root: Path, fd: int, root_fd: int, codex: Path, workdir: Path) -> None:
    _validate_fd(root, fd, "worker.lock")
    root_info, actual = os.fstat(root_fd), root.stat(follow_symlinks=False)
    if (root_info.st_dev, root_info.st_ino) != (actual.st_dev, actual.st_ino):
        raise ValueError("Installation changed during worker handoff")
    engine = Lifecycle(root)
    try:
        while True:
            if not _recover_execution(engine):
                time.sleep(0.2)
                continue
            engine.cleanup()
            # Reserve while owning control and worker.lock. A concurrent submit
            # either lands before this scan or starts a successor after release.
            exec_fd = _lock(root, "execution.lock")
            if exec_fd is None:
                continue
            execution = engine.reserve(on_idle=lambda: fcntl.flock(fd, fcntl.LOCK_UN))
            if not execution:
                os.close(exec_fd)
                return
            command = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                "--root", str(root), "--supervisor", execution["execution_id"],
                "--execution-fd", str(exec_fd), "--codex", str(codex), "--neutral-cwd", str(workdir)]
            try:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True, pass_fds=(exec_fd,))
            finally:
                os.close(exec_fd)
            child.wait()
    finally:
        os.close(fd)
        os.close(root_fd)


def launch(root: Path, *, codex: Path | None = None, workdir: Path | None = None) -> dict[str, Any]:
    import shutil
    root = legacy._project_root(root)
    engine = Lifecycle(root)
    engine.status()  # reconcile and reject legacy format before any process side effect
    with legacy._root_guard(root) as root_fd:
        with control_lock(root):
            fd = _lock(root, "worker.lock")
            if fd is None:
                return {"worker": "already_active"}
            try:
                executable = codex or Path(shutil.which("codex") or "")
                if not executable.is_file() or not os.access(executable, os.X_OK):
                    raise ValueError("Codex executable unavailable; intake is durably queued")
                neutral = workdir or legacy._neutral_cwd(root)
                if neutral.resolve().is_relative_to(root):
                    raise ValueError("Review working directory must be outside the store")
                command = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                    "--root", str(root), "--worker", "--worker-fd", str(fd), "--root-fd", str(root_fd),
                    "--codex", str(executable), "--neutral-cwd", str(neutral)]
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, start_new_session=True, pass_fds=(fd, root_fd))
                legacy._LOCAL_CHILDREN.append(child)
            finally:
                os.close(fd)
    # A spawned PID is not readiness. Return truthful short-wait acknowledgement.
    until = time.monotonic() + 0.5
    while time.monotonic() < until:
        execution = read_record(root)["execution"]
        if execution and execution["state"] == "running":
            return {"worker": "acknowledged", "execution_id": execution["execution_id"]}
        if child.poll() is not None:
            return {"worker": "idle" if child.returncode == 0 else "failed"}
        time.sleep(0.02)
    return {"worker": "starting_unconfirmed"}


def migrate(root: Path, *, confirmed_exit: bool) -> dict[str, Any]:
    if not confirmed_exit:
        raise ValueError("Explicit confirmation of legacy worker and child exit is required")
    with control_lock(root), conversation_lock(root):
        descriptors = []
        try:
            for name in ("worker.lock", "execution.lock", "notifier.lock"):
                fd = _lock(root, name)
                if fd is None:
                    raise ValueError("Legacy worker/notifier is still live; migration refused")
                descriptors.append(fd)
            legacy_path = root / DIRECTORY / "job.json"
            old = legacy._read_json(legacy_path)
            if old and old.get("pid"):
                if process_identity(old["pid"]) is not None or _group_alive(old["pid"]):
                    raise ValueError("Legacy process exit cannot be confirmed")
            if not (root / DIRECTORY / "lifecycle.json").exists():
                _save(root, read_record(root))
            # Preserve committed library material. Legacy operational records
            # contain no recoverable per-request consent and are not imported.
            for name in ("job.json", "requests.json", "notifications.json", "worker.log",
                         "notifier.stderr.log", "response-schema.json"):
                path = root / DIRECTORY / name
                unlink_owned_file(path, root, label="legacy review record", missing_ok=True)
            return {"version": 2, "migrated_requests": 0, "legacy_history": "removed", "documents_preserved": True}
        finally:
            for fd in descriptors:
                os.close(fd)


def _json_stdin() -> dict[str, Any]:
    from research_store.cli import _read_stdin_text
    result = json.loads(_read_stdin_text(label="review intake", max_bytes=1024 * 1024))
    if not isinstance(result, dict):
        raise ValueError("Intake specification must be an object")
    return result


def _source_intake(engine: Lifecycle, rid: str, item: dict[str, Any]) -> dict[str, Any]:
    from research_store.config import load_config
    from research_store.safety import safe_source_file
    from research_store.sync import _hash, _iter_source_pdfs, intake_receipts_locked
    parent = item["item_id"]
    with engine.transaction() as state:
        request = engine._get(state, rid)
        frozen = request.get("source_manifests", {}).get(parent)
    config = load_config(engine.root / ".research-store/config.toml")
    if frozen is None:
        source = next((s for s in config.sources if s.id == item["source_id"] and s.enabled), None)
        if source is None or not source.available:
            raise ValueError("Requested source is unavailable or not registered")
        frozen = {}
        # Hash read-only originals without holding lifecycle/storage locks.
        # The first durable inventory wins concurrent retries of this intake.
        for path in _iter_source_pdfs(source):
            safe = safe_source_file(path, source.path)
            frozen[f"{source.id}:{source.relative_path(path).as_posix()}"] = _hash(safe)
        with engine.transaction() as state:
            request = engine._get(state, rid)
            frozen = request.setdefault("source_manifests", {}).setdefault(parent, frozen)
    with engine.transaction():
        receipts = intake_receipts_locked(config, rid)
    completed = {r["document_key"] for r in receipts if r.get("parent_item_id") == parent and r.get("committed")}
    remaining = {k: v for k, v in frozen.items() if k not in completed}
    if remaining:
        legacy._store(engine.root, "sync", "--source-id", item["source_id"],
            "--request-id", rid, "--item-id", parent,
            "--intake-manifest", json.dumps(remaining, separators=(",", ":")))
    with engine.transaction():
        receipts = intake_receipts_locked(config, rid)
    successful = set()
    for stored in receipts:
        if (stored.get("parent_item_id") == parent and stored.get("committed")
                and frozen.get(stored["document_key"]) == stored["sha256"]):
            engine.attach(rid, stored["item_id"], stored, parent_item_id=parent, explicit=False)
            successful.add(stored["document_key"])
    with engine.transaction() as state:
        request = engine._get(state, rid)
        failed = sorted(set(frozen) - successful)
        request["items"][parent].update(state="failed" if failed else "complete",
                                       failed_documents=failed, committed_documents=sorted(successful))
        engine._derive(state, request)
        return engine._receipt(state, request)


def submit(root: Path, key: str, expires: float, specification: dict[str, Any],
           *, limits: Limits | None = None, start_worker: bool = True) -> dict[str, Any]:
    """One deterministic intent -> text storage -> exact links -> handoff path."""
    engine = Lifecycle(root)
    receipt = engine.begin(key, expires, specification, limits=limits)
    engine.cleanup()
    rid = receipt["request_id"]
    for item in specification["items"]:
        item_id = item["item_id"]
        if receipt["items"][item_id]["state"] in {"linked", "complete", "deleted"}:
            continue
        try:
            if "source_id" in item:
                receipt = _source_intake(engine, rid, item)
                continue
            # Recover only committed item receipts, never infer from filenames
            # or today's global pending queue if an attachment disappeared.
            with engine.transaction() as state:
                from research_store.config import load_config
                from research_store.sync import intake_receipts_locked
                config = load_config(root / ".research-store/config.toml")
                stored = next((r for r in intake_receipts_locked(config, rid) if r["item_id"] == item_id), None)
            document_key = item.get("document_key")
            if stored:
                document_key = stored["document_key"]
            elif "attachment" in item:
                imported = legacy._store(root, "import-pdf", item["attachment"],
                    "--request-id", rid, "--item-id", item_id)
                document_key = imported["document_key"]
            if not document_key:
                raise ValueError("An exact document_key or attachment is required")
            if "attachment" in item or (stored and not stored.get("committed")):
                legacy._store(root, "sync", "--imported-document", document_key,
                              "--request-id", rid, "--item-id", item_id)
            with engine.transaction():
                documents = storage_snapshot(root)
                document = next((d for d in documents if d["document_key"] == document_key), None)
            if document is None:
                raise ValueError("Text conversion did not commit for this input")
            receipt = engine.attach(rid, item_id, document)
        except (OSError, RuntimeError, ValueError) as error:
            receipt = engine.attach(rid, item_id, None, error=str(error))
    handoff = {"worker": "not_requested"}
    if start_worker and any(i["state"] == "linked" for i in receipt["items"].values()):
        try:
            handoff = launch(root)
        except (OSError, RuntimeError, ValueError) as error:
            handoff = {"worker": "startup_failed", "error": str(error)}
    return {**engine.status(rid), "handoff": handoff}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-fd", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--root-fd", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--supervisor", help=argparse.SUPPRESS)
    parser.add_argument("--execution-fd", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--codex", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--neutral-cwd", type=Path, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command")
    key_parser = commands.add_parser("key")
    key_parser.add_argument("--validity-seconds", type=int, default=86400)
    for name in ("submit", "prepare", "start"):
        command = commands.add_parser(name)
        command.add_argument("--key", required=True)
        command.add_argument("--key-expires-at", type=float, required=True)
        command.add_argument("--spec-stdin", action="store_true", required=True)
        command.add_argument("--warn-seconds", type=float)
        command.add_argument("--warn-pages", type=int)
        command.add_argument("--warning-ratio", type=float, default=0.8)
        command.add_argument("--retention-seconds", type=float, default=30 * 86400)
        command.add_argument("--wait", action="store_true", help="저장된 결과가 준비될 때까지 기다리기; 중단해도 작업은 유지")
    command = commands.add_parser("status")
    command.add_argument("--request")
    for name in ("pause", "cancel", "resume"):
        command = commands.add_parser(name)
        scope = command.add_mutually_exclusive_group(required=True)
        scope.add_argument("--request")
        scope.add_argument("--document")
        scope.add_argument("--library", action="store_true")
    commands.add_parser("cleanup")
    command = commands.add_parser("forget")
    command.add_argument("--request", required=True)
    command = commands.add_parser("delete-document")
    command.add_argument("document")
    command = commands.add_parser("migrate")
    command.add_argument("--confirm-legacy-exit", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = legacy._project_root(args.root)
        if args.worker:
            if args.command or args.worker_fd is None or args.root_fd is None or not args.codex or not args.neutral_cwd:
                raise ValueError("Invalid private worker handoff")
            worker(root, args.worker_fd, args.root_fd, args.codex, args.neutral_cwd)
            return
        if args.supervisor:
            if args.command or args.execution_fd is None or not args.codex or not args.neutral_cwd:
                raise ValueError("Invalid private execution handoff")
            supervise(root, args.supervisor, args.execution_fd, args.codex, args.neutral_cwd)
            return
        if any(v is not None for v in (args.worker_fd, args.root_fd, args.execution_fd, args.codex, args.neutral_cwd)):
            raise ValueError("Private process arguments are not public controls")
        engine = Lifecycle(root)
        if args.command not in {"key", "migrate", "prepare", "submit", "start", "cleanup"}:
            engine.cleanup()
        if args.command == "key":
            if not 1 <= args.validity_seconds <= 366 * 86400:
                raise ValueError("Key validity must be between one second and one year")
            import secrets
            expires = int(time.time()) + args.validity_seconds
            result = {"key": f"vr2.{expires}.{secrets.token_hex(16)}", "key_expires_at": expires}
        elif args.command in {"submit", "prepare", "start"}:
            specification = _json_stdin()
            limits = Limits(args.warn_seconds, args.warn_pages, args.warning_ratio, args.retention_seconds)
            result = (engine.begin(args.key, args.key_expires_at, specification, limits=limits)
                      if args.command == "prepare" else submit(root, args.key, args.key_expires_at, specification, limits=limits))
            if args.command == "prepare":
                engine.cleanup()
            if args.wait and args.command != "prepare" and result.get("handoff", {}).get("worker") != "startup_failed":
                while result["state"] in {"queued", "running", "intake"}:
                    time.sleep(0.2)
                    result = engine.status(result["request_id"])
        elif args.command == "status":
            _recover_execution(engine)
            result = engine.status(args.request)
        elif args.command in {"pause", "cancel", "resume"}:
            result = engine.control(args.command, request_id=args.request, document_key=args.document, library=args.library)
            if args.command != "resume":
                _recover_execution(engine)
            if args.command == "resume":
                result["handoff"] = launch(root)
        elif args.command == "cleanup":
            _recover_execution(engine)
            result = engine.cleanup()
        elif args.command == "forget":
            engine.forget(args.request)
            result = {"request_id": args.request, "state": "forgotten_or_cleanup_pending"}
        elif args.command == "delete-document":
            _recover_execution(engine)
            result = engine.delete_document(args.document)
        elif args.command == "migrate":
            result = migrate(root, confirmed_exit=args.confirm_legacy_exit)
        else:
            parser.error("A lifecycle command is required")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"오류: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
