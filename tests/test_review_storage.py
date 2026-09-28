from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from research_store.config import load_config
from research_store.imports import import_pdf_path
from research_store.operations import recover_document_operation
from research_store.sources import add_sources, initialize_config
from research_store.state import LibraryState, SCHEMA_VERSION
from research_store.sync import (
    ConversionResult, complete_reviews, delete_document, intake_receipts,
    render_review_pages, review_snapshot, sync_library,
)
from test_sync import make_project, write_text_pdf


def convert(_):
    return ConversionResult("<!-- page: 1 -->\n\nStored evidence.\n", {1: ["table"]})


class ReviewStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = make_project(self.base / "store")
        self.config_path = initialize_config(self.root / ".research-store/config.toml")
        self.config = load_config(self.config_path)
        self.source = self.base / "source"
        self.source.mkdir()
        self.pdf = self.source / "paper.pdf"
        write_text_pdf(self.pdf, "Original evidence")

    def imported(self, *, request_id="request-a", item_id="item-1"):
        result = import_pdf_path(self.config, self.pdf, request_id=request_id, item_id=item_id)
        stats = sync_library(self.config, convert, imported_document=result["document_key"], request_id=request_id, item_id=item_id)
        return result, stats.committed_documents[0]

    def child(self, script):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        return subprocess.run([sys.executable, "-B", "-c", script, str(self.config_path)], env=environment, capture_output=True, text=True)

    def lifecycle_two_items(self, *, attach_first=True):
        from research_store.review_lifecycle import Lifecycle
        second = self.source / "second.pdf"
        write_text_pdf(second, "Second original evidence")
        specification = {"items": [{"item_id": "a", "attachment": str(self.pdf)},
                                   {"item_id": "b", "attachment": str(second)}]}
        engine = Lifecycle(self.root)
        expires = int(time.time()) + 600
        key = f"vr2.{expires}.two-item-intake-key"
        receipt = engine.begin(key, expires, specification)
        rid = receipt["request_id"]
        imported = []
        for item, path in (("a", self.pdf), ("b", second)):
            stored = import_pdf_path(self.config, path, request_id=rid, item_id=item)
            document = sync_library(self.config, convert, imported_document=stored["document_key"], request_id=rid, item_id=item).committed_documents[0]
            if item != "a" or attach_first:
                engine.attach(rid, item, document)
            imported.append((stored, document))
        return engine, specification, key, expires, rid, imported

    def test_incarnation_stable_across_sync_and_changes_after_delete_reimport(self):
        imported, first = self.imported()
        again = sync_library(self.config, convert, imported_document=imported["document_key"])
        self.assertEqual(again.committed_documents[0]["incarnation"], first["incarnation"])
        original = self.pdf.read_bytes()
        delete_document(self.config, imported["document_key"])
        self.assertFalse(Path(imported["stored_pdf"]).exists())
        self.assertEqual(review_snapshot(self.config), [])
        self.assertEqual(self.pdf.read_bytes(), original)
        _, second = self.imported(request_id="request-b")
        self.assertNotEqual(first["incarnation"], second["incarnation"])
        self.assertEqual(first["sha256"], second["sha256"])

    def test_ordinary_sync_keeps_external_deletion_excluded_until_reregistration(self):
        source = add_sources(self.config_path, [self.source])[0]
        self.config = load_config(self.config_path)
        first = sync_library(self.config, convert).committed_documents[0]
        before = self.pdf.read_bytes()
        delete_document(self.config, first["document_key"])
        self.assertEqual(sync_library(self.config, convert).committed_documents, [])
        self.assertEqual(self.pdf.read_bytes(), before)
        add_sources(self.config_path, [self.source])
        second = sync_library(load_config(self.config_path), convert).committed_documents[0]
        self.assertEqual(second["document_key"], f"{source.id}:paper.pdf")
        self.assertNotEqual(first["incarnation"], second["incarnation"])

    def test_inflight_sync_cannot_resurrect_deleted_document(self):
        add_sources(self.config_path, [self.source])
        self.config = load_config(self.config_path)
        first = sync_library(self.config, convert).committed_documents[0]
        write_text_pdf(self.pdf, "Changed original evidence")
        def delete_while_converting(path):
            delete_document(self.config, first["document_key"])
            return convert(path)
        result = sync_library(self.config, delete_while_converting)
        self.assertEqual(result.committed_documents, [])
        self.assertEqual(review_snapshot(self.config), [])
        self.assertTrue(self.pdf.exists())

    def test_intake_receipt_survives_original_disappearance(self):
        imported = import_pdf_path(self.config, self.pdf, request_id="request-a", item_id="item-1")
        self.pdf.unlink()
        stored = intake_receipts(self.config, "request-a")[0]
        self.assertTrue(stored["stored"])
        self.assertFalse(stored["committed"])
        result = sync_library(self.config, convert, imported_document=imported["document_key"], request_id="request-a", item_id="item-1")
        receipt = intake_receipts(self.config, "request-a")[0]
        self.assertTrue(receipt["committed"])
        self.assertEqual(receipt["incarnation"], result.committed_documents[0]["incarnation"])

    def test_unchanged_intake_gets_own_exact_committed_receipt(self):
        imported, first = self.imported()
        import_pdf_path(self.config, self.pdf, request_id="request-b", item_id="item-2")
        result = sync_library(self.config, convert, imported_document=imported["document_key"], request_id="request-b", item_id="item-2")
        self.assertEqual(result.unchanged, 1)
        self.assertEqual(result.committed_documents, [first])
        self.assertEqual(intake_receipts(self.config, "request-b")[0]["incarnation"], first["incarnation"])

    def test_same_intake_item_cannot_change_pdf(self):
        self.imported()
        write_text_pdf(self.pdf, "Other bytes")
        with self.assertRaisesRegex(ValueError, "다른 문서 버전"):
            import_pdf_path(self.config, self.pdf, request_id="request-a", item_id="item-1")
        self.assertEqual(len(review_snapshot(self.config)), 1)

    def test_snapshot_recovers_committed_intake_after_crash_at_markdown_write(self):
        imported = import_pdf_path(self.config, self.pdf, request_id="request-a", item_id="item-1")
        self.pdf.unlink()
        script = '''
import os, sys
from pathlib import Path
from research_store.config import load_config
from research_store.imports import imported_sources
from research_store.sync import sync_library, ConversionResult
import research_store.operations as operations
config = load_config(Path(sys.argv[1]))
source = imported_sources(config)[0]
original = operations.atomic_text
def stop_after_replace(path, text, root):
    original(path, text, root)
    os._exit(71)
operations.atomic_text = stop_after_replace
sync_library(config, lambda _: ConversionResult("evidence", {1: ["table"]}), imported_document=f"{source.id}:{source.original_name}", request_id="request-a", item_id="item-1")
'''
        stopped = self.child(script)
        self.assertEqual(stopped.returncode, 71, stopped.stderr)
        snapshot = review_snapshot(self.config)
        receipt = intake_receipts(self.config, "request-a")[0]
        self.assertTrue(receipt["committed"])
        self.assertEqual(receipt["document_key"], imported["document_key"])
        self.assertEqual(receipt["incarnation"], snapshot[0]["incarnation"])

    def test_receipt_is_durable_before_owned_copy_publication(self):
        script = '''
import os, sys
from pathlib import Path
from research_store.config import load_config
from research_store.imports import import_pdf_path
import research_store.imports as imports
original = imports.os.rename
def stop_after_publish(*args, **kwargs):
    original(*args, **kwargs)
    os._exit(72)
imports.os.rename = stop_after_publish
config = load_config(Path(sys.argv[1]))
import_pdf_path(config, config.root.parent / "source/paper.pdf", request_id="request-a", item_id="item-1")
'''
        stopped = self.child(script)
        self.assertEqual(stopped.returncode, 72, stopped.stderr)
        self.pdf.unlink()
        receipt = intake_receipts(self.config, "request-a")[0]
        self.assertTrue(receipt["stored"])
        self.assertFalse(receipt["committed"])

    def test_partial_deletion_recovers_without_touching_original(self):
        imported, document = self.imported()
        before = self.pdf.read_bytes()
        script = '''
import os, sys
from pathlib import Path
from research_store.config import load_config
from research_store.sync import delete_document, review_snapshot
import research_store.operations as operations
original = operations.unlink_owned_file
def stop_after_unlink(*args, **kwargs):
    original(*args, **kwargs)
    os._exit(73)
operations.unlink_owned_file = stop_after_unlink
config = load_config(Path(sys.argv[1]))
delete_document(config, review_snapshot(config)[0]["document_key"])
'''
        stopped = self.child(script)
        self.assertEqual(stopped.returncode, 73, stopped.stderr)
        self.assertEqual(review_snapshot(self.config), [])
        self.assertFalse(Path(imported["stored_pdf"]).exists())
        self.assertEqual(self.pdf.read_bytes(), before)
        self.assertTrue(delete_document(self.config, document["document_key"])["deleted"])

    def test_deletion_rejects_replaced_hardlink_and_retains_original(self):
        imported, document = self.imported()
        output = self.root / document["output_path"]
        output.unlink()
        output.hardlink_to(self.pdf)
        before = self.pdf.read_bytes()
        with self.assertRaises(ValueError):
            delete_document(self.config, document["document_key"])
        self.assertEqual(self.pdf.read_bytes(), before)
        self.assertTrue(Path(imported["stored_pdf"]).exists())

    def test_rejected_fence_cannot_prepare_a_journal_or_change_evidence(self):
        _, document = self.imported()
        output = self.root / document["output_path"]
        before = output.read_bytes()
        fence = {"review_id": "review-a", "generation": 1, "incarnation": document["incarnation"], "sha256": document["sha256"], "page": 1, "execution_id": "execution-a", "document_key": document["document_key"]}
        with patch("research_store.review_lifecycle.validate_result", side_effect=ValueError("revoked")) as validate, patch.object(LibraryState, "prepare_document_operation") as prepare:
            with self.assertRaisesRegex(ValueError, "revoked"):
                complete_reviews(self.config, document["document_key"], [1], expected_sha256=document["sha256"], status="verified", reviewer_model="test-model", notes=None, visual_notes="Verified table", fence=fence)
            validate.assert_called_once()
            prepare.assert_not_called()
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(review_snapshot(self.config)[0]["pages"], {"1": "pending"})

    def test_v4_schema_migration_persists_unique_incarnation(self):
        _, document = self.imported()
        with sqlite3.connect(self.config.state) as database:
            database.execute("UPDATE metadata SET value = '4' WHERE key = 'schema_version'")
            database.execute("ALTER TABLE documents DROP COLUMN incarnation")
            database.execute("ALTER TABLE document_operations DROP COLUMN intake_receipt_json")
        with LibraryState(self.config.state, self.root) as state:
            incarnation = state.get_document(document["document_key"])["incarnation"]
            self.assertTrue(incarnation)
            self.assertEqual(state.get_metadata("schema_version"), str(SCHEMA_VERSION))
        with LibraryState(self.config.state, self.root, read_only=True) as state:
            self.assertEqual(state.get_document(document["document_key"])["incarnation"], incarnation)

    def test_snapshot_requires_the_current_verified_note(self):
        _, document = self.imported()
        complete_reviews(self.config, document["document_key"], [1], expected_sha256=document["sha256"], status="verified", reviewer_model="test-model", notes=None, visual_notes="Verified table")
        self.assertEqual(review_snapshot(self.config)[0]["pages"], {"1": "verified"})
        output = self.root / document["output_path"]
        output.write_text(output.read_text().replace("visual-review-status: verified", "visual-review-status: needs_review"))
        self.assertEqual(review_snapshot(self.config)[0]["pages"], {"1": "needs_review"})
        output.unlink()
        self.assertEqual(review_snapshot(self.config)[0]["pages"], {"1": "needs_review"})

    def test_execution_images_have_a_durable_manifest_with_exact_inodes(self):
        _, document = self.imported()
        execution_id = "a" * 32
        rendered = render_review_pages(self.config, document["document_key"], [1], dpi=120, execution_id=execution_id)
        image = rendered.paths[0]
        manifest = json.loads((image.parent / "owned-manifest.json").read_text())
        self.assertEqual(manifest["execution_id"], execution_id)
        self.assertEqual(manifest["directory"]["inode"], image.parent.stat().st_ino)
        self.assertEqual(manifest["files"], [{"path": image.relative_to(self.root).as_posix(), "device": image.stat().st_dev, "inode": image.stat().st_ino}])
        self.assertGreater(image.stat().st_size, 0)
        with self.assertRaises(FileExistsError):
            render_review_pages(self.config, document["document_key"], [1], dpi=120, execution_id=execution_id)

    def test_receipt_cleanup_removes_only_the_expired_request(self):
        self.imported()
        self.imported(request_id="request-b")
        from research_store.locking import conversation_lock
        from research_store.sync import delete_intake_receipts_locked
        with conversation_lock(self.root):
            delete_intake_receipts_locked(self.config, "request-a")
        self.assertEqual(intake_receipts(self.config, "request-a"), [])
        self.assertEqual(len(intake_receipts(self.config, "request-b")), 1)
        self.assertEqual(len(review_snapshot(self.config)), 1)

    def test_source_intake_is_exact_and_commits_one_receipt_per_document(self):
        write_text_pdf(self.source / "second.pdf", "Second evidence")
        other = self.base / "other"
        other.mkdir()
        write_text_pdf(other / "unrequested.pdf", "Outside the requested source")
        selected, _ = add_sources(self.config_path, [self.source, other])
        self.config = load_config(self.config_path)
        result = sync_library(self.config, convert, source_ids=[selected.id], request_id="request-a", item_id="source-1")
        self.assertEqual(result.converted, 2)
        self.assertEqual(len(result.committed_documents), 2)
        receipts = intake_receipts(self.config, "request-a")
        self.assertEqual(len(receipts), 2)
        self.assertTrue(all(receipt["committed"] for receipt in receipts))
        self.assertTrue(all(receipt["parent_item_id"] == "source-1" for receipt in receipts))
        self.assertEqual({doc["receipt_item_id"] for doc in result.committed_documents}, {receipt["item_id"] for receipt in receipts})
        self.assertFalse(any("unrequested" in doc["document_key"] for doc in review_snapshot(self.config)))
        unchanged = sync_library(self.config, convert, source_ids=[selected.id], request_id="request-b", item_id="source-1")
        self.assertEqual(unchanged.unchanged, 2)
        self.assertTrue(all(receipt["committed"] for receipt in intake_receipts(self.config, "request-b")))

    def test_same_source_intake_rejects_a_changed_version_before_journal_prepare(self):
        selected = add_sources(self.config_path, [self.source])[0]
        self.config = load_config(self.config_path)
        first = sync_library(self.config, convert, source_ids=[selected.id], request_id="request-a", item_id="source-1")
        write_text_pdf(self.pdf, "Changed source version")
        with patch.object(LibraryState, "prepare_document_operation") as prepare:
            changed = sync_library(self.config, convert, source_ids=[selected.id], request_id="request-a", item_id="source-1")
            prepare.assert_not_called()
        self.assertEqual(changed.failed, 1)
        self.assertEqual(changed.committed_documents, [])
        self.assertEqual(review_snapshot(self.config)[0]["sha256"], first.committed_documents[0]["sha256"])

    def test_page_fence_is_atomic_with_repeated_outcome_and_survives_reopen(self):
        _, document = self.imported()
        base_fence = {"review_id": "review-a", "generation": 1, "incarnation": document["incarnation"], "sha256": document["sha256"], "page": 1, "execution_id": "execution-a", "document_key": document["document_key"]}
        for execution in ("execution-a", "execution-b"):
            fence = {**base_fence, "execution_id": execution}
            with patch("research_store.review_lifecycle.validate_result"):
                complete_reviews(self.config, document["document_key"], [1], expected_sha256=document["sha256"], status="needs_review", reviewer_model="test-model", notes="unclear", visual_notes="Unresolved table", fence=fence)
            snapshot = review_snapshot(self.config)[0]
            self.assertEqual(snapshot["pages"], {"1": "needs_review"})
            self.assertEqual(snapshot["page_fences"], {"1": fence})

    def test_frozen_source_manifest_ignores_new_files_and_rejects_changed_bytes(self):
        selected = add_sources(self.config_path, [self.source])[0]
        self.config = load_config(self.config_path)
        key = f"{selected.id}:paper.pdf"
        expected = {key: hashlib.sha256(self.pdf.read_bytes()).hexdigest()}
        write_text_pdf(self.source / "later.pdf", "A later PDF")
        result = sync_library(self.config, convert, source_ids=[selected.id], expected_documents=expected)
        self.assertEqual([document["document_key"] for document in result.committed_documents], [key])
        sync_library(self.config, convert, source_ids=[selected.id])
        write_text_pdf(self.pdf, "Changed original")
        changed = sync_library(self.config, convert, source_ids=[selected.id], expected_documents=expected)
        self.assertEqual(changed.failed, 1)
        self.assertEqual(changed.committed_documents, [])
        empty = sync_library(self.config, convert, source_ids=[selected.id], expected_documents={})
        self.assertEqual(empty.committed_documents, [])
        self.assertEqual(empty.discovered, 0)
        with LibraryState(self.config.state, self.root, read_only=True) as state:
            self.assertEqual(state.get_document(f"{selected.id}:later.pdf")["present"], 1)

    def test_deleted_attachment_cannot_reimport_on_same_two_item_request(self):
        engine, specification, key, expires, rid, imported = self.lifecycle_two_items()
        original = self.pdf.read_bytes()
        first, document = imported[0]
        self.assertTrue(engine.delete_document(first["document_key"])["deleted"])
        retry = engine.begin(key, expires, specification)
        self.assertEqual(retry["request_id"], rid)
        self.assertEqual(retry["items"]["a"]["state"], "deleted")
        self.assertEqual(retry["items"]["b"]["state"], "linked")
        with self.assertRaisesRegex(ValueError, "삭제되었거나"):
            import_pdf_path(self.config, self.pdf, request_id=rid, item_id="a")
        self.assertFalse(Path(first["stored_pdf"]).exists())
        self.assertTrue(Path(imported[1][0]["stored_pdf"]).exists())
        self.assertEqual(self.pdf.read_bytes(), original)
        with LibraryState(self.config.state, self.root, read_only=True) as state:
            self.assertTrue(state.is_document_excluded(first["document_key"]))
        fresh = engine.begin(f"vr2.{expires}.new-explicit-import-key", expires,
                             {"items": [specification["items"][0]]})
        new = import_pdf_path(self.config, self.pdf, request_id=fresh["request_id"], item_id="a")
        restored = sync_library(self.config, convert, imported_document=new["document_key"], request_id=fresh["request_id"], item_id="a").committed_documents[0]
        self.assertNotEqual(restored["incarnation"], document["incarnation"])

    def test_delete_after_preparation_before_publication_revokes_import(self):
        engine, specification, key, expires, rid, imported = self.lifecycle_two_items()
        prepared = engine.begin(key, expires, specification)
        self.assertNotEqual(prepared["items"]["a"]["state"], "deleted")
        first = imported[0][0]
        from research_store import imports
        original_validate = imports._validate_pdf
        original = self.pdf.read_bytes()
        def delete_after_copy_is_read(path):
            original_validate(path)
            self.assertTrue(engine.delete_document(first["document_key"])["deleted"])
        with patch.object(imports, "_validate_pdf", side_effect=delete_after_copy_is_read):
            with self.assertRaisesRegex(ValueError, "삭제되었거나"):
                import_pdf_path(self.config, self.pdf, request_id=rid, item_id="a")
        self.assertFalse(Path(first["stored_pdf"]).exists())
        self.assertTrue(Path(imported[1][0]["stored_pdf"]).exists())
        self.assertEqual(list((self.root / ".research-store/imports").glob(".pending-*")), [])
        self.assertEqual(self.pdf.read_bytes(), original)
        with LibraryState(self.config.state, self.root, read_only=True) as state:
            self.assertTrue(state.is_document_excluded(first["document_key"]))
        self.assertEqual(engine.status(rid)["items"]["a"]["state"], "deleted")

    def test_delete_after_text_commit_before_link_revokes_pending_intake(self):
        engine, specification, key, expires, rid, imported = self.lifecycle_two_items(attach_first=False)
        self.assertEqual(engine.status(rid)["items"]["a"]["state"], "pending")
        first = imported[0][0]
        self.assertTrue(engine.delete_document(first["document_key"])["deleted"])
        retry = engine.begin(key, expires, specification)
        self.assertEqual(retry["items"]["a"]["state"], "deleted")
        self.assertEqual(retry["items"]["b"]["state"], "linked")
        with self.assertRaisesRegex(ValueError, "삭제되었거나"):
            import_pdf_path(self.config, self.pdf, request_id=rid, item_id="a")
        self.assertFalse(Path(first["stored_pdf"]).exists())
        self.assertTrue(Path(imported[1][0]["stored_pdf"]).exists())


if __name__ == "__main__":
    unittest.main()
