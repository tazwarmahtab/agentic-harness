"""Policy Collection schema — harness-level container of approval/governance policies."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class PolicyCollectionStatus(str, Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    TEST = "test"
    PRODUCTION = "production"


class PolicyCollectionRule(BaseModel):
    id: str
    name: str
    category: str
    rule: dict[str, Any]
    action: str
    approval_owner: Optional[str] = None
    approval_expires_hours: Optional[int] = Field(None, ge=1)
    source: Optional[str] = None


class DecisionQueueFormat(BaseModel):
    bundled: Optional[bool] = None
    summary_per_decision: Optional[list[str]] = None
    actions_available: Optional[list[str]] = None
    delivery: Optional[str] = None


class DelegationConfig(BaseModel):
    enabled: Optional[bool] = None
    rule: Optional[str] = None
    format: Optional[dict[str, Any]] = None
    current_delegations: Optional[list[Any]] = None


_POLCOL_ID_PATTERN = re.compile(r"^POL-[A-Z]+-[0-9]{3}$")


class PolicyCollection(BaseModel):
    """Harness-level container of approval/governance policies."""

    id: str
    name: str
    harness: str
    version: str = "1.0.0"
    status: PolicyCollectionStatus
    rules: list[PolicyCollectionRule]
    auto_actions: Optional[list[str]] = None
    decision_queue_format: Optional[DecisionQueueFormat] = None
    delegation: Optional[DelegationConfig] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _POLCOL_ID_PATTERN.match(v):
            raise ValueError(f"Policy collection ID must match POL-XXX-NNN: {v}")
        return v
