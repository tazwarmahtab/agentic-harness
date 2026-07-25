"""Tests for Session Handoff — model, store, expiry, persistence."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from aos.handoff import (
    DEFAULT_EXPIRY_DAYS,
    HandoffStore,
    SessionHandoff,
    create_handoff,
)

# ---------------------------------------------------------------------------
# SessionHandoff model tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSessionHandoff:

    def test_frozen(self):
        h = _make_handoff()
        with pytest.raises(AttributeError):
            h.session_id = "changed"  # type: ignore[misc]

    def test_to_dict(self):
        h = _make_handoff(session_id="SES-TEST-001")
        d = h.to_dict()
        assert d["session_id"] == "SES-TEST-001"
        assert d["iteration"] == 1
        assert "is_expired" not in d

    def test_from_dict(self):
        d = {
            "session_id": "SES-001", "agent_id": "AGT-001",
            "venture_id": "V-001", "harness_id": "HAR-001",
            "cycle_id": "CYC-001", "iteration": 1, "phase": "plan",
            "pending_tasks": ["t1"], "completed_tasks": ["t0"],
            "context_summary": "hello", "approval_queue": ["APR-001"],
            "errors": ["err1"], "created_at": "2025-01-01T00:00:00+00:00",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
        h = SessionHandoff.from_dict(d)
        assert h.session_id == "SES-001"
        assert h.pending_tasks == ["t1"]
        assert h.errors == ["err1"]

    def test_roundtrip(self):
        h = _make_handoff()
        h2 = SessionHandoff.from_dict(h.to_dict())
        assert h == h2


# ---------------------------------------------------------------------------
# Expiry tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHandoffExpiry:

    def test_not_expired_future(self):
        h = _make_handoff(expires_at="2099-01-01T00:00:00+00:00")
        assert not h.is_expired

    def test_expired_past(self):
        h = _make_handoff(expires_at="2000-01-01T00:00:00+00:00")
        assert h.is_expired

    def test_no_expiry_never_expired(self):
        h = _make_handoff(expires_at="")
        assert not h.is_expired

    def test_invalid_expiry_format(self):
        h = _make_handoff(expires_at="not-a-date")
        assert not h.is_expired  # fails gracefully


# ---------------------------------------------------------------------------
# create_handoff tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateHandoff:

    def test_auto_generates_ids(self):
        h = create_handoff(
            agent_id="AGT-001", venture_id="V-001", harness_id="HAR-001",
            cycle_id="CYC-001", iteration=1, phase="plan",
        )
        assert h.session_id.startswith("SES-")
        assert len(h.session_id) == 12  # SES- + 8 hex chars

    def test_auto_timestamps(self):
        h = create_handoff(
            agent_id="AGT-001", venture_id="V-001", harness_id="HAR-001",
            cycle_id="CYC-001", iteration=1, phase="plan",
        )
        assert h.created_at
        assert h.expires_at
        created = datetime.fromisoformat(h.created_at)
        expires = datetime.fromisoformat(h.expires_at)
        assert (expires - created).days == DEFAULT_EXPIRY_DAYS

    def test_custom_expiry(self):
        h = create_handoff(
            agent_id="AGT-001", venture_id="V-001", harness_id="HAR-001",
            cycle_id="CYC-001", iteration=1, phase="plan", expiry_days=3,
        )
        created = datetime.fromisoformat(h.created_at)
        expires = datetime.fromisoformat(h.expires_at)
        assert (expires - created).days == 3


# ---------------------------------------------------------------------------
# HandoffStore tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHandoffStore:

    def test_save_and_load(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path)
        h = _make_handoff(session_id="SES-AA000002")
        path = store.save(h)
        assert path.exists()
        assert path.name == "SES-AA000002.json"

        loaded = store.load("SES-AA000002")
        assert loaded is not None
        assert loaded.session_id == "SES-AA000002"
        assert loaded.agent_id == h.agent_id

    def test_load_nonexistent(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path)
        assert store.load("SES-000000FF") is None

    def test_list_pending(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path)
        store.save(_make_handoff(session_id="SES-LIST-001", agent_id="AGT-A"))
        store.save(_make_handoff(session_id="SES-LIST-002", agent_id="AGT-B"))
        store.save(_make_handoff(session_id="SES-LIST-003", agent_id="AGT-A"))

        all_pending = store.list_pending()
        assert len(all_pending) == 3

        agent_a = store.list_pending(agent_id="AGT-A")
        assert len(agent_a) == 2

        agent_b = store.list_pending(agent_id="AGT-B")
        assert len(agent_b) == 1

    def test_list_pending_skips_expired(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path)
        store.save(_make_handoff(
            session_id="SES-EXPIRED", agent_id="AGT-X",
            expires_at="2000-01-01T00:00:00+00:00",
        ))
        store.save(_make_handoff(session_id="SES-ACTIVE", agent_id="AGT-X"))

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].session_id == "SES-ACTIVE"

    def test_cleanup_expired(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path)
        store.save(_make_handoff(
            session_id="SES-CC000001",
            expires_at="2000-01-01T00:00:00+00:00",
        ))
        store.save(_make_handoff(
            session_id="SES-CC000002",
            expires_at="2099-01-01T00:00:00+00:00",
        ))
        deleted = store.cleanup_expired()
        assert deleted == 1
        assert store.load("SES-CC000001") is None
        assert store.load("SES-CC000002") is not None

    def test_delete(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path)
        store.save(_make_handoff(session_id="SES-DD000001"))
        assert store.delete("SES-DD000001")
        assert store.load("SES-DD000001") is None
        assert not store.delete("SES-DD000001")  # already gone

    def test_list_pending_empty_dir(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path)
        assert store.list_pending() == []

    def test_save_creates_directory(self, tmp_path: Path):
        store = HandoffStore(base_dir=tmp_path / "nested" / "dir")
        h = _make_handoff(session_id="SES-MKDIR-001")
        path = store.save(h)
        assert path.exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handoff(
    *,
    session_id: str = "SES-AA000001",
    agent_id: str = "AGT-EXEC-COO",
    expires_at: str = "2099-01-01T00:00:00+00:00",
) -> SessionHandoff:
    return SessionHandoff(
        session_id=session_id,
        agent_id=agent_id,
        venture_id="V-NETSO",
        harness_id="HAR-EXECUTIVE-001",
        cycle_id="CYC-001",
        iteration=1,
        phase="plan",
        pending_tasks=["task-1", "task-2"],
        completed_tasks=["task-0"],
        context_summary="Planning phase in progress",
        approval_queue=[],
        errors=[],
        created_at="2025-01-01T00:00:00+00:00",
        expires_at=expires_at,
    )
