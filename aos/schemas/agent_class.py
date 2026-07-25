"""AgentClass schema — structured role definition for harness agents.

Replaces prompt-only agent definitions with enforceable contracts:
tool permissions, allowed actions, review requirements, and escalation targets.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AgentClassStatus(str, Enum):
    DRAFT = "draft"
    DEPLOYED = "deployed"
    RETIRED = "retired"


class ToolPermission(BaseModel):
    """A single tool permission entry."""

    capability: str = Field(..., description="Capability name (e.g. 'read_file', 'execute_code')")
    permission: str = Field(..., description="Permission level: read, write, execute, request_approval")


class EscalationTarget(BaseModel):
    """Where to escalate when this agent class encounters a failure."""

    failure_mode: str = Field(..., description="Failure mode name (e.g. 'tool_failure', 'low_confidence')")
    target: str = Field(..., description="Agent class ID or role to escalate to")


class ReviewRequirement(BaseModel):
    """What must be reviewed and by whom."""

    artifact_type: str = Field(..., description="Type of artifact requiring review")
    reviewer: str = Field(..., description="Agent class ID or role of the reviewer")


_AGENT_CLASS_ID_PATTERN = re.compile(r"^ACL-[A-Z]+-[0-9]{3}$")


class AgentClass(BaseModel):
    """Structured role definition for a harness agent.

    Defines the agent's identity, permissions, enforcement rules,
    escalation paths, and review responsibilities in a machine-readable format.
    """

    id: str
    name: str
    harness: str = Field(..., description="Owning harness ID (e.g. HAR-EXECUTIVE-001)")
    version: str = "1.0.0"
    status: AgentClassStatus = AgentClassStatus.DRAFT
    role: str = Field(..., description="Functional role name (e.g. 'planner', 'specialist', 'reviewer')")
    description: str = ""

    # Permissions
    allowed_tools: list[ToolPermission] = Field(default_factory=list)
    allowed_memory_read: list[str] = Field(default_factory=list)
    allowed_memory_write: list[str] = Field(default_factory=list)
    denied_actions: list[str] = Field(
        default_factory=list,
        description="Actions this agent class must never perform",
    )

    # Enforcement
    enforcement_rules: list[str] = Field(
        default_factory=list,
        description="IDs of enforcement rules that apply to this agent class",
    )

    # Escalation
    escalation_targets: list[EscalationTarget] = Field(default_factory=list)

    # Review responsibilities
    review_requirements: list[ReviewRequirement] = Field(default_factory=list)

    # Constraints
    constraints: list[str] = Field(
        default_factory=list,
        description="Anti-patterns this agent must never violate",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _AGENT_CLASS_ID_PATTERN.match(v):
            raise ValueError(f"AgentClass ID must match ACL-XXX-NNN: {v}")
        return v

    @field_validator("harness")
    @classmethod
    def validate_harness_ref(cls, v: str) -> str:
        if not v.startswith("HAR-"):
            raise ValueError(f"harness reference must start with HAR-: {v}")
        return v
