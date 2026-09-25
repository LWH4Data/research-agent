from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HELPER = Path(__file__).resolve().parents[1] / "scripts/import_attachment.py"
SPEC = importlib.util.spec_from_file_location("attachment_transport", HELPER)
transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transport)


class AttachmentTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.originals = self.base / "originals"
        self.originals.mkdir()
        self.pdf = self.originals / "paper.pdf"
        self.content = b"%PDF-1.7\ntransport fixture\n%%EOF\n"
        self.pdf.write_bytes(self.content)
        self.args = ["--codex", str(self.base / "codex"), "--root",
                     str(self.base / "store"), "--sandbox-home",
                     str(self.base / "profile"), "--path", str(self.pdf)]

    def fingerprint(self):
        result = {}
        for path in self.originals.iterdir():
            info = path.lstat()
            result[path.name] = (info.st_mode, info.st_size, info.st_ino,
                                 info.st_mtime_ns, info.st_ctime_ns,
                                 hashlib.sha256(path.read_bytes()).hexdigest())
        return result

    def test_exact_bytes_fixed_argv_profile_and_original_preserved(self):
        before = self.fingerprint()
        with mock.patch.object(transport.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(transport.main(self.args), 0)
        self.assertEqual(self.fingerprint(), before)
        command = run.call_args.args[0]
        self.assertEqual(command, [str(self.base / "codex"), "sandbox", "-P",
            "research-store", "-C", str(self.base / "profile"), "--",
            str(self.base / "store/research-store"), "import-pdf", "--stdin",
            "--name", "paper.pdf"])
        options = run.call_args.kwargs
        self.assertEqual(options["input"], self.content)
        self.assertEqual(options["env"]["CODEX_HOME"], str(self.base / "profile"))
        self.assertFalse(options["check"])
        self.assertNotIn("shell", options)
        self.assertNotIn("stdout", options)
        self.assertNotIn("stderr", options)
        self.assertNotIn(str(self.pdf), command)
        self.assertNotIn(str(self.originals), command)

    def test_quoted_newline_name_is_single_literal_argument(self):
        name = "paper'\"$(touch unexpected)\n한글.PDF"
        renamed = self.pdf.with_name(name)
        self.pdf.rename(renamed)
        args = self.args[:-1] + [str(renamed)]
        with mock.patch.object(transport.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertEqual(transport.main(args), 0)
        self.assertEqual(run.call_args.args[0][-1], name)
        self.assertEqual(run.call_args.kwargs["input"], self.content)
        self.assertEqual(list(self.originals.iterdir()), [renamed])

    def test_only_exact_attachment_is_opened_readonly_and_descriptor_closed(self):
        for content in (self.content, b"invalid"):
            self.pdf.write_bytes(content)
            with mock.patch.object(transport.os, "open", wraps=os.open) as opened:
                with mock.patch.object(transport.os, "close", wraps=os.close) as closed:
                    if content == self.content:
                        transport.read_attachment(str(self.pdf))
                    else:
                        with self.assertRaises(ValueError):
                            transport.read_attachment(str(self.pdf))
                    opened.assert_called_once_with(str(self.pdf),
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    closed.assert_called_once()
                    with self.assertRaises(OSError):
                        os.fstat(closed.call_args.args[0])

    def test_symlink_is_rejected_without_launching_child(self):
        link = self.originals / "linked.pdf"
        link.symlink_to(self.pdf)
        with mock.patch.object(transport.subprocess, "run") as run:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(transport.main(self.args[:-1] + [str(link)]), 2)
            run.assert_not_called()
        self.assertTrue(link.is_symlink())
        self.assertEqual(self.pdf.read_bytes(), self.content)

    def test_fifo_and_directory_are_rejected_without_blocking(self):
        fifo = self.originals / "fifo.pdf"
        os.mkfifo(fifo)
        folder = self.originals / "directory.pdf"
        folder.mkdir()
        for path in (fifo, folder):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "일반 파일"):
                    transport.read_attachment(str(path))
        self.assertTrue(stat.S_ISFIFO(fifo.lstat().st_mode))

    def test_relative_path_and_invalid_filename_are_rejected_before_open(self):
        for path in ("paper.pdf", "", "/tmp/bad.txt", "/tmp/back\\slash.pdf",
                     "/tmp/invalid\0.pdf", "/tmp/" + "가" * 90 + ".pdf"):
            with self.subTest(path=path), mock.patch.object(transport.os, "open") as opened:
                with self.assertRaises(ValueError):
                    transport.read_attachment(path)
                opened.assert_not_called()

    def test_bad_magic_and_empty_file_are_rejected(self):
        for data in (b"", b"short", b"not a PDF\n%PDF-1.7"):
            self.pdf.write_bytes(data)
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "형식"):
                transport.read_attachment(str(self.pdf))

    def test_oversize_is_rejected_before_reading(self):
        with mock.patch.object(transport, "MAX_PDF_BYTES", 8):
            with mock.patch.object(transport.os, "read") as read:
                with self.assertRaisesRegex(ValueError, "256 MiB"):
                    transport.read_attachment(str(self.pdf))
                read.assert_not_called()

    def test_growing_file_read_is_bounded_to_limit_plus_one(self):
        self.pdf.write_bytes(b"%PDF-123")
        with mock.patch.object(transport, "MAX_PDF_BYTES", 16):
            with mock.patch.object(transport.os, "read", side_effect=[b"%PDF-", b"x" * 12]) as read:
                with self.assertRaisesRegex(ValueError, "256 MiB"):
                    transport.read_attachment(str(self.pdf))
                self.assertEqual([call.args[1] for call in read.call_args_list], [5, 12])

    def test_exact_size_limit_is_allowed(self):
        with mock.patch.object(transport, "MAX_PDF_BYTES", len(self.content)):
            self.assertEqual(transport.read_attachment(str(self.pdf)),
                             (self.pdf.name, self.content))

    def test_modified_file_is_rejected_after_read(self):
        original_read = os.read
        changed = False

        def concurrent_read(fd, count):
            nonlocal changed
            result = original_read(fd, count)
            if not changed:
                changed = True
                self.pdf.write_bytes(self.content.replace(b"fixture", b"updated"))
            return result

        with mock.patch.object(transport.os, "read", side_effect=concurrent_read):
            with self.assertRaisesRegex(ValueError, "변경"):
                transport.read_attachment(str(self.pdf))

    def test_replaced_path_is_rejected_after_read(self):
        original_read = os.read
        changed = False

        def concurrent_read(fd, count):
            nonlocal changed
            result = original_read(fd, count)
            if not changed:
                changed = True
                replacement = self.originals / "replacement.pdf"
                replacement.write_bytes(self.content)
                replacement.replace(self.pdf)
            return result

        with mock.patch.object(transport.os, "read", side_effect=concurrent_read):
            with self.assertRaisesRegex(ValueError, "변경"):
                transport.read_attachment(str(self.pdf))

    def test_missing_or_denied_path_returns_safe_error(self):
        for error in (FileNotFoundError("private filename"), PermissionError("private filename")):
            with self.subTest(error=error), mock.patch.object(transport.os, "open", side_effect=error):
                with mock.patch.object(transport.subprocess, "run") as run:
                    stderr = io.StringIO()
                    with contextlib.redirect_stderr(stderr):
                        self.assertEqual(transport.main(self.args), 2)
                    run.assert_not_called()
                    self.assertIn("읽기 권한", stderr.getvalue())
                    self.assertNotIn("private filename", stderr.getvalue())

    def test_no_passthrough_arguments_or_relative_trusted_paths(self):
        for args in (self.args + ["--", "sh", "-c", "exit 0"],
                     ["--codex", "relative"] + self.args[2:],
                     self.args + ["--arbitrary-command", "delete"]):
            with self.subTest(args=args), mock.patch.object(transport.subprocess, "run") as run:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    transport.main(args)
                self.assertEqual(caught.exception.code, 2)
                run.assert_not_called()

    def test_child_nonzero_and_signal_status_are_preserved(self):
        for status, expected in ((23, 23), (-15, 143)):
            with self.subTest(status=status), mock.patch.object(transport.subprocess, "run") as run:
                run.return_value.returncode = status
                self.assertEqual(transport.main(self.args), expected)

    def test_launch_failure_is_reported_without_fallback(self):
        with mock.patch.object(transport.subprocess, "run", side_effect=PermissionError) as run:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(transport.main(self.args), 1)
            self.assertEqual(run.call_count, 1)

    def test_isolated_process_inherits_child_output_and_failure(self):
        child = self.base / "codex"
        child.write_text("#!" + sys.executable + "\n"
                         "import hashlib, json, sys\n"
                         "print(json.dumps({'argv': sys.argv[1:], 'sha256': "
                         "hashlib.sha256(sys.stdin.buffer.read()).hexdigest()}))\n"
                         "print('child diagnostic', file=sys.stderr)\n"
                         "sys.exit(17)\n")
        child.chmod(0o700)
        before = self.fingerprint()
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(HELPER), *self.args],
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertEqual(result.stderr, b"child diagnostic\n")
        output = json.loads(result.stdout)
        self.assertEqual(output["sha256"], hashlib.sha256(self.content).hexdigest())
        self.assertEqual(output["argv"][-4:], ["import-pdf", "--stdin", "--name", "paper.pdf"])
        self.assertEqual(self.fingerprint(), before)


if __name__ == "__main__":
    unittest.main()
