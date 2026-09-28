"""Native ownership inspection and fail-closed lifecycle decisions; no models."""
from __future__ import annotations

import ctypes
from contextlib import nullcontext
import errno
import importlib.util
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("process_identity_runner", PROJECT / "scripts/background_lifecycle.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class DarwinIdentityTests(unittest.TestCase):
    def setUp(self):
        platform = patch.object(runner.sys, "platform", "darwin")
        platform.start()
        self.addCleanup(platform.stop)
        forbidden_ps = patch.object(runner.subprocess, "check_output", side_effect=AssertionError("Darwin must not execute ps"))
        forbidden_ps.start()
        self.addCleanup(forbidden_ps.stop)

    def query(self, *, returned=136, error=0, pid=123, status=2, group=123,
              seconds=1_800_000_000, micros=123456):
        # Independent SDK wire layout, including signed pbi_nice. Do not build
        # the fixture through the ctypes structure being tested.
        data = struct.pack("=12I16s32s5Ii2Q", 0, status, 0, pid, 1, 501, 20,
            501, 20, 501, 20, 0, b"python", b"python", 3, group, 0, 0, 0, -2,
            seconds, micros)
        def inspect(requested, flavor, argument, buffer, size):
            self.assertEqual((requested, flavor, argument, size), (123, 3, 0, 136))
            ctypes.memmove(buffer, data, len(data))
            ctypes.set_errno(error)
            return returned
        function = Mock(side_effect=inspect)
        library = Mock(proc_pidinfo=function)
        with patch.object(runner.ctypes, "CDLL", return_value=library) as load:
            identity = runner.process_identity(123)
        load.assert_called_once_with("/usr/lib/libproc.dylib", use_errno=True)
        self.assertEqual(function.argtypes, [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                            ctypes.c_void_p, ctypes.c_int])
        self.assertIs(function.restype, ctypes.c_int)
        return identity

    def test_sdk_structure_has_exact_fixed_width_offsets_on_both_alignments(self):
        expected = {"pbi_flags": 0, "pbi_status": 4, "pbi_xstatus": 8, "pbi_pid": 12,
            "pbi_ppid": 16, "pbi_uid": 20, "pbi_gid": 24, "pbi_ruid": 28,
            "pbi_rgid": 32, "pbi_svuid": 36, "pbi_svgid": 40, "rfu_1": 44,
            "pbi_comm": 48, "pbi_name": 64, "pbi_nfiles": 96, "pbi_pgid": 100,
            "pbi_pjobc": 104, "e_tdev": 108, "e_tpgid": 112, "pbi_nice": 116,
            "pbi_start_tvsec": 120, "pbi_start_tvusec": 128}
        for alignment in (4, 8):
            layout = type(f"Layout{alignment}", (ctypes.Structure,), {
                "_pack_": alignment, "_fields_": runner._DarwinProcBsdInfo._fields_})
            with self.subTest(alignment=alignment):
                self.assertEqual(ctypes.sizeof(layout), 136)
                self.assertEqual({name: getattr(layout, name).offset for name in expected}, expected)
        self.assertEqual(ctypes.sizeof(runner._DarwinProcBsdInfo), 136)

    def test_native_identity_preserves_microsecond_creation_time(self):
        first = self.query(micros=1)
        second = self.query(micros=2)
        self.assertEqual(first, {"pid": 123, "group": 123, "birth": "darwin:1800000000.000001"})
        self.assertNotEqual(first, second)
        self.assertEqual(self.query(micros=0)["birth"], "darwin:1800000000.000000")

    def test_full_64_bit_seconds_are_not_truncated(self):
        self.assertEqual(self.query(seconds=2**40)["birth"], f"darwin:{2**40}.123456")

    def test_pid_types_and_c_integer_range_are_validated_before_native_call(self):
        with patch.object(runner.ctypes, "CDLL") as load:
            for pid in (0, -1, True, False, "123", 123.0, None, 2**31, 2**64 + 123):
                with self.subTest(pid=pid), self.assertRaises(runner.ProcessInspectionError):
                    runner.process_identity(pid)
            load.assert_not_called()

    def test_returned_pid_must_match_even_for_zombie(self):
        for status in (2, 5):
            with self.subTest(status=status), self.assertRaisesRegex(runner.ProcessInspectionError, "PID did not match"):
                self.query(pid=124, status=status)

    def test_zombie_has_no_live_identity(self):
        self.assertIsNone(self.query(status=5, group=0, seconds=0, micros=0))

    def test_only_confirmed_missing_syscall_is_absent(self):
        for result in (0, -1):
            with self.subTest(result=result):
                self.assertIsNone(self.query(returned=result, error=errno.ESRCH))

    def test_denied_and_other_failed_queries_remain_unknown(self):
        for error in (0, errno.EPERM, errno.EACCES, errno.EINVAL, errno.EIO):
            with self.subTest(error=error), self.assertRaises(runner.ProcessInspectionError):
                self.query(returned=0, error=error)

    def test_exact_return_size_is_required(self):
        for returned in (1, 128, 135, 137, 272):
            with self.subTest(returned=returned), self.assertRaisesRegex(runner.ProcessInspectionError, "incomplete or incompatible"):
                self.query(returned=returned, error=errno.ESRCH)

    def test_missing_or_invalid_identity_fields_remain_unknown(self):
        for values in ({"group": 0}, {"group": 2**31}, {"seconds": 0},
                       {"micros": 1_000_000}, {"status": 0}, {"status": 6}):
            with self.subTest(values=values), self.assertRaisesRegex(runner.ProcessInspectionError, "record is invalid"):
                self.query(**values)

    def test_incompatible_local_layout_is_rejected_before_syscall(self):
        with patch.object(runner.ctypes, "sizeof", return_value=128), patch.object(runner.ctypes, "CDLL") as load:
            with self.assertRaisesRegex(runner.ProcessInspectionError, "ABI is unsupported"):
                runner.process_identity(123)
            load.assert_not_called()

    def test_missing_library_or_symbol_has_sanitized_diagnostic(self):
        for value in (OSError("private implementation detail"), AttributeError("private implementation detail")):
            with self.subTest(value=value), patch.object(runner.ctypes, "CDLL", side_effect=value):
                with self.assertRaises(runner.ProcessInspectionError) as caught:
                    runner.process_identity(123)
                self.assertEqual(str(caught.exception), "Darwin process identity API is unavailable")


class OtherPlatformIdentityTests(unittest.TestCase):
    def linux_query(self, value):
        with patch.object(runner.sys, "platform", "linux"), patch.object(runner.Path, "is_dir", return_value=True), \
                patch.object(runner.Path, "read_text", side_effect=value if isinstance(value, Exception) else None,
                             return_value=value), patch.object(runner.os, "kill"):
            return runner.process_identity(123)

    def test_linux_preserves_proc_start_ticks_and_group(self):
        fields = ["S", "1", "123", *(["0"] * 16), "67890"]
        self.assertEqual(self.linux_query("123 (name with ) parentheses) " + " ".join(fields)),
                         {"pid": 123, "group": 123, "birth": "67890"})

    def test_linux_missing_and_zombie_are_absent(self):
        self.assertIsNone(self.linux_query(FileNotFoundError()))
        self.assertIsNone(self.linux_query("123 (python) Z"))

    def test_linux_denied_and_malformed_records_are_not_absent(self):
        for value in (PermissionError(), "malformed", "123 (python) S 1 0"):
            with self.subTest(value=value), self.assertRaises(runner.ProcessInspectionError):
                self.linux_query(value)

    def test_unsupported_platform_preserves_ps_fallback(self):
        with patch.object(runner.sys, "platform", "freebsd"), patch.object(runner.Path, "is_dir", return_value=False), \
                patch.object(runner.subprocess, "check_output", return_value=" 123 Mon Sep 28 10:00:00 2026\n") as ps:
            self.assertEqual(runner.process_identity(123),
                {"pid": 123, "group": 123, "birth": "Mon Sep 28 10:00:00 2026"})
            self.assertEqual(ps.call_args.kwargs["stderr"], subprocess.PIPE)

    def test_ps_failure_requires_independent_confirmation_of_absence(self):
        with patch.object(runner.sys, "platform", "freebsd"), patch.object(runner.Path, "is_dir", return_value=False), \
                patch.object(runner.subprocess, "check_output", side_effect=subprocess.CalledProcessError(1, "ps")), \
                patch.object(runner.os, "kill", side_effect=ProcessLookupError()) as probe:
            self.assertIsNone(runner.process_identity(123))
            probe.assert_called_once_with(123, 0)

    def test_ps_denial_and_missing_executable_are_not_absent(self):
        for error in (PermissionError(), FileNotFoundError(), subprocess.CalledProcessError(1, "ps")):
            with self.subTest(error=error), patch.object(runner.sys, "platform", "freebsd"), \
                    patch.object(runner.Path, "is_dir", return_value=False), \
                    patch.object(runner.subprocess, "check_output", side_effect=error), \
                    patch.object(runner.os, "kill", side_effect=PermissionError()):
                with self.assertRaises(runner.ProcessInspectionError):
                    runner.process_identity(123)


class OwnershipFailureTests(unittest.TestCase):
    def setUp(self):
        self.owner = {"pid": 123, "group": 123, "birth": "native-time"}
        self.denied = runner.ProcessInspectionError("Darwin process identity inspection was denied")

    def test_initial_inspection_denial_never_signals(self):
        child = Mock(pid=123, poll=Mock(return_value=None))
        with patch.object(runner, "process_identity", side_effect=self.denied), patch.object(runner.os, "killpg") as kill:
            self.assertFalse(runner.stop_owned(child, self.owner))
            kill.assert_not_called()

    def test_inspection_denial_after_term_prevents_kill_escalation(self):
        child = Mock(pid=123, poll=Mock(return_value=None))
        with patch.object(runner, "process_identity", side_effect=[self.owner, self.denied]), \
                patch.object(runner.time, "monotonic", side_effect=[0, 3]), patch.object(runner.os, "killpg") as kill:
            self.assertFalse(runner.stop_owned(child, self.owner))
            kill.assert_called_once_with(123, signal.SIGTERM)

    def test_denied_supervisor_or_model_cannot_authorize_orphan_signals(self):
        execution = {"state": "stopping", "owner": {"pid": 122}, "model_owner": self.owner}
        for lookups in ([self.denied], [None, self.denied]):
            with self.subTest(lookups=lookups), patch.object(runner, "_lock", return_value=None), \
                    patch.object(runner, "read_record", return_value={"execution": execution}), \
                    patch.object(runner, "process_identity", side_effect=lookups), patch.object(runner.os, "killpg") as kill:
                self.assertFalse(runner._recover_execution(Mock(root=Path("/unused"))))
                kill.assert_not_called()

    def test_orphan_inspection_denial_after_term_prevents_escalation(self):
        execution = {"state": "stopping", "owner": {"pid": 122}, "model_owner": self.owner}
        with patch.object(runner, "_lock", return_value=None), \
                patch.object(runner, "read_record", return_value={"execution": execution}), \
                patch.object(runner, "process_identity", side_effect=[None, self.owner, self.owner, self.denied]), \
                patch.object(runner.time, "monotonic", side_effect=[0, .1]), patch.object(runner.os, "killpg") as kill:
            self.assertFalse(runner._recover_execution(Mock(root=Path("/unused"))))
            kill.assert_called_once_with(123, signal.SIGTERM)

    def test_denied_owner_prevents_recovery_cleanup_and_release(self):
        execution = {"state": "running", "execution_id": "e", "owner": self.owner,
                     "model_owner": {"pid": 124, "group": 124, "birth": "model-time"}}
        for lookups in ([self.denied], [None, self.denied]):
            engine = Mock(root=Path("/unused"))
            with self.subTest(lookups=lookups), patch.object(runner, "_lock", return_value=456), \
                    patch.object(runner, "read_record", return_value={"execution": execution}), \
                    patch.object(runner, "process_identity", side_effect=lookups), \
                    patch.object(runner, "_group_alive", return_value=False), \
                    patch.object(runner, "_cleanup_artifacts") as cleanup, patch.object(runner.os, "close") as close:
                self.assertFalse(runner._recover_execution(engine))
                engine.finish.assert_not_called()
                engine.release_execution.assert_not_called()
                cleanup.assert_not_called()
                close.assert_called_once_with(456)

    def test_supervisor_records_safe_inspection_diagnostic(self):
        engine = Mock()
        with patch.object(runner, "_validate_fd"), patch.object(runner, "Lifecycle", return_value=engine), \
                patch.object(runner, "process_identity", side_effect=self.denied), \
                patch.object(runner, "read_record", return_value={"execution": {"execution_id": "e"}}), \
                patch.object(runner, "_usage", return_value=None), patch.object(runner, "_cleanup_artifacts"), \
                patch.object(runner.os, "close"), patch.object(runner, "_model") as model:
            runner.supervise(Path("/unused"), "e", 456, Path("/fake"), Path("/work"))
            model.assert_not_called()
            engine.acknowledge.assert_not_called()
            engine.finish.assert_called_once_with("e", tokens=None,
                error="Cannot verify execution supervisor: Darwin process identity inspection was denied")

    def test_model_inspection_denial_closes_gate_and_reaps_without_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / ".research-agent-root").write_text("research-agent-owned-root-v1\n")
            (root / runner.DIRECTORY).mkdir(parents=True)
            execution = {"execution_id": "e", "document_key": "s:paper.pdf",
                         "sha256": "a" * 64, "pages": [1], "state": "running"}
            engine = Mock(root=root)
            engine.transaction.side_effect = lambda: nullcontext({"execution": execution})
            engine._execution.return_value = execution
            popen, children = subprocess.Popen, []
            def launch(*args, **kwargs):
                child = popen(*args, **kwargs)
                children.append(child)
                return child
            row = {"document_key": "s:paper.pdf", "page_number": 1}
            with patch.object(runner.legacy, "_review_queue", return_value=[row]), \
                    patch.object(runner.legacy, "_render_source_directory", return_value=(root / "renders", set())), \
                    patch.object(runner.legacy, "_store", return_value={"sha256": "a" * 64, "rendered": []}), \
                    patch.object(runner.legacy, "_validate_rendered_images", return_value=(None,) * 4), \
                    patch.object(runner.legacy, "_read_base_pages", return_value=""), \
                    patch.object(runner.legacy, "_prompt", return_value=""), \
                    patch.object(runner, "_record_artifacts"), \
                    patch.object(runner.subprocess, "Popen", side_effect=launch), \
                    patch.object(runner, "process_identity", side_effect=self.denied):
                with self.assertRaisesRegex(RuntimeError, "Cannot verify model process ownership: Darwin process identity inspection was denied"):
                    runner._model(engine, execution, Path(sys.executable), root, 0)
            self.assertEqual(len(children), 1)
            self.assertEqual(children[0].poll(), 125)  # Gate EOF exit, before exec.
            self.assertEqual(execution["state"], "running")
            self.assertNotIn("termination_error", execution)


