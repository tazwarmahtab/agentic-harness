"""Tool schema — capability-based tool registry for a harness."""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, field_validator


class ToolCategory(str, Enum):
    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    FINANCE = "finance"
    CRM = "crm"
    INTERNAL = "internal"
    KNOWLEDGE = "knowledge"
    GOVERNANCE = "governance"


class ToolStatus(str, Enum):
    REGISTERED = "registered"
    WIRED = "wired"
    DEPRECATED = "deprecated"


class ToolPermissions(BaseModel):
    read: Optional[list[str]] = None
    write: Optional[list[str]] = None
    execute: Optional[Union[list[str], str]] = None


class ToolInputs(BaseModel):
    required: Optional[list[str]] = None
    optional: Optional[list[str]] = None


class RateLimits(BaseModel):
    max_per_hour: Optional[int] = None
    max_per_day: Optional[int] = None


class RetryPolicy(BaseModel):
    max_attempts: Optional[int] = None
    backoff: Optional[str] = None


class ToolValidation(BaseModel):
    must_use: Optional[str] = None
    hard_fail_if: Optional[str] = None


class ToolEntry(BaseModel):
    id: str
    name: str
    capability: str
    category: ToolCategory
    version: str = "1.0.0"
    status: ToolStatus
    permissions: ToolPermissions
    inputs: Optional[ToolInputs] = None
    outputs: Optional[list[str]] = None
    rate_limits: Optional[RateLimits] = None
    retry_policy: Optional[RetryPolicy] = None
    cost_model: Optional[str] = None
    approval_gate: Optional[str] = None
    fallback: Optional[Union[str, list[str], None]] = None
    validation: Optional[ToolValidation] = None
    note: Optional[str] = None
    format: Optional[str] = None


class ToolCompositionStep(BaseModel):
    capability: str
    gate: Optional[str] = None


class ToolComposition(BaseModel):
    name: str
    steps: list[ToolCompositionStep]
    owner: str


class ProviderEntry(BaseModel):
    preferred: Optional[str] = None
    fallback: Optional[list[str]] = None


_TOL_ID_PATTERN = re.compile(r"^TOL-[A-Z]+-[0-9]{3}$")


class ToolRegistry(BaseModel):
    """Capability-based tool definitions for a harness."""

    id: str
    name: str
    harness: str
    version: str = "1.0.0"
    tools: list[ToolEntry]
    compositions: Optional[list[ToolComposition]] = None
    providers: Optional[dict[str, ProviderEntry]] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _TOL_ID_PATTERN.match(v):
            raise ValueError(f"Tool registry ID must match TOL-XXX-NNN: {v}")
        return v
