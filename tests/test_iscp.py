"""Tests for ISCP — Dispatch, Flag, ISCPStore SQLite CRUD."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from aos.iscp import (
    Dispatch,
    DispatchStatus,
    DispatchType,
    Flag,
    FlagStatus,
    ISCPStore,
    create_dispatch,
    create_flag,
)


# ---------------------------------------------------------------------------
# Dispatch model tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDispatch:

    def test_frozen(self):
        d = _make_dispatch()
        with pytest.raises(AttributeError):
            d.id = "changed"  # type: ignore[misc]

    def test_to_row(self):
        d = _make_dispatch(id_="DSP-001", subject="test subject")
        row = d.to_row()
        assert row[0] == "DSP-001"
        assert row[3] == "test subject"
        assert row[5] == "directive"
        assert row[6] == "unread"

    def test_from_row(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        d = _make_dispatch(id_="DSP-FROM")
        store.create_dispatch(d)
        loaded = store.get_dispatch("DSP-FROM")
        assert loaded is not None
        assert loaded.id == "DSP-FROM"
        assert loaded.dispatch_type == DispatchType.DIRECTIVE
        assert loaded.status == DispatchStatus.UNREAD
        store.close()

    def test_defaults(self):
        d = Dispatch(
            id="DSP-X", from_agent="A", to_agent="B",
            subject="s", body="b", dispatch_type=DispatchType.SEED,
        )
        assert d.status == DispatchStatus.UNREAD
        assert d.read_at is None
        assert d.resolved_at is None

    def test_roundtrip(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        d = _make_dispatch(id_="DSP-RT")
        store.create_dispatch(d)
        loaded = store.get_dispatch("DSP-RT")
        assert loaded == d
        store.close()


# ---------------------------------------------------------------------------
# Flag model tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFlag:

    def test_frozen(self):
        f = _make_flag()
        with pytest.raises(AttributeError):
            f.id = "changed"  # type: ignore[misc]

    def test_to_row(self):
        f = _make_flag(id_="FLG-001", to_agent="AGT-B")
        row = f.to_row()
        assert row[0] == "FLG-001"
        assert row[2] == "AGT-B"
        assert row[4] == "unread"

    def test_from_row(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        f = _make_flag(id_="FLG-FROM")
        store.create_flag(f)
        loaded = store.get_flag("FLG-FROM")
        assert loaded is not None
        assert loaded.id == "FLG-FROM"
        assert loaded.status == FlagStatus.UNREAD
        store.close()

    def test_self_flag(self):
        f = _make_flag(to_agent=None)
        assert f.to_agent is None

    def test_defaults(self):
        f = Flag(id="FLG-X", from_agent="A", to_agent="B", message="m")
        assert f.status == FlagStatus.UNREAD
        assert f.created_at == ""


# ---------------------------------------------------------------------------
# create_dispatch tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateDispatch:

    def test_auto_generates_id(self):
        d = create_dispatch(
            from_agent="AGT-A", to_agent="AGT-B",
            subject="test", body="hello",
        )
        assert d.id.startswith("DSP-")
        assert len(d.id) == 12

    def test_auto_timestamp(self):
        d = create_dispatch(
            from_agent="AGT-A", to_agent="AGT-B",
            subject="test", body="hello",
        )
        assert d.created_at  # non-empty

    def test_custom_type(self):
        d = create_dispatch(
            from_agent="AGT-A", to_agent="AGT-B",
            subject="review", body="please review",
            dispatch_type=DispatchType.REVIEW,
        )
        assert d.dispatch_type == DispatchType.REVIEW


# ---------------------------------------------------------------------------
# create_flag tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateFlag:

    def test_auto_generates_id(self):
        f = create_flag(from_agent="AGT-A", message="flag!")
        assert f.id.startswith("FLG-")
        assert len(f.id) == 12

    def test_auto_timestamp(self):
        f = create_flag(from_agent="AGT-A", message="flag!")
        assert f.created_at

    def test_with_target(self):
        f = create_flag(from_agent="AGT-A", to_agent="AGT-B", message="hey")
        assert f.to_agent == "AGT-B"

    def test_self_flag(self):
        f = create_flag(from_agent="AGT-A", message="note to self")
        assert f.to_agent is None


# ---------------------------------------------------------------------------
# ISCPStore — Dispatch operations
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestISCPStoreDispatch:

    def test_create_and_get(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        d = _make_dispatch(id_="DSP-CG-001")
        store.create_dispatch(d)
        loaded = store.get_dispatch("DSP-CG-001")
        assert loaded is not None
        assert loaded.subject == "test dispatch"
        store.close()

    def test_get_nonexistent(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        assert store.get_dispatch("DSP-DOES-NOT-EXIST") is None
        store.close()

    def test_list_unread_dispatches(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_dispatch(_make_dispatch(id_="DSP-LU-001", to_agent="AGT-X"))
        store.create_dispatch(_make_dispatch(id_="DSP-LU-002", to_agent="AGT-X"))
        store.create_dispatch(_make_dispatch(id_="DSP-LU-003", to_agent="AGT-Y"))

        unread = store.list_unread_dispatches("AGT-X")
        assert len(unread) == 2
        unread_y = store.list_unread_dispatches("AGT-Y")
        assert len(unread_y) == 1
        store.close()

    def test_mark_dispatch_read(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_dispatch(_make_dispatch(id_="DSP-MR-001"))
        assert store.mark_dispatch_read("DSP-MR-001")
        d = store.get_dispatch("DSP-MR-001")
        assert d is not None
        assert d.status == DispatchStatus.READ
        assert d.read_at is not None
        store.close()

    def test_mark_dispatch_read_nonexistent(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        assert not store.mark_dispatch_read("DSP-NOPE")
        store.close()

    def test_resolve_dispatch(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_dispatch(_make_dispatch(id_="DSP-RS-001"))
        assert store.resolve_dispatch("DSP-RS-001")
        d = store.get_dispatch("DSP-RS-001")
        assert d is not None
        assert d.status == DispatchStatus.RESOLVED
        assert d.resolved_at is not None
        store.close()

    def test_delete_dispatch(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_dispatch(_make_dispatch(id_="DSP-DEL-001"))
        assert store.delete_dispatch("DSP-DEL-001")
        assert store.get_dispatch("DSP-DEL-001") is None
        assert not store.delete_dispatch("DSP-DEL-001")
        store.close()

    def test_unread_excludes_read(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_dispatch(_make_dispatch(id_="DSP-UE-001", to_agent="AGT-Z"))
        store.mark_dispatch_read("DSP-UE-001")
        store.create_dispatch(_make_dispatch(id_="DSP-UE-002", to_agent="AGT-Z"))
        unread = store.list_unread_dispatches("AGT-Z")
        assert len(unread) == 1
        assert unread[0].id == "DSP-UE-002"
        store.close()


# ---------------------------------------------------------------------------
# ISCPStore — Flag operations
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestISCPStoreFlag:

    def test_create_and_get(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        f = _make_flag(id_="FLG-CG-001")
        store.create_flag(f)
        loaded = store.get_flag("FLG-CG-001")
        assert loaded is not None
        assert loaded.message == "test flag"
        store.close()

    def test_get_nonexistent(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        assert store.get_flag("FLG-DOES-NOT-EXIST") is None
        store.close()

    def test_list_unread_flags(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_flag(_make_flag(id_="FLG-LU-001", to_agent="AGT-X"))
        store.create_flag(_make_flag(id_="FLG-LU-002", to_agent="AGT-X"))
        store.create_flag(_make_flag(id_="FLG-LU-003", to_agent="AGT-Y"))

        unread = store.list_unread_flags("AGT-X")
        assert len(unread) == 2
        store.close()

    def test_mark_flag_read(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_flag(_make_flag(id_="FLG-MR-001"))
        assert store.mark_flag_read("FLG-MR-001")
        f = store.get_flag("FLG-MR-001")
        assert f is not None
        assert f.status == FlagStatus.READ
        store.close()

    def test_mark_flag_processed(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_flag(_make_flag(id_="FLG-MP-001"))
        assert store.mark_flag_processed("FLG-MP-001")
        f = store.get_flag("FLG-MP-001")
        assert f is not None
        assert f.status == FlagStatus.PROCESSED
        store.close()

    def test_delete_flag(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        store.create_flag(_make_flag(id_="FLG-DEL-001"))
        assert store.delete_flag("FLG-DEL-001")
        assert store.get_flag("FLG-DEL-001") is None
        assert not store.delete_flag("FLG-DEL-001")
        store.close()

    def test_mark_flag_read_nonexistent(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        assert not store.mark_flag_read("FLG-NOPE")
        store.close()


# ---------------------------------------------------------------------------
# ISCPStore — Schema and persistence tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestISCPStoreSchema:

    def test_wal_mode(self, tmp_path: Path):
        store = ISCPStore(tmp_path / "test.db")
        conn = store._get_conn()
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode == "wal"
        store.close()

    def test_schema_idempotent(self, tmp_path: Path):
        """Creating the store twice doesn't error."""
        ISCPStore(tmp_path / "test.db")
        store2 = ISCPStore(tmp_path / "test.db")
        assert store2 is not None
        store2.close()

    def test_persistence(self, tmp_path: Path):
        """Data persists across store instances."""
        store1 = ISCPStore(tmp_path / "test.db")
        store1.create_dispatch(_make_dispatch(id_="DSP-PERSIST-001"))
        store1.close()

        store2 = ISCPStore(tmp_path / "test.db")
        loaded = store2.get_dispatch("DSP-PERSIST-001")
        assert loaded is not None
        store2.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dispatch(
    *,
    id_: str = "DSP-TEST-001",
    to_agent: str = "AGT-EXEC-COO",
    subject: str = "test dispatch",
    dispatch_type: DispatchType = DispatchType.DIRECTIVE,
) -> Dispatch:
    return Dispatch(
        id=id_,
        from_agent="AGT-EXEC-CEO",
        to_agent=to_agent,
        subject=subject,
        body="This is a test dispatch body.",
        dispatch_type=dispatch_type,
        created_at="2025-01-01T00:00:00+00:00",
    )


def _make_flag(
    *,
    id_: str = "FLG-TEST-001",
    to_agent: str | None = "AGT-EXEC-COO",
    message: str = "test flag",
) -> Flag:
    return Flag(
        id=id_,
        from_agent="AGT-EXEC-CEO",
        to_agent=to_agent,
        message=message,
        created_at="2025-01-01T00:00:00+00:00",
    )
