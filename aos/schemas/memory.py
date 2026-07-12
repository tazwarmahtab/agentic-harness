"""Memory schema — shared memory for a harness with three layers."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, field_validator


class LongTermEntry(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None
    ref: Optional[str] = None
    description: Optional[str] = None
    classification: Optional[str] = None


class EpisodicEntry(BaseModel):
    ref: Optional[str] = None
    path: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    write_access: Optional[list[str]] = None
    classification: Optional[str] = None
    format: Optional[dict[str, str]] = None


class SemanticEntry(BaseModel):
    ref: Optional[str] = None
    description: Optional[str] = None
    classification: Optional[str] = None


class MemoryLayers(BaseModel):
    long_term: Optional[dict[str, Any]] = None
    episodic: Optional[dict[str, Any]] = None
    semantic: Optional[dict[str, Any]] = None


class MemoryPermission(BaseModel):
    read: list[str]
    write: list[str]
    cannot_read: list[str]


class UpdateRules(BaseModel):
    agents_submit_memory_candidates: Optional[bool] = None
    reflection_engine_decides: Optional[list[str]] = None
    purpose: Optional[str] = None
    audit: Optional[str] = None


_MEM_ID_PATTERN = re.compile(r"^MEM-[A-Z]+-[0-9]{3}$")


class Memory(BaseModel):
    """Shared memory for a harness with three layers."""

    id: str
    name: str
    harness: str
    version: str = "1.0.0"
    layers: MemoryLayers
    permissions: Optional[dict[str, MemoryPermission]] = None
    update_rules: Optional[UpdateRules] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _MEM_ID_PATTERN.match(v):
            raise ValueError(f"Memory ID must match MEM-XXX-NNN: {v}")
        return v
