"""Identity schema — globally unique identity for every TAZ OS object."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class IdentityType(str, Enum):
    HUMAN = "human"
    VENTURE = "venture"
    HARNESS = "harness"
    AGENT = "agent"
    TOOL = "tool"
    POLICY = "policy"
    ARTIFACT = "artifact"
    WORKFLOW = "workflow"
    MEMORY = "memory"
    DOCUMENT = "document"
    PROJECT = "project"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    INVESTOR = "investor"
    MEETING = "meeting"
    TASK = "task"
    EVALUATION = "evaluation"
    SOP = "sop"


class IdentityStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    DEPLOYED = "deployed"
    BLOCKED = "blocked"
    RETIRED = "retired"
    DRAFT = "draft"
    PRODUCTION = "production"


class Classification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    FOUNDER_ONLY = "founder_only"


# Regex: TYPE-CONTEXT-NUMBER or TYPE-NUMBER (HUM only)
_ID_PATTERN = re.compile(
    r"^(HUM|VEN|HAR|AGT|TOL|POL|ART|WRK|MEM|DOC|PRJ|CUS|SUP|INV|MTG|TSK|EVAL|SOP)"
    r"-[A-Z]+-[0-9]{,}$"
    r"|^(HUM)-[0-9]{6}$"
)


class Identity(BaseModel):
    """Globally unique identity for every object in TAZ OS."""

    id: str = Field(
        ..., description="Globally unique. TYPE-CONTEXT-NUMBER or TYPE-NUMBER."
    )
    type: IdentityType
    name: str
    owner: Optional[str] = Field(
        None, description="ID of the owning identity. Null for root."
    )
    status: IdentityStatus
    classification: Classification = Classification.INTERNAL
    created_at: Optional[datetime] = None
    version: str = "1.0.0"

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _ID_PATTERN.match(v):
            raise ValueError(
                f"ID must match TYPE-CONTEXT-NUMBER or HUM-NUMBER format: {v}"
            )
        return v
