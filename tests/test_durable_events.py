"""Behavioral acceptance tests for the new scoped durable event journal.

These are intentionally isolated from the existing in-process EventBus:
they do NOT assert that existing agent workflows have been migrated.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aos.durable_events import DurableEventStore, Event, IdempotencyConflict


def event(event_id: str = "ev-1", *, payload: dict | None = None, scope: str = "netso") -> Event:
    return Event(
        event_id=event_id,
        scope=scope,
        event_type="task.created",
        actor="agent-A",
        correlation_id="work-123",
        occurred_at="2026-11-01T01:00:00+00:00",
        payload=payload if payload is not None else {"task_id": "task-1"},
    )


def test_event_survives_store_restart(tmp_path: Path) -> None:
    db = tmp_path / "state" / "events.sqlite3"
    first = DurableEventStore(db)
    seq = first.append(event(), idempotency_key="create-task-1")
    second = DurableEventStore(db)
    assert second.list_events(scope="netso") == [(seq, event())]


def test_retry_returns_original_sequence_without_duplicate(tmp_path: Path) -> None:
    store = DurableEventStore(tmp_path / "journal.db")
    first = store.append(event(), idempotency_key="operation-1")
    second = store.append(event(), idempotency_key="operation-1")
    assert first == second
    assert len(store.list_events(scope="netso")) == 1


def test_payload_mutation_under_same_key_is_rejected(tmp_path: Path) -> None:
    store = DurableEventStore(tmp_path / "journal.db")
    store.append(event(), idempotency_key="operation-1")
    with pytest.raises(IdempotencyConflict):
        store.append(event(payload={"task_id": "task-2"}), idempotency_key="operation-1")
    assert len(store.list_events(scope="netso")) == 1


def test_reusing_event_id_for_different_work_is_rejected(tmp_path: Path) -> None:
    store = DurableEventStore(tmp_path / "journal.db")
    store.append(event(), idempotency_key="operation-1")
    with pytest.raises(IdempotencyConflict):
        store.append(event(payload={"task_id": "task-2"}), idempotency_key="operation-2")


def test_same_idempotency_key_is_separate_for_each_scope(tmp_path: Path) -> None:
    store = DurableEventStore(tmp_path / "journal.db")
    store.append(event("a", scope="netso"), idempotency_key="reference-1")
    store.append(event("b", scope="personal"), idempotency_key="reference-1")
    assert len(store.list_events(scope="netso")) == 1
    assert len(store.list_events(scope="personal")) == 1
    assert store.list_events(scope="personal")[0][1].event_id == "b"


def test_multiple_writers_cannot_duplicate_one_operation(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"

    def write() -> int:
        return DurableEventStore(path).append(event(), idempotency_key="same-op")

    with ThreadPoolExecutor(max_workers=8) as executor:
        seqs = list(executor.map(lambda _: write(), range(16)))
    assert len(set(seqs)) == 1
    assert len(DurableEventStore(path).list_events(scope="netso")) == 1


def test_scope_is_required_for_reads_and_writes(tmp_path: Path) -> None:
    store = DurableEventStore(tmp_path / "journal.db")
    with pytest.raises(ValueError):
        store.list_events(scope="")
    with pytest.raises(ValueError):
        store.append(event(scope=""))


def test_event_data_is_not_mutated_after_writing(tmp_path: Path) -> None:
    store = DurableEventStore(tmp_path / "journal.db")
    data = {"task_id": "1"}
    store.append(event(payload=data))
    data["task_id"] = "unexpected"
    assert store.list_events(scope="netso")[0][1].payload == {"task_id": "1"}


def test_database_is_private_by_default(tmp_path: Path) -> None:
    db = tmp_path / "state" / "events.sqlite3"
    DurableEventStore(db).append(event())
    assert db.stat().st_mode & 0o077 == 0


def test_existing_world_readable_database_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "old.sqlite3"
    db.write_bytes(b"")
    db.chmod(0o644)
    with pytest.raises(PermissionError):
        DurableEventStore(db)
