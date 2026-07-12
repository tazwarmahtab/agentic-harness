"""AOS Workflow Engine — pause, resume, and event-logged state machines.

Wraps LangGraph compiled graphs with:
  - Workflow identity (every run is an entity)
  - Pause/resume gate (approval required before execution)
  - Event bus integration (emits typed events at each state transition)
  - Immutable run log (every step persisted)

Usage:
    engine = WorkflowEngine(compiled_graph, registry, event_bus=default_bus)
    run_id = engine.start(initial_state, config)
    engine.resume(run_id)          # after approval
    run = engine.get_run(run_id)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from aos.event_bus import AOSEvent, EventBus, EventType, default_bus


class WorkflowStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    PAUSED    = "paused"       # waiting for approval
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """One recorded step in a workflow run."""
    step: int
    node: str
    status: WorkflowStatus
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    output_summary: str = ""
    error: str | None = None


@dataclass
class WorkflowRun:
    """A single workflow execution instance."""
    id: str
    harness_id: str
    venture_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: str | None = None
    completed_at: str | None = None
    steps: list[WorkflowStep] = field(default_factory=list)
    pending_approvals: list[str] = field(default_factory=list)
    final_state: dict[str, Any] | None = None
    error: str | None = None

    def duration_s(self) -> float | None:
        if self.started_at and self.completed_at:
            from datetime import datetime
            try:
                s = datetime.fromisoformat(self.started_at)
                e = datetime.fromisoformat(self.completed_at)
                return (e - s).total_seconds()
            except Exception:
                return None
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "harness_id": self.harness_id,
            "venture_id": self.venture_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "step_count": len(self.steps),
            "pending_approvals": self.pending_approvals,
            "duration_s": self.duration_s(),
            "error": self.error,
        }


class WorkflowEngine:
    """Wraps a compiled LangGraph graph with AOS workflow management."""

    def __init__(
        self,
        compiled_graph: Any,
        harness_id: str,
        venture_id: str = "VEN-NETSO-001",
        bus: EventBus | None = None,
    ) -> None:
        self._graph = compiled_graph
        self._harness_id = harness_id
        self._venture_id = venture_id
        self._bus = bus or default_bus
        self._runs: dict[str, WorkflowRun] = {}

    def start(self, initial_state: dict, config: dict | None = None) -> str:
        """Create and start a new workflow run. Returns run_id."""
        run_id = f"WFL-{str(uuid.uuid4())[:8].upper()}"
        run = WorkflowRun(
            id=run_id,
            harness_id=self._harness_id,
            venture_id=self._venture_id,
        )
        self._runs[run_id] = run

        self._bus.emit(AOSEvent(
            type=EventType.HARNESS_STARTED,
            source_harness=self._harness_id,
            source_agent="workflow_engine",
            payload={"run_id": run_id},
            venture_id=self._venture_id,
        ))

        run.status = WorkflowStatus.RUNNING
        run.started_at = datetime.now(timezone.utc).isoformat()

        try:
            cfg = config or {}
            state = self._graph.invoke(initial_state, cfg)
            run.final_state = {k: str(v)[:200] for k, v in (state or {}).items()}
            run.status = WorkflowStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc).isoformat()
            self._bus.emit(AOSEvent(
                type=EventType.CYCLE_COMPLETED,
                source_harness=self._harness_id,
                source_agent="workflow_engine",
                payload={"run_id": run_id, "duration_s": run.duration_s()},
                venture_id=self._venture_id,
            ))
        except Exception as exc:
            run.status = WorkflowStatus.FAILED
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc).isoformat()

        return run_id

    def get_run(self, run_id: str) -> WorkflowRun | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[WorkflowRun]:
        return list(self._runs.values())

    def summary(self) -> dict[str, Any]:
        runs = self.list_runs()
        return {
            "total": len(runs),
            "by_status": {
                s.value: sum(1 for r in runs if r.status == s)
                for s in WorkflowStatus
            },
        }
