"""Agent schema — an autonomous worker within a harness."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class AgentStatus(str, Enum):
    DRAFT = "draft"
    DEPLOYED = "deployed"
    PRODUCTION = "production"
    IDLE = "idle"
    BLOCKED = "blocked"
    RETIRED = "retired"


class AgentCriticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolPermission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    REQUEST_APPROVAL = "request_approval"


class AgentInput(BaseModel):
    name: str
    type: str
    required: bool


class AgentOutput(BaseModel):
    name: str
    type: str
    becomes_artifact: bool = True
    artifact_type: Optional[str] = None
    classification: Optional[str] = None


class AllowedMemory(BaseModel):
    read: list[str]
    write: list[str]
    cannot_read: list[str]


class ToolCapability(BaseModel):
    capability: str
    permission: ToolPermission


class EvaluationMetric(BaseModel):
    metric: str
    weight: float = Field(..., ge=0, le=1)
    hard_fail_if: Optional[str] = None


class FailureHandling(BaseModel):
    missing_information: Optional[str] = None
    tool_failure: Optional[str] = None
    low_confidence: Optional[str] = None
    policy_conflict: Optional[str] = None


class ModelConfig(BaseModel):
    preferred: Optional[str] = None
    fallback: Optional[list[str]] = None


class DelegationHeuristic(BaseModel):
    if_conditions: list[str] = Field(..., alias="if")
    then: dict[str, Optional[str]]

    model_config = {"populate_by_name": True}


class RoutingEntry(BaseModel):
    task: str
    route_to: str
    sla: str
    escalation: Optional[str] = None
    harness: Optional[str] = None


class RoutingTable(BaseModel):
    executive_internal: Optional[list[RoutingEntry]] = None
    cross_harness: Optional[list[RoutingEntry]] = None


class TaskLifecycle(BaseModel):
    states: Optional[list[str]] = None
    transitions: Optional[list[dict[str, Any]]] = None
    rules: Optional[list[str]] = None


_AGT_ID_PATTERN = re.compile(r"^AGT-[A-Z]+-[0-9A-Z]+$")


class Agent(BaseModel):
    """An autonomous worker that executes a well-defined capability within a harness."""

    id: str
    name: str
    harness: str
    version: str = "1.0.0"
    status: AgentStatus
    criticality: AgentCriticality
    mission: str = Field(..., description="Exactly one sentence.")
    source_persona: Optional[str] = None
    persona_source: Optional[str] = None
    note: Optional[str] = None
    capabilities: list[str] = []
    inputs: list[AgentInput] = []
    outputs: list[AgentOutput] = []
    allowed_memory: AllowedMemory
    allowed_tools: list[ToolCapability] = []
    reasoning_structure: list[str] = []
    self_check: list[str] = []
    evaluation: list[EvaluationMetric] = []
    failure_handling: Optional[FailureHandling] = None
    financial_rules: Optional[dict[str, Any]] = None
    risk_categories: Optional[dict[str, Any]] = None
    escalation_rules: Optional[list[dict[str, Any]]] = None
    models: Optional[ModelConfig] = None
    constraints: list[str] = []

    # Role-specific fields (planner, dispatcher, chief-of-staff, perf analyst)
    planner_prompt: Optional[str] = None
    priority_framework: Optional[dict[str, Any]] = None
    delegation_heuristics: Optional[list[DelegationHeuristic]] = None
    routing_table: Optional[RoutingTable] = None
    handoff_format: Optional[str] = None
    task_lifecycle: Optional[TaskLifecycle] = None
    daily_brief_format: Optional[str] = None
    meeting_prep_pack_includes: Optional[list[str]] = None
    decision_log_format: Optional[dict[str, str]] = None
    tracked_kpis: Optional[dict[str, list[str]]] = None
    drift_thresholds: Optional[dict[str, dict[str, str]]] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _AGT_ID_PATTERN.match(v):
            raise ValueError(f"Agent ID must match AGT-XXX-XXXX: {v}")
        return v
