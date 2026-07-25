"""ISCP — Inter-Session Communication Protocol.

SQLite-backed dispatch and flag storage for agent-to-agent communication
across sessions and worktrees. Modeled after TheAgency's ISCP messaging.

Uses parameterized SQL queries (CRITICAL: never string-interpolate user values).
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DispatchType(str, Enum):
    DIRECTIVE = "directive"
    REVIEW = "review"
    SEED = "seed"
    ESCALATION = "escalation"


class DispatchStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    RESOLVED = "resolved"


class FlagStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    PROCESSED = "processed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dispatch:
    """Structured inter-session message with immutable payload."""

    id: str
    from_agent: str
    to_agent: str
    subject: str
    body: str
    dispatch_type: DispatchType
    status: DispatchStatus = DispatchStatus.UNREAD
    created_at: str = ""
    read_at: str | None = None
    resolved_at: str | None = None

    def to_row(self) -> tuple[Any, ...]:
        """Serialize to SQLite row values (parameterized insert)."""
        return (
            self.id, self.from_agent, self.to_agent, self.subject,
            self.body, self.dispatch_type.value, self.status.value,
            self.created_at, self.read_at, self.resolved_at,
        )

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Dispatch:
        """Deserialize from SQLite Row."""
        return cls(
            id=row["id"],
            from_agent=row["from_agent"],
            to_agent=row["to_agent"],
            subject=row["subject"],
            body=row["body"],
            dispatch_type=DispatchType(row["dispatch_type"]),
            status=DispatchStatus(row["status"]),
            created_at=row["created_at"],
            read_at=row["read_at"],
            resolved_at=row["resolved_at"],
        )


@dataclass(frozen=True)
class Flag:
    """Quick-capture observation, agent-addressable."""

    id: str
    from_agent: str
    to_agent: str | None  # None = self-flag
    message: str
    status: FlagStatus = FlagStatus.UNREAD
    created_at: str = ""

    def to_row(self) -> tuple[Any, ...]:
        """Serialize to SQLite row values (parameterized insert)."""
        return (
            self.id, self.from_agent, self.to_agent,
            self.message, self.status.value, self.created_at,
        )

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Flag:
        """Deserialize from SQLite Row."""
        return cls(
            id=row["id"],
            from_agent=row["from_agent"],
            to_agent=row["to_agent"],
            message=row["message"],
            status=FlagStatus(row["status"]),
            created_at=row["created_at"],
        )


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def create_dispatch(
    *,
    from_agent: str,
    to_agent: str,
    subject: str,
    body: str,
    dispatch_type: DispatchType = DispatchType.DIRECTIVE,
) -> Dispatch:
    """Create a dispatch with auto-generated ID and timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    return Dispatch(
        id=f"DSP-{uuid.uuid4().hex[:8].upper()}",
        from_agent=from_agent,
        to_agent=to_agent,
        subject=subject,
        body=body,
        dispatch_type=dispatch_type,
        created_at=now,
    )


def create_flag(
    *,
    from_agent: str,
    to_agent: str | None = None,
    message: str,
) -> Flag:
    """Create a flag with auto-generated ID and timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    return Flag(
        id=f"FLG-{uuid.uuid4().hex[:8].upper()}",
        from_agent=from_agent,
        to_agent=to_agent,
        message=message,
        created_at=now,
    )


# ---------------------------------------------------------------------------
# SQLite store
# ---------------------------------------------------------------------------


class ISCPStore:
    """SQLite-backed dispatch and flag storage.

    Uses parameterized SQL queries throughout — never string-interpolates
    user-supplied values into SQL.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS dispatches (
                id TEXT PRIMARY KEY,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                dispatch_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unread',
                created_at TEXT NOT NULL,
                read_at TEXT,
                resolved_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_dispatches_to
                ON dispatches(to_agent, status);
            CREATE INDEX IF NOT EXISTS idx_dispatches_from
                ON dispatches(from_agent);

            CREATE TABLE IF NOT EXISTS flags (
                id TEXT PRIMARY KEY,
                from_agent TEXT NOT NULL,
                to_agent TEXT,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unread',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_flags_to
                ON flags(to_agent, status);
        """)
        conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- Dispatch operations --

    def create_dispatch(self, dispatch: Dispatch) -> str:
        """Insert a dispatch. Returns the dispatch ID."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO dispatches "
            "(id, from_agent, to_agent, subject, body, dispatch_type, "
            "status, created_at, read_at, resolved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            dispatch.to_row(),
        )
        conn.commit()
        logger.info("Dispatch created: %s → %s", dispatch.from_agent, dispatch.to_agent)
        return dispatch.id

    def get_dispatch(self, dispatch_id: str) -> Dispatch | None:
        """Fetch a dispatch by ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM dispatches WHERE id = ?", (dispatch_id,)
        )
        row = cursor.fetchone()
        return Dispatch.from_row(row) if row else None

    def list_unread_dispatches(self, agent_id: str) -> list[Dispatch]:
        """List unread dispatches for an agent."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM dispatches WHERE to_agent = ? AND status = 'unread' "
            "ORDER BY created_at ASC",
            (agent_id,),
        )
        return [Dispatch.from_row(row) for row in cursor.fetchall()]

    def mark_dispatch_read(self, dispatch_id: str) -> bool:
        """Mark a dispatch as read. Returns True if updated."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "UPDATE dispatches SET status = 'read', read_at = ? WHERE id = ?",
            (now, dispatch_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def resolve_dispatch(self, dispatch_id: str) -> bool:
        """Mark a dispatch as resolved. Returns True if updated."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "UPDATE dispatches SET status = 'resolved', resolved_at = ? WHERE id = ?",
            (now, dispatch_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_dispatch(self, dispatch_id: str) -> bool:
        """Delete a dispatch. Returns True if deleted."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM dispatches WHERE id = ?", (dispatch_id,))
        conn.commit()
        return cursor.rowcount > 0

    # -- Flag operations --

    def create_flag(self, flag: Flag) -> str:
        """Insert a flag. Returns the flag ID."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO flags "
            "(id, from_agent, to_agent, message, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            flag.to_row(),
        )
        conn.commit()
        logger.info("Flag created: %s → %s", flag.from_agent, flag.to_agent)
        return flag.id

    def get_flag(self, flag_id: str) -> Flag | None:
        """Fetch a flag by ID."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM flags WHERE id = ?", (flag_id,))
        row = cursor.fetchone()
        return Flag.from_row(row) if row else None

    def list_unread_flags(self, agent_id: str) -> list[Flag]:
        """List unread flags for an agent (includes self-flags)."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM flags WHERE to_agent = ? AND status = 'unread' "
            "ORDER BY created_at ASC",
            (agent_id,),
        )
        return [Flag.from_row(row) for row in cursor.fetchall()]

    def mark_flag_read(self, flag_id: str) -> bool:
        """Mark a flag as read. Returns True if updated."""
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE flags SET status = 'read' WHERE id = ?", (flag_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def mark_flag_processed(self, flag_id: str) -> bool:
        """Mark a flag as processed. Returns True if updated."""
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE flags SET status = 'processed' WHERE id = ?", (flag_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_flag(self, flag_id: str) -> bool:
        """Delete a flag. Returns True if deleted."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM flags WHERE id = ?", (flag_id,))
        conn.commit()
        return cursor.rowcount > 0
