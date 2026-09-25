from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


INSTALLER = Path(__file__).resolve().parents[1] / "install-release.sh"
VERSION = "0.3.0"
ARCHIVE = f"research-agent-{VERSION}.tar.gz"


class ReleaseInstallerTests(unittest.TestCase):
    """Exercise the actual shell bootstrap without network or real registration."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="release installer ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home with spaces"
        self.home.mkdir()
        self.downloads = self.root / "private temporary files"
        self.downloads.mkdir()
        self.fixtures = self.root / "release assets"
        self.fixtures.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        curl = self.bin / "curl"
        curl.write_text(
            f"#!{sys.executable}\n"
            "import os, pathlib, shutil, sys\n"
            "args = sys.argv[1:]\n"
            "url = next(arg for arg in args if arg.startswith('https://'))\n"
            "assert url.startswith('https://github.com/LWH4Data/research-agent/releases/download/v0.3.0/')\n"
            "assert '--proto-redir' in args and '=https' in args\n"
            "output = args[args.index('-o') + 1]\n"
            "if os.environ.get('RELEASE_TEST_DOWNLOAD_FAILURE'):\n"
            "    sys.exit(22)\n"
            "source = pathlib.Path(os.environ['RELEASE_TEST_ASSETS']) / url.rsplit('/', 1)[1]\n"
            "shutil.copyfile(source, output)\n"
            "if os.environ.get('RELEASE_TEST_CREATE_TARGET'):\n"
            "    pathlib.Path(os.environ['RELEASE_TEST_CREATE_TARGET']).mkdir(exist_ok=True)\n",
            encoding="utf-8",
        )
        curl.chmod(0o700)
        self.environment = os.environ | {
            "HOME": str(self.home),
            "TMPDIR": str(self.downloads),
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "RELEASE_TEST_ASSETS": str(self.fixtures),
        }
        self.target = self.home / "research-agent"
        self.make_archive()

    def make_archive(
        self,
        extra: list[tuple[str, bytes | None, bytes]] | None = None,
        *,
        setup_exit: int = 0,
        marker: str = "research-agent-owned-root-v1\n",
    ) -> None:
        """An optional None payload denotes a link or a special tar member."""
        setup = (
            '#!/bin/sh\nset -eu\n'
            'printf "%s\\n" "$0" > "$HOME/setup-ran"\n'
            'if [ "${RELEASE_TEST_READ_STDIN-}" = 1 ]; then\n'
            '    IFS= read -r answer\n'
            '    printf "%s\\n" "$answer" > "$HOME/setup-input"\n'
            'fi\n'
            'root=$(dirname -- "$0")\n'
            'mkdir "$root/.research-store"\n'
            'printf "saved data\\n" > "$root/.research-store/result"\n'
            f"exit {setup_exit}\n"
        ).encode()
        entries = [
            ("research-agent", None, tarfile.DIRTYPE),
            ("research-agent/.research-agent-root", marker.encode(), tarfile.REGTYPE),
            ("research-agent/install.sh", setup, tarfile.REGTYPE),
            ("research-agent/README.md", b"User guide\n", tarfile.REGTYPE),
        ] + (extra or [])
        with tarfile.open(self.fixtures / ARCHIVE, "w:gz") as archive:
            for name, body, kind in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.mode = 0o755 if kind == tarfile.DIRTYPE or name.endswith(".sh") else 0o644
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = "../../outside"
                if body is not None:
                    member.size = len(body)
                archive.addfile(member, io.BytesIO(body) if body is not None else None)
        checksum = hashlib.sha256((self.fixtures / ARCHIVE).read_bytes()).hexdigest()
        (self.fixtures / "SHA256SUMS").write_text(
            f"{checksum}  {ARCHIVE}\n" + "a" * 64 + "  install-release.sh\n",
            encoding="ascii",
        )

    def run_installer(self, *args: str, version: bool = True, stdin_text: str = "") -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["bash", str(INSTALLER), *(["--version", VERSION] if version else []), *args],
            env=self.environment,
            input=stdin_text,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(list(self.downloads.iterdir()), [], "Private staging must be cleaned.")
        return result

    def assert_rejected_before_install(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.target.exists())
        self.assertFalse((self.home / "setup-ran").exists())

    def test_fresh_install_verifies_and_keeps_stdin_available(self) -> None:
        self.environment["RELEASE_TEST_READ_STDIN"] = "1"
        result = self.run_installer(stdin_text="folder choice\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.home / "setup-ran").read_text().strip(), str((self.target / "install.sh").resolve()))
        self.assertEqual((self.home / "setup-input").read_text(), "folder choice\n")
        self.assertEqual((self.target / ".research-store/result").read_text(), "saved data\n")
        self.assertEqual((self.target / "README.md").read_text(), "User guide\n")

    def test_custom_destination_with_spaces(self) -> None:
        target = self.home / "my research tools"
        result = self.run_installer("--destination", str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / "README.md").is_file())
        self.assertFalse(self.target.exists())

    def test_bad_hash_never_extracts_or_creates_target(self) -> None:
        (self.fixtures / ARCHIVE).write_bytes(b"tampered file")
        self.assert_rejected_before_install(self.run_installer())

    def test_ambiguous_missing_and_malformed_checksum_are_rejected(self) -> None:
        checksum = self.fixtures / "SHA256SUMS"
        valid = checksum.read_text().splitlines()[0]
        for value in (valid + "\n" + valid + "\n", "", "z" * 64 + f"  {ARCHIVE}\n", valid + " injected\n"):
            with self.subTest(value=value):
                checksum.write_text(value)
                self.assert_rejected_before_install(self.run_installer())

    def test_existing_directory_and_file_are_preserved(self) -> None:
        for directory in (True, False):
            with self.subTest(directory=directory):
                if directory:
                    self.target.mkdir()
                    sentinel = self.target / "my-saved-conversation.md"
                else:
                    sentinel = self.target
                sentinel.write_text("keep this")
                result = self.run_installer()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(sentinel.read_text(), "keep this")
                self.assertFalse((self.home / "setup-ran").exists())
                sentinel.unlink()
                if directory:
                    self.target.rmdir()

    def test_existing_or_broken_symlink_is_never_followed(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "original.pdf"
        sentinel.write_bytes(b"original")
        for destination in (outside, self.root / "nonexistent"):
            with self.subTest(destination=destination):
                self.target.symlink_to(destination, target_is_directory=True)
                result = self.run_installer()
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(self.target.is_symlink())
                self.assertEqual(sentinel.read_bytes(), b"original")
                self.target.unlink()

    def test_destination_created_during_download_is_not_merged(self) -> None:
        self.environment["RELEASE_TEST_CREATE_TARGET"] = str(self.target)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.target.iterdir()), [])
        self.assertFalse((self.home / "setup-ran").exists())

    def test_unsafe_archive_paths_are_rejected_before_extraction(self) -> None:
        names = (
            "/absolute-path",
            "../outside",
            "research-agent/../outside",
            "research-agent/./file",
            "research-agent//file",
            "other-root/file",
            "research-agent/with space",
            "research-agent/a\nresearch-agent/b",
            "research-agent/README.md",
        )
        for name in names:
            with self.subTest(name=name):
                self.make_archive([(name, b"unsafe", tarfile.REGTYPE)])
                self.assert_rejected_before_install(self.run_installer())

    def test_links_and_special_archive_types_are_rejected(self) -> None:
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE):
            with self.subTest(kind=kind):
                self.make_archive([("research-agent/unsafe", None, kind)])
                self.assert_rejected_before_install(self.run_installer())

    def test_wrong_root_marker_is_rejected(self) -> None:
        self.make_archive(marker="another-project\n")
        self.assert_rejected_before_install(self.run_installer())

    def test_failed_native_install_is_preserved_without_cleanup_of_user_data(self) -> None:
        self.make_archive(setup_exit=7)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.home / "setup-ran").is_file())
        self.assertEqual((self.target / ".research-store/result").read_text(), "saved data\n")
        self.assertIn("보존", result.stderr)

    def test_failed_download_cleans_only_staging(self) -> None:
        sentinel = self.home / "original.pdf"
        sentinel.write_bytes(b"original")
        self.environment["RELEASE_TEST_DOWNLOAD_FAILURE"] = "1"
        self.assert_rejected_before_install(self.run_installer())
        self.assertEqual(sentinel.read_bytes(), b"original")

    def test_version_must_be_explicit_and_cannot_change_download_path(self) -> None:
        for arguments in ((), ("--version", "../bad"), ("--version", "0.3"), ("--version", "00.3.0"), ("--version", "0.3.0\n0.3.0")):
            with self.subTest(arguments=arguments):
                self.assert_rejected_before_install(self.run_installer(*arguments, version=False))


if __name__ == "__main__":
    unittest.main()
