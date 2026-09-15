from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from research_store.config import load_config
from research_store.sync import markitdown_converter, sync_library


def write_text_pdf(path: Path, text: str) -> None:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode("ascii"))
        content.extend(body)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(content)


class SyncLibraryTests(unittest.TestCase):
    def test_markitdown_converts_a_text_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "paper.pdf"
            write_text_pdf(pdf, "Hello Research")

            converted = markitdown_converter(pdf)

            self.assertIn("Hello Research", converted)

    def test_sync_is_incremental_and_never_changes_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            pdf = source / "nested" / "paper.PDF"
            pdf.parent.mkdir()
            original = b"unchanged source bytes"
            pdf.write_bytes(original)

            config_path = project / "config.toml"
            config_path.write_text(
                """
[store]
documents = "knowledge/documents"
conversations = "knowledge/conversations"
state = ".research-store/state.json"
temporary = ".research-store/tmp"

[[sources]]
id = "papers"
path = "../papers"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            config = load_config(config_path)
            seen_paths: list[Path] = []

            def fake_converter(path: Path) -> str:
                seen_paths.append(path)
                self.assertFalse(path.is_relative_to(source))
                return "# Parsed paper\n\nUseful content.\n"

            first = sync_library(config, fake_converter)
            second = sync_library(config, fake_converter)

            self.assertEqual(first.converted, 1)
            self.assertEqual(second.unchanged, 1)
            self.assertEqual(len(seen_paths), 1)
            self.assertEqual(pdf.read_bytes(), original)
            output = project / "knowledge/documents/papers/nested/paper.md"
            self.assertIn('source_path: "nested/paper.PDF"', output.read_text())

    def test_rejects_output_inside_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "papers"
            source.mkdir()
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                f"""
[store]
documents = "{source / 'generated'}"
conversations = "conversations"
state = "state.json"
temporary = "tmp"

[[sources]]
id = "papers"
path = "{source}"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "쓰기 경로가 원본 디렉터리 안"):
                load_config(config_path)

    def test_missing_source_is_marked_without_deleting_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "papers"
            project = root / "project"
            source.mkdir()
            project.mkdir()
            pdf = source / "paper.pdf"
            pdf.write_bytes(b"pdf")
            config_path = project / "config.toml"
            config_path.write_text(
                f"""
[store]
documents = "knowledge/documents"
conversations = "knowledge/conversations"
state = ".research-store/state.json"
temporary = ".research-store/tmp"

[[sources]]
id = "papers"
path = "{source}"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            config = load_config(config_path)
            sync_library(config, lambda _: "content\n")
            output = project / "knowledge/documents/papers/paper.md"
            pdf.unlink()

            result = sync_library(config, lambda _: "content\n")
            state = json.loads((project / ".research-store/state.json").read_text())

            self.assertEqual(result.missing, 1)
            self.assertTrue(output.is_file())
            self.assertFalse(state["documents"]["papers:paper.pdf"]["present"])


if __name__ == "__main__":
    unittest.main()
