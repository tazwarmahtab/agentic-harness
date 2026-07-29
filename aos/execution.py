"""Inspectable execution context for multi-agent workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ExecutionBudget:
    max_steps: int = 50
    max_tokens: int | None = None
    max_duration_s: float | None = None

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if self.max_duration_s is not None and self.max_duration_s <= 0:
            raise ValueError("max_duration_s must be positive")


@dataclass(frozen=True)
class ExecutionDecision:
    actor: str
    decision: str
    rationale: str
    evidence: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class AgentHandoff:
    from_agent: str
    to_agent: str
    task: str
    acceptance_criteria: list[str] = field(default_factory=list)
    status: str = "queued"


@dataclass
class ExecutionTrace:
    task_id: str
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)
    scratchpad: dict[str, Any] = field(default_factory=dict)
    decisions: list[ExecutionDecision] = field(default_factory=list)
    handoffs: list[AgentHandoff] = field(default_factory=list)
    steps_completed: int = 0
    tokens_used: int = 0
    stop_reason: str | None = None

    def record_step(self, *, tokens: int = 0) -> None:
        self.steps_completed += 1
        self.tokens_used += max(tokens, 0)
        if self.steps_completed >= self.budget.max_steps:
            self.stop_reason = "step_budget_exhausted"
        elif self.budget.max_tokens is not None and self.tokens_used >= self.budget.max_tokens:
            self.stop_reason = "token_budget_exhausted"

    def add_decision(self, decision: ExecutionDecision) -> None:
        self.decisions.append(decision)

    def add_handoff(self, handoff: AgentHandoff) -> None:
        self.handoffs.append(handoff)

    def stop(self, reason: str) -> None:
        self.stop_reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "budget": asdict(self.budget),
            "scratchpad": self.scratchpad,
            "decisions": [asdict(d) for d in self.decisions],
            "handoffs": [asdict(h) for h in self.handoffs],
            "steps_completed": self.steps_completed,
            "tokens_used": self.tokens_used,
            "stop_reason": self.stop_reason,
        }