@unittest.skipUnless(sys.platform in ("darwin", "linux"), "Native process inspection requires Darwin or Linux")
class NativeIdentitySmokeTests(unittest.TestCase):
    def test_self_identity_is_stable_and_matches_os_group(self):
        identity = runner.process_identity(os.getpid())
        self.assertIsNotNone(identity)
        self.assertEqual(identity["pid"], os.getpid())
        self.assertEqual(identity["group"], os.getpgrp())
        self.assertEqual(runner.process_identity(os.getpid()), identity)

    def test_gated_child_identity_survives_exec_then_disappears_after_reap(self):
        reader, writer = os.pipe()
        code = ("import os,sys; f=int(sys.argv[1]); os.read(f,1); os.close(f); "
                "os.execv(sys.executable,[sys.executable,'-I','-S','-c',"
                "'import sys; print(\"ready\",flush=True); sys.stdin.read(1)'])")
        child = subprocess.Popen([sys.executable, "-I", "-S", "-c", code, str(reader)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, start_new_session=True, pass_fds=(reader,))
        os.close(reader)
        try:
            identity = runner.process_identity(child.pid)
            self.assertEqual(identity["group"], child.pid)
            os.write(writer, b"G")
            os.close(writer)
            writer = None
            self.assertEqual(child.stdout.readline(), b"ready\n")
            self.assertEqual(runner.process_identity(child.pid), identity)
            child.communicate(b"X", timeout=5)
            self.assertIsNone(runner.process_identity(child.pid))
        finally:
            if writer is not None:
                os.close(writer)
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.stdin.close()
            child.stdout.close()


if __name__ == "__main__":
    unittest.main()
