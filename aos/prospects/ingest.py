"""Bounded, local extraction with stable document/locator references."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import subprocess
import sys
from pathlib import PurePath
from typing import Any
from uuid import uuid4

from aos.prospects.models import Passage, Upload

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 120_000


def extract(upload: Upload) -> tuple[dict[str, Any], bytes, list[Passage]]:
    name = upload.filename
    if (
        PurePath(name).name != name
        or any(c in name for c in "/\\\r\n\x00")
        or name.startswith(".")
    ):
        raise ValueError("Invalid document filename")
    try:
        raw = base64.b64decode(upload.content_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64 document") from exc
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise ValueError("Document must be between 1 byte and 5 MiB")
    suffix = PurePath(name).suffix.lower()
    kind = "line"
    try:
        if suffix in {".txt", ".md"}:
            chunks = raw.decode("utf-8-sig").splitlines()
        elif suffix in {".pdf", ".docx"}:
            if os.name != "posix":
                raise ValueError(
                    "Resource-bounded PDF/DOCX parsing requires macOS/Linux; use TXT/MD"
                )
            try:
                parsed = subprocess.run(
                    [sys.executable, "-m", "aos.prospects.parser_worker", suffix],
                    input=raw,
                    capture_output=True,
                    check=False,
                    timeout=15,
                    env={"PYTHONUTF8": "1"},
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError(
                    "Document parser time budget exceeded; provide readable text"
                ) from exc
            if parsed.returncode != 0:
                raise ValueError(
                    "Document unreadable or parser resource budget exceeded; OCR may be required"
                )
            result = json.loads(parsed.stdout)
            chunks, kind = result["chunks"], result["kind"]
        else:
            raise ValueError("Supported types: TXT, MD, DOCX and text PDF")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Document extraction failed; provide readable text") from exc
    if sum(len(text) for text in chunks) > MAX_TEXT_CHARS:
        raise ValueError("Extracted text exceeds 120,000 character limit")
    source_id = str(uuid4())
    passages = [
        Passage(source_id=source_id, page=n, text=text.strip())
        for n, text in enumerate(chunks, 1)
        if text.strip()
    ]
    if not passages:
        raise ValueError("Document has no readable text; OCR may be required")
    return (
        {
            "id": source_id,
            "filename": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "locator_kind": kind,
            "passages": [p.model_dump() for p in passages],
        },
        raw,
        passages,
    )
