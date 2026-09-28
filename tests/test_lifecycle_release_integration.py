"""Exercise shipped lifecycle entry points without a model or a real user home."""
from __future__ import annotations

import io
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import venv


PROJECT = Path(__file__).resolve().parents[1]


class LifecycleReleaseIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="review-bundle-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.home = self.base / "disposable home"
        self.home.mkdir()
        self.unrelated = self.base / "unrelated working directory"
        self.unrelated.mkdir()

        # Use only the same explicit product manifest consumed by the release
        # workflow. Repository-relative imports must not rescue missing files.
        archive_path = self.base / "runtime.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for line in (PROJECT / "packaging/runtime-files.txt").read_text().splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                fields = line.split()
                source = PROJECT / fields[0]
                content = source.read_bytes()
                member = tarfile.TarInfo("research-agent/" + fields[-1])
                member.mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        with tarfile.open(archive_path) as archive:
            archive.extractall(self.home, filter="data")
        self.root = self.home / "research-agent"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(self.root / ".venv")
        self.python = self.root / ".venv/bin/python"
        site = subprocess.check_output(
            [str(self.python), "-I", "-c", "import sysconfig;print(sysconfig.get_path('purelib'))"],
            text=True,
        ).strip()
        dependencies = [p for p in sys.path if Path(p).name in {"site-packages", "dist-packages"}]
        (Path(site) / "test-runtime.pth").write_text(
            "\n".join([str(self.root / "src"), *dependencies]) + "\n"
        )
        console = self.root / ".venv/bin/research-store"
        console.write_text(
            "#!/bin/sh\nexec " + "'" + str(self.python).replace("'", "'\\''")
            + "' -B -c 'from research_store.cli import main; main()' \"$@\"\n"
        )
        console.chmod(0o755)

        binary = self.base / "fake bin"
        binary.mkdir()
        self.calls = self.base / "sandbox-calls.jsonl"
        fake = binary / "codex"
        fake.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "if not args or args[0] != 'sandbox' or '--' not in args:\n"
            "    raise SystemExit('A real model call is forbidden in this fixture')\n"
            "with Path(os.environ['TEST_REVIEW_CALLS']).open('a') as f:\n"
            "    f.write(json.dumps(args) + '\\n')\n"
            "command = args[args.index('--') + 1:]\n"
            "os.execv(command[0], command)\n"
        )
        fake.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(binary) + os.pathsep + os.environ["PATH"],
                        TEST_REVIEW_CALLS=str(self.calls), PYTHONDONTWRITEBYTECODE="1",
                        RESEARCH_AGENT_NOTIFICATIONS="0")
        for name in ("CODEX_HOME", "PYTHONPATH", "PYTHONHOME"):
            self.env.pop(name, None)
        registration = self.run_command(
            [str(self.python), "-I", "-B", str(self.root / "scripts/personal_registration.py"),
             "install", "--root", str(self.root), "--home", str(self.home)]
        )
        self.assertEqual(registration.returncode, 0, registration.stdout + registration.stderr)
        initialized = self.run_command([str(self.root / "research-store"), "init"])
        self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)
        self.public = self.home / ".agents/skills/research-library/scripts/research-review"

    def run_command(self, arguments: list[str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(arguments, cwd=self.unrelated, env=self.env, input=input_text,
                              capture_output=True, text=True, timeout=20, check=False)

    def test_public_status_loads_only_shipped_modules_with_isolated_python(self) -> None:
        result = self.run_command([str(self.public), "status"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIsInstance(json.loads(result.stdout), dict)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(len(calls), 1, calls)
        call = calls[0]
        self.assertEqual(call[call.index("-P") + 1], "research-review-worker")
        invocation = call[call.index("--") + 1:]
        self.assertIn("-I", invocation)
        self.assertIn("-S", invocation)
        self.assertIn("-B", invocation)
        self.assertFalse((self.root / "tests").exists())

    def test_private_entry_points_are_rejected_before_sandbox_or_model_launch(self) -> None:
        for private in ("--worker", "--launch-notifier", "--notifier"):
            with self.subTest(private=private):
                result = self.run_command([str(self.public), private])
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_library_hold_survives_fresh_controller_invocation(self) -> None:
        held = self.run_command([str(self.public), "pause", "--library"])
        self.assertEqual(held.returncode, 0, held.stdout + held.stderr)
        later = self.run_command([str(self.public), "status"])
        self.assertEqual(later.returncode, 0, later.stdout + later.stderr)
        self.assertTrue(json.loads(later.stdout)["global_hold"])
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(len(calls), 2, calls)

    def test_foreign_owner_rejected_without_starting_controller(self) -> None:
        marker = self.home / ".codex/research-library-sandbox/.research-agent-owner"
        marker.write_text("# research-agent-registration-v1\n# research-agent-root: /wrong-owner\n")
        result = self.run_command([str(self.public), "status"])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_shipped_host_bridge_imports_two_attachments_under_persistent_hold(self) -> None:
        from pypdf import PdfWriter
        sources = self.base / "original PDFs"
        sources.mkdir()
        items = []
        originals = {}
        for index in (1, 2):
            path = sources / f"attachment {index}.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.add_metadata({"/Title": f"Disposable fixture {index}"})
            writer.write(path)
            originals[path] = hashlib.sha256(path.read_bytes()).hexdigest()
            items.append({"item_id": f"item-{index}", "attachment": str(path)})
        hold = self.run_command([str(self.public), "pause", "--library"])
        self.assertEqual(hold.returncode, 0, hold.stderr)
        key = self.run_command([str(self.public), "key"])
        self.assertEqual(key.returncode, 0, key.stderr)
        identity = json.loads(key.stdout)
        result = self.run_command([str(self.public), "submit", "--key", identity["key"],
            "--key-expires-at", str(identity["key_expires_at"]), "--spec-stdin"],
            json.dumps({"items": items}) + "\n__RESEARCH_STORE_STDIN_END__\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual({i["state"] for i in receipt["items"].values()}, {"linked"}, receipt)
        self.assertEqual(len(receipt["links"]), 2)
        self.assertTrue(receipt["global_hold"])
        self.assertIsNone(receipt["token_usage"])
        for path, digest in originals.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertEqual(sorted(p.name for p in sources.iterdir()), ["attachment 1.pdf", "attachment 2.pdf"])
        status = self.run_command([str(self.public), "status", "--request", receipt["request_id"]])
        self.assertEqual(status.returncode, 0, status.stderr)
        stored = json.loads(status.stdout)
        self.assertEqual(stored["state"], "held")
        self.assertEqual(stored["usage"]["page_attempts"], 0)

    def test_public_source_add_manages_only_confirmed_and_reselected_folders_under_hold(self) -> None:
        from pypdf import PdfWriter
        sources = self.base / "read-only source fixtures"
        sources.mkdir()
        folders = [sources / name for name in ("선택 A", "selected B", "unselected")]
        for index, folder in enumerate(folders, 1):
            folder.mkdir()
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.add_metadata({"/Title": f"Source selection fixture {index}"})
            writer.write(folder / f"paper {index}.pdf")

        def originals_snapshot():
            return {path.relative_to(sources).as_posix(): (
                path.stat().st_ino, path.stat().st_mode, path.stat().st_mtime_ns,
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            ) for path in sources.rglob("*")}

        before = originals_snapshot()
        # The root primitive only registers this unrelated source. Public
        # confirmation below must not turn that registration into intake scope.
        unrelated = self.run_command([str(self.root / "research-store"),
                                      "source-add", str(folders[2])])
        self.assertEqual(unrelated.returncode, 0, unrelated.stdout + unrelated.stderr)
        unrelated_id = json.loads(unrelated.stdout)["selected"][0]["id"]
        hold = self.run_command([str(self.public), "pause", "--library"])
        self.assertEqual(hold.returncode, 0, hold.stdout + hold.stderr)
        public_store = self.home / ".agents/skills/research-library/scripts/research-store"
        first = self.run_command([str(public_store), "source-add", *map(str, folders[:2])])
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        receipt = json.loads(first.stdout)
        self.assertEqual(receipt["registration"], "registered")
        self.assertEqual(receipt["processing"]["state"], "submitted")
        self.assertEqual([row["path"] for row in receipt["selected"]], list(map(str, folders[:2])))
        self.assertEqual(len(receipt["added"]), 2)
        selected_ids = {row["id"] for row in receipt["selected"]}
        self.assertNotIn(unrelated_id, selected_ids)
        self.assertEqual({item["source_id"] for item in receipt["processing"]["retry"]["specification"]["items"]}, selected_ids)

        def stored_versions():
            result = self.run_command([str(self.root / "research-store"), "review-snapshot"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return {document["document_key"]: (document["sha256"], document["incarnation"])
                    for document in json.loads(result.stdout)}

        versions = stored_versions()
        self.assertEqual(len(versions), 2)
        self.assertEqual({key.split(":", 1)[0] for key in versions}, selected_ids)
        first_request = receipt["processing"]["request"]
        self.assertEqual(first_request["state"], "held")
        self.assertTrue(first_request["global_hold"])
        self.assertEqual(first_request["usage"]["page_attempts"], 0)
        self.assertEqual(len(first_request["links"]), 2)

        # Reselection is a new exact intent even when registration adds nothing.
        repeated = self.run_command([str(public_store), "source-add", "--",
                                     str(folders[1]), str(folders[0]), str(folders[1])])
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        again = json.loads(repeated.stdout)
        self.assertEqual(again["added"], [])
        self.assertEqual([row["path"] for row in again["selected"]],
                         [str(folders[1]), str(folders[0])])
        self.assertEqual({row["id"] for row in again["selected"]}, selected_ids)
        self.assertEqual(again["processing"]["state"], "submitted")
        second_request = again["processing"]["request"]
        self.assertNotEqual(first_request["request_id"], second_request["request_id"])
        self.assertEqual(second_request["state"], "held")
        self.assertEqual(second_request["usage"]["page_attempts"], 0)
        self.assertEqual(stored_versions(), versions)
        self.assertEqual(len(list((self.root / "knowledge/documents").rglob("*.md"))), 2)
        status = self.run_command([str(self.public), "status"])
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        library = json.loads(status.stdout)
        self.assertTrue(library["global_hold"])
        self.assertEqual(library["library_usage"]["page_attempts"], 0)
        self.assertIsNone(library["execution"])
        self.assertEqual(originals_snapshot(), before)


if __name__ == "__main__":
    unittest.main()
