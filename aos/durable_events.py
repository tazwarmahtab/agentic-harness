"""Scoped, SQLite-backed append-only event journal (not yet wired to legacy EventBus).

Canonical audit-event prototype. SQLite durability is not a distributed worker
or external exactly-once guarantee; consumers must persist their own receipts.
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class IdempotencyConflict(ValueError):
    """An event ID or scoped idempotency key was reused for different content."""


@dataclass(frozen=True)
class Event:
    event_id: str
    scope: str
    event_type: str
    actor: str
    correlation_id: str
    occurred_at: str
    payload: dict[str, Any]


def _nonempty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _encode(event: Event) -> str:
    for field in ("event_id", "scope", "event_type", "actor", "correlation_id", "occurred_at"):
        _nonempty(field, getattr(event, field))
    if not isinstance(event.payload, dict):
        raise ValueError("payload must be a JSON object")
    encoded = json.dumps(asdict(event), sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > 64 * 1024:
        raise ValueError("event data exceeds the 64 KiB metadata-only limit")
    return encoded


class DurableEventStore:
    """Single-host SQLite event store with atomic replay detection and scoped reads.

    Multi-process SQLite writes are serialized by BEGIN IMMEDIATE. This is not
    an authorization boundary: callers must authenticate and enforce ACLs.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # The journal can hold sensitive metadata. Fail closed for inherited
        # permissive files; never silently chmod a pre-existing database.
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if self.path.is_symlink():
                raise PermissionError("journal path may not be a symbolic link") from None
        else:
            os.close(fd)
        mode = self.path.stat().st_mode
        if not stat.S_ISREG(mode) or mode & 0o077:
            raise PermissionError("journal must be a private regular file (mode 0600)")
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS journal (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    scope TEXT NOT NULL,
                    idempotency_key TEXT,
                    event_json TEXT NOT NULL,
                    UNIQUE(scope, idempotency_key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS journal_scope_seq ON journal(scope, seq)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=20)
        conn.execute("PRAGMA busy_timeout=20000")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def append(self, event: Event, *, idempotency_key: str | None = None) -> int:
        data = _encode(event)
        if idempotency_key is not None:
            _nonempty("idempotency_key", idempotency_key)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT seq, event_json, idempotency_key FROM journal "
                "WHERE event_id = ? OR (scope = ? AND idempotency_key = ?)",
                (event.event_id, event.scope, idempotency_key),
            ).fetchall()
            if existing:
                if len(existing) != 1 or existing[0][1] != data or existing[0][2] != idempotency_key:
                    raise IdempotencyConflict("event ID or scoped operation conflicts with recorded content")
                return int(existing[0][0])
            cursor = conn.execute(
                "INSERT INTO journal(event_id, scope, idempotency_key, event_json) VALUES (?, ?, ?, ?)",
                (event.event_id, event.scope, idempotency_key, data),
            )
            return int(cursor.lastrowid)

    def list_events(self, *, scope: str, after_seq: int = 0, limit: int = 100) -> list[tuple[int, Event]]:
        _nonempty("scope", scope)
        if after_seq < 0 or not 1 <= limit <= 1000:
            raise ValueError("invalid journal pagination")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT seq, event_json FROM journal WHERE scope = ? AND seq > ? "
                "ORDER BY seq ASC LIMIT ?",
                (scope, after_seq, limit),
            ).fetchall()
        return [(int(seq), Event(**json.loads(data))) for seq, data in rows]
