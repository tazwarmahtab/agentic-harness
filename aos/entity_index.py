"""AOS Entity Index — every concept in AOS is an entity with an identity.

Entities tracked:
    Venture, Customer, Project, Proposal, Contract, Invoice,
    Meeting, Decision, Blocker, Task, Handoff,
    Harness, Agent, Memory, Workflow, Approval, Artifact, Alert

Every entity has: id, venture_id, created_at, created_by, status, version.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    VENTURE = "venture"
    CUSTOMER = "customer"
    PROJECT = "project"
    PROPOSAL = "proposal"
    CONTRACT = "contract"
    INVOICE = "invoice"
    MEETING = "meeting"
    DECISION = "decision"
    BLOCKER = "blocker"
    TASK = "task"
    HANDOFF = "handoff"
    HARNESS = "harness"
    AGENT = "agent"
    MEMORY = "memory"
    WORKFLOW = "workflow"
    APPROVAL = "approval"
    ARTIFACT = "artifact"
    ALERT = "alert"


@dataclass
class Entity:
    id: str
    type: EntityType
    venture_id: str
    name: str
    status: str = "active"
    version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    created_by: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)
    replaced_by: str | None = None

    @classmethod
    def create(
        cls,
        entity_type: EntityType,
        name: str,
        venture_id: str,
        created_by: str = "system",
        **metadata: Any,
    ) -> "Entity":
        prefix = entity_type.value.upper()[:3]
        entity_id = f"{prefix}-{str(uuid.uuid4())[:8].upper()}"
        return cls(
            id=entity_id,
            type=entity_type,
            venture_id=venture_id,
            name=name,
            created_by=created_by,
            metadata=metadata,
        )


class EntityIndex:
    """In-memory entity registry. Append-only writes."""

    def __init__(self) -> None:
        self._store: dict[str, Entity] = {}
        self._by_type: dict[EntityType, list[str]] = {}

    def register(self, entity: Entity) -> Entity:
        self._store[entity.id] = entity
        self._by_type.setdefault(entity.type, []).append(entity.id)
        return entity

    def get(self, entity_id: str) -> Entity | None:
        return self._store.get(entity_id)

    def list_by_type(self, entity_type: EntityType) -> list[Entity]:
        return [
            self._store[eid]
            for eid in self._by_type.get(entity_type, [])
            if eid in self._store
        ]

    def find(self, name: str) -> list[Entity]:
        q = name.lower()
        return [e for e in self._store.values() if q in e.name.lower()]

    def summary(self) -> dict[str, int]:
        return {t.value: len(ids) for t, ids in self._by_type.items()}

    def __len__(self) -> int:
        return len(self._store)


default_index = EntityIndex()
