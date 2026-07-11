"""AOS Event Bus — typed events for inter-harness communication.

All harness-to-harness communication flows through events.
No direct harness calls. Ever.

Event lifecycle:
    Agent emits event → EventBus logs it → Runtime routes → Target harness picks up

Usage:
    from aos.event_bus import EventBus, AOSEvent, EventType

    bus = EventBus()
    bus.emit(AOSEvent(
        type=EventType.TASK_CREATED,
        source_harness="HAR-EXEC-001",
        source_agent="AGT-EXEC-DISPATCH",
        payload={"task": "investor_deck", "target": "AGT-FIN-UNIT"},
    ))
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class EventType(str, Enum):
    # Task lifecycle
    TASK_CREATED    = "harness.task.created"
    TASK_COMPLETED  = "harness.task.completed"
    TASK_BLOCKED    = "harness.task.blocked"
    TASK_ESCALATED  = "harness.task.escalated"
    # Approval lifecycle
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED   = "approval.decided"
    # Memory
    MEMORY_CANDIDATE   = "memory.candidate.submitted"
    MEMORY_STORED      = "memory.entry.stored"
    # Alerts
    ALERT_TRIGGERED    = "alert.triggered"
    DSCR_BREACH        = "alert.dscr_breach"
    # Artifacts
    ARTIFACT_PRODUCED  = "artifact.produced"
    # System
    HARNESS_STARTED    = "system.harness.started"
    HARNESS_STOPPED    = "system.harness.stopped"
    CYCLE_COMPLETED    = "system.cycle.completed"


@dataclass
class AOSEvent:
    """Immutable AOS event."""
    type: EventType
    source_harness: str
    source_agent: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    venture_id: str = "VEN-NETSO-001"


class EventBus:
    """In-process event bus. Thread-safe, append-only log."""

    def __init__(self) -> None:
        self._log: list[AOSEvent] = []
        self._handlers: dict[EventType, list[Callable]] = {}

    def emit(self, event: AOSEvent) -> None:
        """Emit an event. Calls registered handlers synchronously."""
        self._log.append(event)
        for handler in self._handlers.get(event.type, []):
            try:
                handler(event)
            except Exception as exc:
                # Never let a handler crash the bus
                import logging
                logging.getLogger("aos.event_bus").warning(
                    "Handler error for %s: %s", event.type, exc
                )

    def on(self, event_type: EventType, handler: Callable) -> None:
        """Register a handler for an event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    def log(self) -> list[AOSEvent]:
        """Return all events in order."""
        return list(self._log)

    def log_for_harness(self, harness_id: str) -> list[AOSEvent]:
        """Return events emitted by a specific harness."""
        return [e for e in self._log if e.source_harness == harness_id]

    def summary(self) -> dict[str, int]:
        """Count events by type."""
        counts: dict[str, int] = {}
        for e in self._log:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts


# Module-level default bus (can be replaced in tests)
default_bus = EventBus()
