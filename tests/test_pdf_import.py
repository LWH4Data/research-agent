from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from research_store.config import load_config
from research_store.imports import import_pdf, import_pdf_path, imported_sources
from research_store.search import search_library
from research_store.sources import add_sources, initialize_config, source_rows
from research_store.sync import complete_reviews, pending_reviews, render_review_pages, sync_library
from test_sync import make_project, tree_snapshot, write_text_pdf


class PDFImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = make_project(self.base / "store")
        self.config_path = initialize_config(self.root / ".research-store/config.toml")
        self.config = load_config(self.config_path)
        self.originals = self.base / "originals"
        self.originals.mkdir()
        self.pdf = self.originals / "Attention 한글.pdf"
        write_text_pdf(self.pdf, "Attention import evidence")
        self.before = tree_snapshot(self.originals)

    def cli(self, *args, input=None):
        return subprocess.run(
            [sys.executable, "-c", "from research_store.cli import main; main()",
             "--config", str(self.config_path), *map(str, args)],
            input=input, capture_output=True, check=False,
        )

    def test_path_import_preserves_original_and_does_not_register_location(self):
        result = import_pdf_path(self.config, self.pdf)
        self.assertTrue(result["stored"])
        self.assertFalse(result["duplicate"])
        self.assertEqual(Path(result["stored_pdf"]).read_bytes(), self.pdf.read_bytes())
        self.assertEqual(tree_snapshot(self.originals), self.before)
        self.assertEqual(source_rows(self.config_path), [])
        source = imported_sources(self.config)[0]
        self.assertEqual(source.origin_path, str(self.pdf))
        self.assertEqual(source.relative_path(source.path), Path(self.pdf.name))

    def test_attachment_disappears_before_sync_search_and_visual_review(self):
        result = import_pdf_path(self.config, self.pdf)
        self.pdf.unlink()  # Simulate the host deleting its attachment cache.
        stats = sync_library(self.config)
        self.assertEqual(stats.converted, 1)
        reviews = pending_reviews(self.config)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["document_key"], result["document_key"])
        self.assertEqual(reviews[0]["original_pdf"], result["stored_pdf"])
        rendered = render_review_pages(self.config, result["document_key"], dpi=120)
        self.assertEqual(len(rendered.paths), 1)
        self.assertTrue(rendered.paths[0].is_file())
        complete_reviews(self.config, result["document_key"], [1],
                         expected_sha256=rendered.sha256, status="verified",
                         reviewer_model="gpt-5.6-sol", notes=None,
                         visual_notes="Attention import evidence verified.")
        self.assertEqual(pending_reviews(self.config), [])
        search = search_library(self.config, ["Attention"], scope="pdf")
        self.assertIn("Attention", json.dumps(search, ensure_ascii=False))
        markdown = next(self.config.documents.rglob("*.md")).read_text()
        self.assertIn('source_kind: "imported-pdf"', markdown)
        self.assertIn('original_filename: "Attention 한글.pdf"', markdown)
        self.assertEqual(sync_library(self.config).unchanged, 1)

    def test_same_bytes_different_names_deduplicate_and_preserve_reviews(self):
        first = import_pdf_path(self.config, self.pdf)
        sync_library(self.config)
        markdown = next(self.config.documents.rglob("*.md"))
        before = markdown.read_bytes()
        duplicate = import_pdf(self.config, io.BytesIO(self.pdf.read_bytes()), name="renamed.pdf")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(first["document_key"], duplicate["document_key"])
        self.assertEqual(len(imported_sources(self.config)), 1)
        self.assertEqual(markdown.read_bytes(), before)
        self.assertEqual(sync_library(self.config).unchanged, 1)

    def test_changed_bytes_same_filename_create_separate_snapshot(self):
        first = import_pdf_path(self.config, self.pdf)
        write_text_pdf(self.pdf, "New attachment revision")
        second = import_pdf_path(self.config, self.pdf)
        self.assertNotEqual(first["document_key"], second["document_key"])
        self.assertEqual(len(imported_sources(self.config)), 2)
        self.assertEqual(sync_library(self.config).converted, 2)

    def test_external_source_and_import_remain_distinct(self):
        add_sources(self.config_path, [self.originals])
        config = load_config(self.config_path)
        import_pdf_path(config, self.pdf)
        self.assertEqual(sync_library(config).converted, 2)
        self.assertEqual(len(source_rows(self.config_path)), 1)
        with self.assertRaisesRegex(ValueError, "서로 포함"):
            add_sources(self.config_path, [self.root / ".research-store/imports"])
        self.assertEqual(tree_snapshot(self.originals), self.before)

    def test_targeted_sync_only_handles_requested_attachment(self):
        add_sources(self.config_path, [self.originals])
        config = load_config(self.config_path)
        first = import_pdf_path(config, self.pdf)
        other = self.base / "other.pdf"
        write_text_pdf(other, "Unrelated stored attachment")
        second = import_pdf_path(config, other)
        one = sync_library(config, imported_document=first["document_key"])
        self.assertEqual((one.registered_sources, one.discovered, one.converted), (1, 1, 1))
        self.assertEqual({r["document_key"] for r in pending_reviews(config)}, {first["document_key"]})
        two = self.cli("sync", "--imported-document", second["document_key"], "--progress", "off")
        self.assertEqual(two.returncode, 0, two.stderr)
        self.assertEqual(json.loads(two.stdout)["converted"], 1)
        # A targeted pass must not mark other documents missing.
        again = sync_library(config, imported_document=first["document_key"])
        self.assertEqual(again.missing, 0)
        self.assertEqual({r["document_key"] for r in pending_reviews(config)},
                         {first["document_key"], second["document_key"]})
        with self.assertRaisesRegex(ValueError, "정확한 문서 키"):
            sync_library(config, imported_document="unknown:paper.pdf")
        self.assertEqual(tree_snapshot(self.originals), self.before)

    def test_multiple_conversation_attachments_join_one_library_without_folder_registration(self):
        second = self.originals / "Laser cavity.pdf"
        third = self.originals / "Silicon waveguide.pdf"
        broken = self.originals / "broken.pdf"
        write_text_pdf(second, "Laser cavity batch evidence")
        write_text_pdf(third, "Silicon waveguide batch evidence")
        broken.write_bytes(b"%PDF-1.4\ninvalid\n")
        originals_before = tree_snapshot(self.originals)

        imported_keys = []
        for path in (self.pdf, broken, second, third):
            result = self.cli("import-pdf", path)
            if path == broken:
                self.assertNotEqual(result.returncode, 0)
                continue
            self.assertEqual(result.returncode, 0, result.stderr)
            imported_keys.append(json.loads(result.stdout)["document_key"])

        self.assertEqual(len(set(imported_keys)), 3)
        for key in imported_keys:
            result = self.cli("sync", "--imported-document", key,
                              "--progress", "off")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["converted"], 1)

        self.assertEqual(len(imported_sources(self.config)), 3)
        self.assertEqual(source_rows(self.config_path), [])
        self.assertEqual(len(pending_reviews(self.config)), 3)
        for term in ("Attention", "Laser", "Silicon"):
            results = search_library(self.config, [term], scope="pdf")
            self.assertIn(term, json.dumps(results, ensure_ascii=False))
        self.assertEqual(tree_snapshot(self.originals), originals_before)

    def test_invalid_empty_encrypted_and_oversized_inputs_leave_no_snapshot(self):
        from pypdf import PdfWriter
        encrypted = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("password")
        writer.write(encrypted)
        for data in (b"", b"not a pdf", b"%PDF-1.4\ninvalid", encrypted.getvalue()):
            with self.subTest(data=data[:20]):
                with self.assertRaises(ValueError):
                    import_pdf(self.config, io.BytesIO(data), name="bad.pdf")
                self.assertEqual(imported_sources(self.config), ())
        with mock.patch("research_store.imports.MAX_PDF_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "256 MiB"):
                import_pdf_path(self.config, self.pdf)
            with self.assertRaisesRegex(ValueError, "256 MiB"):
                import_pdf(self.config, io.BytesIO(b"x" * 11), name="large.pdf")
        self.assertEqual(tree_snapshot(self.originals), self.before)

    def test_invalid_filename_cannot_escape_owned_storage(self):
        for name in ("../escape.pdf", "/escape.pdf", "x\\escape.pdf", "no.txt", "\0.pdf"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                import_pdf(self.config, io.BytesIO(self.pdf.read_bytes()), name=name)
        self.assertFalse((self.root / ".research-store/imports").exists())

    def test_symlink_and_nonregular_input_rejected_without_mutation(self):
        link = self.base / "link.pdf"
        link.symlink_to(self.pdf)
        with self.assertRaises(ValueError):
            import_pdf_path(self.config, link)
        fifo = self.base / "pipe.pdf"
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            import_pdf_path(self.config, fifo)
        self.assertEqual(tree_snapshot(self.originals), self.before)

    def test_storage_symlink_never_writes_to_originals(self):
        (self.root / ".research-store/imports").symlink_to(self.originals)
        with self.assertRaises(ValueError):
            import_pdf_path(self.config, self.pdf)
        self.assertEqual(tree_snapshot(self.originals), self.before)

    def test_hardlinked_managed_copy_is_rejected(self):
        result = import_pdf_path(self.config, self.pdf)
        stored = Path(result["stored_pdf"])
        stored.unlink()
        os.link(self.pdf, stored)
        with self.assertRaisesRegex(ValueError, "하드 링크"):
            sync_library(self.config)
        self.assertEqual(tree_snapshot(self.originals), self.before)

    def test_same_size_corruption_is_not_reparsed_or_overwritten(self):
        result = import_pdf_path(self.config, self.pdf)
        sync_library(self.config)
        stored = Path(result["stored_pdf"])
        before_stat = stored.stat()
        stored.write_bytes(stored.read_bytes().replace(b"Attention", b"Corrupted"))
        os.utime(stored, ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
        self.assertEqual(sync_library(self.config).failed, 1)
        with self.assertRaisesRegex(ValueError, "변경"):
            render_review_pages(self.config, result["document_key"], [1], dpi=120)
        with self.assertRaisesRegex(ValueError, "변경"):
            import_pdf_path(self.config, self.pdf)

    def test_cli_path_and_binary_stdin(self):
        one = self.cli("import-pdf", self.pdf)
        self.assertEqual(one.returncode, 0, one.stderr)
        two = self.cli("import-pdf", "--stdin", "--name", "copy.pdf", input=self.pdf.read_bytes())
        self.assertEqual(two.returncode, 0, two.stderr)
        self.assertTrue(json.loads(two.stdout)["duplicate"])
        self.assertEqual(tree_snapshot(self.originals), self.before)
        for args in (("import-pdf",), ("import-pdf", "--stdin"),
                     ("import-pdf", self.pdf, "--stdin", "--name", "x.pdf")):
            self.assertNotEqual(self.cli(*args, input=b"").returncode, 0)

    def test_failed_publish_can_retry(self):
        with mock.patch("research_store.imports.os.rename", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                import_pdf_path(self.config, self.pdf)
        self.assertEqual(imported_sources(self.config), ())
        self.assertFalse(import_pdf_path(self.config, self.pdf)["duplicate"])

    def test_actual_interruption_before_and_after_publish_recovers(self):
        script = '''
import os, sys
from pathlib import Path
from research_store.config import load_config
from research_store.imports import import_pdf_path
import research_store.imports as module
real = module.os.rename
def stop(*args, **kwargs):
    if sys.argv[3] == "after": real(*args, **kwargs)
    os._exit(79)
module.os.rename = stop
import_pdf_path(load_config(Path(sys.argv[1])), Path(sys.argv[2]))
'''
        for when in ("before", "after"):
            with self.subTest(when=when):
                # Distinct content prevents the second case being a duplicate.
                write_text_pdf(self.pdf, "Interruption " + when)
                child = subprocess.run([sys.executable, "-c", script, str(self.config_path),
                                        str(self.pdf), when], capture_output=True)
                self.assertEqual(child.returncode, 79, child.stderr)
                result = import_pdf_path(self.config, self.pdf)
                self.assertEqual(result["duplicate"], when == "after")
                self.assertFalse(list((self.root / ".research-store/imports").glob(".pending-*")))
        self.assertEqual(sync_library(self.config).converted, 2)

    def test_concurrent_duplicate_imports_publish_one_snapshot(self):
        args = [sys.executable, "-c", "from research_store.cli import main; main()",
                "--config", str(self.config_path), "import-pdf", str(self.pdf)]
        children = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for _ in range(2)]
        results = []
        for child in children:
            stdout, stderr = child.communicate(timeout=15)
            self.assertEqual(child.returncode, 0, stderr)
            results.append(json.loads(stdout))
        self.assertEqual(sorted(item["duplicate"] for item in results), [False, True])
        self.assertEqual(len(imported_sources(self.config)), 1)


if __name__ == "__main__":
    unittest.main()
