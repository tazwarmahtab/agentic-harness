"""Venture schema — a business venture mounted into TAZ OS."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class VentureStatus(str, Enum):
    ACTIVE = "active"
    PLANNING = "planning"
    PAUSED = "paused"
    ARCHIVED = "archived"
    DRAFT = "draft"


class HumanIdentity(BaseModel):
    id: str
    name: str
    role: str
    status: str
    classification: Optional[str] = None
    approval_authority: Optional[bool] = None


class AIRehoming(BaseModel):
    persona: str
    becomes: str
    persona_source: str


class DispatchSpecialist(BaseModel):
    persona: str
    domain: str
    role: str


class ArtifactEntry(BaseModel):
    path: str
    role: Optional[str] = None
    generator: Optional[str] = None
    classification: Optional[str] = None
    rule: Optional[str] = None


class FinancialConstants(BaseModel):
    capex_per_kw_scenario_a: Optional[float] = None
    capex_per_kw_scenario_b: Optional[float] = None
    capex_default_scenario: Optional[str] = None
    true_variable_rate: Optional[float] = None
    blended_rate: Optional[float] = None
    ppa_rate: Optional[float] = None
    customer_savings_pct: Optional[float] = None
    nem_export_rate: Optional[float] = None
    idcol_debt_pct: Optional[float] = None
    idcol_interest: Optional[float] = None
    idcol_term_years: Optional[int] = None
    dscr_scenario_a: Optional[float] = None
    dscr_scenario_b: Optional[float] = None
    dscr_alert_floor: Optional[float] = None
    capacity_factor: Optional[float] = None
    opex_per_kw: Optional[float] = None


_VEN_ID_PATTERN = re.compile(r"^VEN-[A-Z]+-[0-9]{3}$")


class Venture(BaseModel):
    """A business venture mounted into TAZ OS."""

    id: str
    name: str
    type: str = "venture"
    status: VentureStatus
    classification: Optional[str] = None
    version: str = "1.0.0"
    created_at: Optional[str] = None
    description: Optional[str] = None
    identities: dict[str, Any]
    dispatch_only_specialists: Optional[list[DispatchSpecialist]] = None
    artifacts: dict[str, ArtifactEntry]
    financial_constants: Optional[FinancialConstants] = None
    approval_thresholds: Optional[dict[str, float]] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _VEN_ID_PATTERN.match(v):
            raise ValueError(f"Venture ID must match VEN-XXX-NNN: {v}")
        return v
