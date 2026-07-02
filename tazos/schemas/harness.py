"""Harness schema — a self-contained business system."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class HarnessStatus(str, Enum):
    DRAFT = "draft"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class Criticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Frequency(str, Enum):
    REALTIME = "realtime"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ArtifactType(str, Enum):
    DAILY_BRIEF = "daily_brief"
    WEEKLY_REPORT = "weekly_report"
    BOARD_REPORT = "board_report"
    DECISION_QUEUE = "decision_queue"
    HANDOFF = "handoff"
    ESCALATION = "escalation"
    DECISION_LOG = "decision_log"
    MEETING_PREP = "meeting_prep"
    RISK_REPORT = "risk_report"
    KPI_DASHBOARD = "kpi_dashboard"
    WEEKLY_REPORT_SECTION = "weekly_report_section"
    RISK_STATE = "risk_state"


class OutputType(str, Enum):
    ARTIFACT = "artifact"
    EVENT = "event"
    MEMORY_WRITE = "memory_write"


class DataSource(BaseModel):
    source: str
    items: Optional[list[str]] = None
    ref: Optional[str] = None


class HarnessOutput(BaseModel):
    name: str
    type: OutputType
    artifact_type: Optional[ArtifactType] = None
    frequency: Optional[Frequency] = None
    owner: Optional[str] = None
    classification: Optional[str] = None
    description: Optional[str] = None


class KPI(BaseModel):
    name: str
    target: str
    frequency: Optional[Frequency] = None
    owner: Optional[str] = None


class Scope(BaseModel):
    in_scope: list[str]
    out_of_scope: list[str]


class Components(BaseModel):
    planner: Optional[str] = None
    dispatcher: Optional[str] = None
    specialists_dir: Optional[str] = None
    memory: Optional[str] = None
    tools: Optional[str] = None
    approvals: Optional[str] = None
    evaluation: Optional[str] = None
    sops_dir: Optional[str] = None


class TeamMember(BaseModel):
    """A member of an agent team with a defined role."""
    agent_id: str
    role: str = "specialist"
    weight: float = 1.0


class AgentTeam(BaseModel):
    """A team of agents that collaborate on complex tasks.

    Supports backward-compatible loading: if `lead`/`members` are missing
    but `specialists` (legacy flat list) is present, they are populated
    automatically from YAML-side unknowns via the loader.
    """
    id: str
    name: str
    description: Optional[str] = None
    lead: Optional[str] = None
    members: list[TeamMember] = []
    coordination_strategy: str = "sequential"
    # Legacy field — kept for partial backward compatibility during migration
    specialists: list[str] = []


class ExecutionCycle(BaseModel):
    name: Optional[str] = None
    trigger: Optional[str] = None
    steps: Optional[list[dict[str, Any] | str]] = None


_HARNESS_ID_PATTERN = re.compile(r"^HAR-[A-Z]+-[0-9]{3}$")


class Harness(BaseModel):
    """A self-contained business system with mission, scope, KPIs, inputs, outputs."""

    id: str
    name: str
    venture: str
    version: str = "1.0.0"
    status: HarnessStatus
    criticality: Optional[Criticality] = None
    mission: str = Field(..., description="Exactly one sentence.")
    scope: Scope
    kpis: list[KPI]
    inputs: list[dict[str, Any]]
    outputs: list[HarnessOutput]
    components: Optional[Components] = None
    execution_cycle: Optional[ExecutionCycle] = None
    teams: Optional[list[AgentTeam]] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _HARNESS_ID_PATTERN.match(v):
            raise ValueError(f"Harness ID must match HAR-XXX-NNN: {v}")
        return v
