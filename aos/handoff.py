"""Session Handoff — structured state snapshots for cross-session continuity.

Modeled after TheAgency's session handoff pattern. Captures session state
so work survives /compact, /exit, and multi-day gaps.

HandoffStore persists handoffs as JSON files with automatic expiry.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_EXPIRY_DAYS = 7

# Session ID validation — prevents path traversal via crafted session_id
_SESSION_ID_RE = re.compile(r"^SES-[A-F0-9]{8}$")


# ---------------------------------------------------------------------------
# Handoff model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionHandoff:
    """Structured state snapshot for session continuity."""

    session_id: str
    agent_id: str
    venture_id: str
    harness_id: str
    cycle_id: str
    iteration: int
    phase: str  # current pipeline phase
    pending_tasks: list[str] = field(default_factory=list)
    completed_tasks: list[str] = field(default_factory=list)
    context_summary: str = ""
    approval_queue: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: str = ""
    expires_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "venture_id": self.venture_id,
            "harness_id": self.harness_id,
            "cycle_id": self.cycle_id,
            "iteration": self.iteration,
            "phase": self.phase,
            "pending_tasks": self.pending_tasks,
            "completed_tasks": self.completed_tasks,
            "context_summary": self.context_summary,
            "approval_queue": self.approval_queue,
            "errors": self.errors,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionHandoff:
        """Deserialize from dict."""
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            venture_id=data["venture_id"],
            harness_id=data["harness_id"],
            cycle_id=data["cycle_id"],
            iteration=data["iteration"],
            phase=data["phase"],
            pending_tasks=data.get("pending_tasks", []),
            completed_tasks=data.get("completed_tasks", []),
            context_summary=data.get("context_summary", ""),
            approval_queue=data.get("approval_queue", []),
            errors=data.get("errors", []),
            created_at=data.get("created_at", ""),
            expires_at=data.get("expires_at", ""),
        )

    @property
    def is_expired(self) -> bool:
        """Check if the handoff has expired."""
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at)
            return datetime.now(UTC) > expires
        except (ValueError, TypeError):
            return False


def create_handoff(
    *,
    agent_id: str,
    venture_id: str,
    harness_id: str,
    cycle_id: str,
    iteration: int,
    phase: str,
    pending_tasks: list[str] | None = None,
    completed_tasks: list[str] | None = None,
    context_summary: str = "",
    approval_queue: list[str] | None = None,
    errors: list[str] | None = None,
    expiry_days: int = DEFAULT_EXPIRY_DAYS,
) -> SessionHandoff:
    """Create a handoff with auto-generated IDs and timestamps."""
    now = datetime.now(UTC)
    return SessionHandoff(
        session_id=f"SES-{uuid.uuid4().hex[:8].upper()}",
        agent_id=agent_id,
        venture_id=venture_id,
        harness_id=harness_id,
        cycle_id=cycle_id,
        iteration=iteration,
        phase=phase,
        pending_tasks=pending_tasks or [],
        completed_tasks=completed_tasks or [],
        context_summary=context_summary,
        approval_queue=approval_queue or [],
        errors=errors or [],
        created_at=now.isoformat(),
        expires_at=(now + timedelta(days=expiry_days)).isoformat(),
    )


# ---------------------------------------------------------------------------
# Handoff store
# ---------------------------------------------------------------------------


class HandoffStore:
    """Persist and restore session handoffs as JSON files.

    Directory layout:
      <base_dir>/
        handoffs/
          SES-XXXXXXXX.json
          SES-YYYYYYYY.json
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path(".")
        self._handoffs_dir = self._base_dir / "handoffs"

    @property
    def handoffs_dir(self) -> Path:
        return self._handoffs_dir

    def save(self, handoff: SessionHandoff) -> Path:
        """Save a handoff to disk. Returns the file path."""
        self._handoffs_dir.mkdir(parents=True, exist_ok=True)
        path = self._handoffs_dir / f"{handoff.session_id}.json"
        path.write_text(json.dumps(handoff.to_dict(), indent=2))
        logger.info("Handoff saved: %s → %s", handoff.session_id, path)
        return path

    def load(self, session_id: str) -> SessionHandoff | None:
        """Load a handoff by session ID. Returns None if not found."""
        if not _SESSION_ID_RE.match(session_id):
            raise ValueError(f"Invalid session_id format: {session_id}")
        path = self._handoffs_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return SessionHandoff.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load handoff %s: %s", session_id, exc)
            return None

    def list_pending(self, agent_id: str | None = None) -> list[SessionHandoff]:
        """List non-expired handoffs, optionally filtered by agent_id."""
        if not self._handoffs_dir.exists():
            return []
        handoffs: list[SessionHandoff] = []
        for path in sorted(self._handoffs_dir.glob("SES-*.json")):
            try:
                data = json.loads(path.read_text())
                handoff = SessionHandoff.from_dict(data)
                if handoff.is_expired:
                    continue
                if agent_id and handoff.agent_id != agent_id:
                    continue
                handoffs.append(handoff)
            except (json.JSONDecodeError, KeyError):
                continue
        return handoffs

    def cleanup_expired(self) -> int:
        """Delete expired handoff files. Returns count of deleted files."""
        if not self._handoffs_dir.exists():
            return 0
        deleted = 0
        for path in self._handoffs_dir.glob("SES-*.json"):
            try:
                data = json.loads(path.read_text())
                handoff = SessionHandoff.from_dict(data)
                if handoff.is_expired:
                    path.unlink()
                    deleted += 1
                    logger.info("Expired handoff cleaned: %s", path.name)
            except (json.JSONDecodeError, KeyError):
                continue
        return deleted

    def delete(self, session_id: str) -> bool:
        """Delete a handoff file. Returns True if deleted."""
        if not _SESSION_ID_RE.match(session_id):
            raise ValueError(f"Invalid session_id format: {session_id}")
        path = self._handoffs_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
