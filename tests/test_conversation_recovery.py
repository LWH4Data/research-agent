from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from research_store.config import load_config
from research_store.conversations import (
    get_conversation,
    list_conversations,
    save_conversation,
)
from research_store.safety import PROJECT_MARKER_CONTENT


def make_project(path: Path) -> Path:
    path.mkdir()
    (path / ".research-agent-root").write_text(
        PROJECT_MARKER_CONTENT + "\n", encoding="utf-8"
    )
    return path.resolve()


def write_config(project: Path, source: Path) -> Path:
    config_path = project / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[store]",
                'documents = "knowledge/documents"',
                'conversations = "knowledge/conversations"',
                'assets = "knowledge/assets"',
                'state = ".research-store/library.sqlite"',
                'temporary = ".research-store/tmp"',
                "",
                "[[sources]]",
                'id = "papers"',
                f"path = {json.dumps(str(source))}",
                'kind = "directory"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def conversation_payload(marker: str = "BASE") -> dict[str, object]:
    return {
        "title": f"복구 테스트 {marker}",
        "created_at": "2026-09-21T10:00:00+09:00",
        "scope": "current-topic",
        "capture_status": "complete",
        "summary": f"복구 테스트 요약 {marker}",
        "tags": ["recovery"],
        "aliases": ["crash recovery"],
        "user_points": [f"사용자 메모 {marker}"],
        "decisions": ["저널로 완료한다"],
        "unverified": [],
        "open_questions": [],
        "related_documents": [],
        "transcript": [
            {"role": "user", "content": f"원문 {marker}"},
            {"role": "assistant", "content": "원문을 보존합니다."},
        ],
    }


def update_payload(marker: str) -> dict[str, object]:
    return {
        "title": f"수정된 제목 {marker}",
        "summary": f"수정된 요약 {marker}",
        "tags": ["updated", marker],
        "aliases": [f"alias {marker}"],
        "user_points": [f"수정된 메모 {marker}"],
        "decisions": ["승인된 수정을 끝까지 완료한다"],
        "unverified": [],
        "open_questions": [],
        "related_documents": [],
    }


class ConversationRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        temporary_root = Path(self.temporary.name)
        self.source = temporary_root / "source"
        self.source.mkdir()
        self.source_pdf = self.source / "original.pdf"
        self.source_pdf.write_bytes(b"read-only-original")
        self.source_before = self.source_pdf.read_bytes()
        self.project = make_project(temporary_root / "agent")
        self.config_path = write_config(self.project, self.source)
        self.config = load_config(self.config_path)

    def run_child(
        self, source: str, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPYCACHEPREFIX"] = str(
            Path(self.temporary.name) / "pycache"
        )
        result = subprocess.run(
            [sys.executable, "-c", source, *arguments],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(self.source_pdf.read_bytes(), self.source_before)
        return result

    def pending_count(self) -> int:
        with sqlite3.connect(self.config.state) as database:
            return int(
                database.execute(
                    "SELECT COUNT(*) FROM conversation_operations"
                ).fetchone()[0]
            )

    def database_revision(self, conversation_id: str) -> int | None:
        with sqlite3.connect(self.config.state) as database:
            row = database.execute(
                "SELECT revision FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return None if row is None else int(row[0])

    def interrupt_update_before_file_write(
        self, conversation_id: str, marker: str
    ) -> subprocess.CompletedProcess[str]:
        return self.run_child(
            """
import json, os, sys
from pathlib import Path
import research_store.conversations as module
from research_store.config import load_config

def crash_before_write(*args, **kwargs):
    os._exit(74)
module.atomic_text = crash_before_write
module.update_conversation(
    load_config(Path(sys.argv[1])), sys.argv[2], json.loads(sys.argv[3]),
    expected_revision=1,
)
""",
            str(self.config_path),
            conversation_id,
            json.dumps(update_payload(marker), ensure_ascii=False),
        )

    def test_interrupted_save_rolls_forward_on_next_read(self) -> None:
        child = self.run_child(
            """
import json, os, sys
from pathlib import Path
import research_store.conversations as module
from research_store.config import load_config

real_atomic_text = module.atomic_text
def crash_after_write(*args, **kwargs):
    real_atomic_text(*args, **kwargs)
    os._exit(71)
module.atomic_text = crash_after_write
module.save_conversation(load_config(Path(sys.argv[1])), json.loads(sys.argv[2]))
""",
            str(self.config_path),
            json.dumps(conversation_payload("SAVE_CRASH"), ensure_ascii=False),
        )
        self.assertEqual(child.returncode, 71, child.stderr)
        self.assertEqual(self.pending_count(), 1)
        with sqlite3.connect(self.config.state) as database:
            self.assertEqual(
                database.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
                0,
            )

        records = list_conversations(self.config)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["revision"], 1)
        self.assertIn(
            "SAVE_CRASH",
            (self.project / records[0]["path"]).read_text(encoding="utf-8"),
        )
        self.assertEqual(self.pending_count(), 0)
        self.assertEqual(self.source_pdf.read_bytes(), self.source_before)

    def test_interrupted_update_rolls_forward_on_next_get(self) -> None:
        output = save_conversation(self.config, conversation_payload())
        conversation_id = str(list_conversations(self.config)[0]["conversation_id"])
        child = self.run_child(
            """
import json, os, sys
from pathlib import Path
import research_store.conversations as module
from research_store.config import load_config

real_atomic_text = module.atomic_text
def crash_after_write(*args, **kwargs):
    real_atomic_text(*args, **kwargs)
    os._exit(72)
module.atomic_text = crash_after_write
module.update_conversation(
    load_config(Path(sys.argv[1])), sys.argv[2], json.loads(sys.argv[3]),
    expected_revision=1,
)
""",
            str(self.config_path),
            conversation_id,
            json.dumps(update_payload("UPDATE_CRASH"), ensure_ascii=False),
        )
        self.assertEqual(child.returncode, 72, child.stderr)
        self.assertEqual(self.pending_count(), 1)
        self.assertEqual(self.database_revision(conversation_id), 1)
        self.assertIn("UPDATE_CRASH", output.read_text(encoding="utf-8"))

        recovered = get_conversation(self.config, conversation_id)

        self.assertEqual(recovered["revision"], 2)
        self.assertEqual(
            recovered["editable"]["summary"], "수정된 요약 UPDATE_CRASH"
        )
        self.assertEqual(self.database_revision(conversation_id), 2)
        self.assertEqual(self.pending_count(), 0)
        self.assertEqual(self.source_pdf.read_bytes(), self.source_before)

    def test_interrupted_delete_rolls_forward_on_next_list(self) -> None:
        output = save_conversation(self.config, conversation_payload())
        conversation_id = str(list_conversations(self.config)[0]["conversation_id"])
        child = self.run_child(
            """
import os, sys
from pathlib import Path
import research_store.conversations as module
from research_store.config import load_config

real_unlink = module.unlink_owned_file
def crash_after_unlink(*args, **kwargs):
    result = real_unlink(*args, **kwargs)
    os._exit(73)
module.unlink_owned_file = crash_after_unlink
module.delete_conversation(
    load_config(Path(sys.argv[1])), sys.argv[2], expected_revision=1
)
""",
            str(self.config_path),
            conversation_id,
        )
        self.assertEqual(child.returncode, 73, child.stderr)
        self.assertFalse(output.exists())
        self.assertEqual(self.pending_count(), 1)
        self.assertEqual(self.database_revision(conversation_id), 1)

        self.assertEqual(list_conversations(self.config), [])

        self.assertIsNone(self.database_revision(conversation_id))
        self.assertEqual(self.pending_count(), 0)
        self.assertEqual(self.source_pdf.read_bytes(), self.source_before)

    def test_recovery_refuses_unexpected_markdown_instead_of_overwriting_it(self) -> None:
        output = save_conversation(self.config, conversation_payload())
        conversation_id = str(list_conversations(self.config)[0]["conversation_id"])
        child = self.interrupt_update_before_file_write(
            conversation_id, "FILE_CONFLICT"
        )
        self.assertEqual(child.returncode, 74, child.stderr)
        tampered = output.read_bytes() + b"\nUNEXPECTED_EXTERNAL_EDIT\n"
        output.write_bytes(tampered)

        with self.assertRaisesRegex(RuntimeError, "예상하지 못한 내용"):
            get_conversation(self.config, conversation_id)

        self.assertEqual(output.read_bytes(), tampered)
        self.assertEqual(self.database_revision(conversation_id), 1)
        self.assertEqual(self.pending_count(), 1)

    def test_recovery_refuses_unexpected_database_record(self) -> None:
        output = save_conversation(self.config, conversation_payload())
        original = output.read_bytes()
        conversation_id = str(list_conversations(self.config)[0]["conversation_id"])
        child = self.interrupt_update_before_file_write(
            conversation_id, "DATABASE_CONFLICT"
        )
        self.assertEqual(child.returncode, 74, child.stderr)
        with sqlite3.connect(self.config.state) as database:
            database.execute(
                "UPDATE conversations SET title = ? WHERE conversation_id = ?",
                ("unexpected database edit", conversation_id),
            )

        with self.assertRaisesRegex(RuntimeError, "SQLite 레코드.*예상하지 못한"):
            get_conversation(self.config, conversation_id)

        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(self.database_revision(conversation_id), 1)
        self.assertEqual(self.pending_count(), 1)

    def test_get_waits_for_in_progress_update_and_reads_complete_revision(self) -> None:
        save_conversation(self.config, conversation_payload())
        conversation_id = str(list_conversations(self.config)[0]["conversation_id"])
        ready = Path(self.temporary.name) / "file-written"
        release = Path(self.temporary.name) / "release"
        environment = os.environ.copy()
        environment["PYTHONPYCACHEPREFIX"] = str(
            Path(self.temporary.name) / "pycache"
        )
        updater = subprocess.Popen(
            [
                sys.executable,
                "-c",
                """
import json, sys, time
from pathlib import Path
import research_store.conversations as module
from research_store.config import load_config

real_atomic_text = module.atomic_text
ready, release = Path(sys.argv[4]), Path(sys.argv[5])
def pause_after_write(*args, **kwargs):
    real_atomic_text(*args, **kwargs)
    ready.write_text("ready", encoding="utf-8")
    while not release.exists():
        time.sleep(0.02)
module.atomic_text = pause_after_write
module.update_conversation(
    load_config(Path(sys.argv[1])), sys.argv[2], json.loads(sys.argv[3]),
    expected_revision=1,
)
""",
                str(self.config_path),
                conversation_id,
                json.dumps(update_payload("LOCK_WAIT"), ensure_ascii=False),
                str(ready),
                str(release),
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(lambda: updater.poll() is None and updater.kill())
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(ready.exists(), "updater did not reach the split-state window")

        getter = subprocess.Popen(
            [
                sys.executable,
                "-c",
                """
import json, sys
from pathlib import Path
from research_store.config import load_config
from research_store.conversations import get_conversation
print(json.dumps(get_conversation(load_config(Path(sys.argv[1])), sys.argv[2])))
""",
                str(self.config_path),
                conversation_id,
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(lambda: getter.poll() is None and getter.kill())
        time.sleep(0.25)
        self.assertIsNone(getter.poll(), "get observed the split state instead of waiting")

        release.write_text("release", encoding="utf-8")
        updater_stdout, updater_stderr = updater.communicate(timeout=5)
        self.assertEqual(updater.returncode, 0, updater_stdout + updater_stderr)
        getter_stdout, getter_stderr = getter.communicate(timeout=5)
        self.assertEqual(getter.returncode, 0, getter_stderr)
        received = json.loads(getter_stdout)
        self.assertEqual(received["revision"], 2)
        self.assertEqual(received["editable"]["summary"], "수정된 요약 LOCK_WAIT")
        self.assertEqual(self.source_pdf.read_bytes(), self.source_before)

    def test_concurrent_same_revision_updates_allow_exactly_one(self) -> None:
        save_conversation(self.config, conversation_payload())
        conversation_id = str(list_conversations(self.config)[0]["conversation_id"])
        barrier = Path(self.temporary.name) / "go"
        environment = os.environ.copy()
        environment["PYTHONPYCACHEPREFIX"] = str(
            Path(self.temporary.name) / "pycache"
        )
        child_source = """
import json, sys, time
from pathlib import Path
from research_store.config import load_config
from research_store.conversations import update_conversation

while not Path(sys.argv[4]).exists():
    time.sleep(0.01)
try:
    result = update_conversation(
        load_config(Path(sys.argv[1])), sys.argv[2], json.loads(sys.argv[3]),
        expected_revision=1,
    )
except Exception as error:
    print(str(error), file=sys.stderr)
    raise SystemExit(2)
print(json.dumps(result))
"""
        children = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    child_source,
                    str(self.config_path),
                    conversation_id,
                    json.dumps(update_payload(marker), ensure_ascii=False),
                    str(barrier),
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for marker in ("RACER_A", "RACER_B")
        ]
        for child in children:
            self.addCleanup(lambda process=child: process.poll() is None and process.kill())
        barrier.write_text("go", encoding="utf-8")
        results = [child.communicate(timeout=8) for child in children]
        return_codes = [child.returncode for child in children]

        self.assertEqual(sorted(return_codes), [0, 2], results)
        rejected = results[return_codes.index(2)][1]
        self.assertIn("expected=1, current=2", rejected)
        final = get_conversation(self.config, conversation_id)
        self.assertEqual(final["revision"], 2)
        self.assertIn(
            final["editable"]["summary"],
            {"수정된 요약 RACER_A", "수정된 요약 RACER_B"},
        )
        self.assertEqual(self.pending_count(), 0)
        self.assertEqual(self.source_pdf.read_bytes(), self.source_before)


if __name__ == "__main__":
    unittest.main()
