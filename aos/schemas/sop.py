"""SOP schema — declarative standard operating procedure."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StartupStep(BaseModel):
    action: str
    artifact: str
    purpose: str


class ShutdownStep(BaseModel):
    action: str
    artifact: str
    owner: str
    rule: str


class GatedAction(BaseModel):
    action: str
    gate: str
    threshold: Optional[str] = None
    owner: str
    expires: Optional[str] = None


class EscalatedAction(BaseModel):
    trigger: str
    gate: Optional[str] = None
    notify: str
    urgency: str
    source: Optional[str] = None


class RoutingTable(BaseModel):
    auto: Optional[list[str]] = None
    gated: Optional[list[GatedAction]] = None
    escalated: Optional[list[EscalatedAction]] = None


class QueueProcessStep(BaseModel):
    model_config = ConfigDict(extra="allow")


class ExpirationRules(BaseModel):
    rule: Optional[str] = None
    action: Optional[str] = None
    notification: Optional[str] = None


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


_SOP_ID_PATTERN = re.compile(r"^SOP-[A-Z]+-[0-9]{3}$")


class SOP(BaseModel):
    """Declarative standard operating procedure."""

    id: str
    name: str
    owner: str
    version: str = "1.0.0"
    source: Optional[str] = None
    trigger: Optional[str] = None
    principle: Optional[str] = None
    startup_protocol: Optional[dict[str, StartupStep]] = None
    shutdown_protocol: Optional[dict[str, ShutdownStep]] = None
    rules: Optional[list[str]] = None
    routing: Optional[RoutingTable] = None
    queue_process: Optional[list[dict[str, Any]]] = None
    expiration: Optional[ExpirationRules] = None
    decision_queue_format: Optional[DecisionQueueFormat] = None
    delegation: Optional[DelegationConfig] = None
    brief_format: Optional[str] = None
    daily_brief_format: Optional[str] = None
    decision_log_format: Optional[dict[str, str]] = None
    meeting_prep_pack_includes: Optional[list[str]] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _SOP_ID_PATTERN.match(v):
            raise ValueError(f"SOP ID must match SOP-XXX-NNN: {v}")
        return v
