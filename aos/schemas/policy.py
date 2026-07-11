"""Policy schema — declarative, versioned rule evaluated by the Policy Engine."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class PolicyCategory(str, Enum):
    SECURITY = "security"
    FINANCIAL = "financial"
    LEGAL = "legal"
    COMMERCIAL = "commercial"
    ENGINEERING = "engineering"
    PRIVACY = "privacy"
    AI_SAFETY = "ai_safety"
    COMPLIANCE = "compliance"
    OPERATIONS = "operations"
    EXECUTIVE = "executive"


class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    ESCALATE = "escalate"
    DELAY = "delay"
    LOG_ONLY = "log_only"


class PolicyCondition(BaseModel):
    if_conditions: dict[str, Any] = Field(..., alias="if")
    then: Optional[str] = None
    else_: Optional[str] = Field(None, alias="else")

    model_config = {"populate_by_name": True}


class PolicyStatus(str, Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"
    TEST = "test"


_POL_ID_PATTERN = re.compile(r"^POL-[A-Z]+-[0-9]{3}$")


class Policy(BaseModel):
    """Declarative, versioned rule evaluated by the Policy Engine."""

    id: str
    name: str
    category: PolicyCategory
    version: str = "1.0.0"
    status: PolicyStatus = PolicyStatus.ACTIVE
    description: Optional[str] = None
    rule: PolicyCondition
    action: PolicyAction
    approval_owner: Optional[str] = None
    approval_expires_hours: Optional[int] = Field(None, ge=1)
    source: Optional[str] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _POL_ID_PATTERN.match(v):
            raise ValueError(f"Policy ID must match POL-XXX-NNN: {v}")
        return v
