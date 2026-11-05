"""Resource-bounded PDF/DOCX parser subprocess; no credentials or tools."""

from __future__ import annotations

import io
import json
import resource
import sys
import zipfile

MAX_CHARS = 120_000


def main() -> None:
    # Process resource limits are a parser budget, not a filesystem/network sandbox.
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    raw = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("File exceeds limit")
    chunks: list[str] = []
    count = 0

    def append(text: str) -> None:
        nonlocal count
        count += len(text)
        if count > MAX_CHARS:
            raise ValueError("Extracted text exceeds character budget")
        chunks.append(text)

    if sys.argv[1] == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("Encrypted or oversized PDF is not supported")
        for page in reader.pages:
            text = page.extract_text() or ""
            if not text.strip():
                raise ValueError("PDF has unreadable pages; OCR is required")
            append(text)
        kind = "page"
    else:
        from docx import Document

        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 20 * 1024 * 1024:
                raise ValueError("DOCX expanded size exceeds limit")
        doc = Document(io.BytesIO(raw))
        for paragraph in doc.paragraphs:
            append(paragraph.text)
        for table in doc.tables:
            for row in table.rows:
                append(" | ".join(cell.text for cell in row.cells))
        kind = "paragraph/table-row"
    sys.stdout.write(json.dumps({"chunks": chunks, "kind": kind}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — parser boundary reports a sanitized failure
        sys.stderr.write(
            "Document unreadable or parser budget exceeded; provide readable text/OCR.\n"
        )
        sys.exit(1)
