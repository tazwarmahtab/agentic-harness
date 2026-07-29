"""Deal pipeline tracking — treats each potential customer as a game level."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DealStage(Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    LOI_SIGNED = "loi_signed"
    PPA_DRAFT = "ppa_draft"
    PPA_SIGNED = "ppa_signed"
    SITE_ASSESSMENT = "site_assessment"
    INSTALLATION = "installation"
    COMMISSIONED = "commissioned"
    REVENUE = "revenue"

    @property
    def next(self) -> DealStage | None:
        stages = list(DealStage)
        idx = stages.index(self)
        return stages[idx + 1] if idx + 1 < len(stages) else None

    @property
    def index(self) -> int:
        return list(DealStage).index(self)


@dataclass
class Deal:
    id: str
    customer: str
    stage: DealStage
    venture: str
    capacity_kw: float = 0.0
    ppa_rate: float = 10.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def advance(self) -> DealStage | None:
        next_stage = self.stage.next
        if next_stage:
            self.stage = next_stage
            self.updated_at = datetime.now(timezone.utc).isoformat()
        return next_stage

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer": self.customer,
            "stage": self.stage.value,
            "venture": self.venture,
            "capacity_kw": self.capacity_kw,
            "ppa_rate": self.ppa_rate,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Deal:
        return cls(
            id=d["id"],
            customer=d["customer"],
            stage=DealStage(d["stage"]),
            venture=d.get("venture", "unknown"),
            capacity_kw=d.get("capacity_kw", 0.0),
            ppa_rate=d.get("ppa_rate", 10.0),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            notes=d.get("notes", []),
            metadata=d.get("metadata", {}),
        )


@dataclass
class DealPipeline:
    venture: str
    deals: list[Deal] = field(default_factory=list)
    stages: list[DealStage] = field(default_factory=lambda: list(DealStage))

    def add_deal(self, deal: Deal) -> None:
        self.deals.append(deal)

    def by_stage(self, stage: DealStage) -> list[Deal]:
        return [d for d in self.deals if d.stage == stage]

    def summary(self) -> dict[str, int]:
        return {stage.value: len(self.by_stage(stage)) for stage in self.stages}

    def total_pipeline_value(self) -> float:
        return sum(d.capacity_kw * d.ppa_rate for d in self.deals if d.capacity_kw > 0)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "venture": self.venture,
            "deals": [d.to_dict() for d in self.deals],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> DealPipeline:
        path = Path(path)
        with open(path) as f:
            data = json.load(f)
        pipeline = cls(venture=data["venture"])
        for d in data.get("deals", []):
            pipeline.add_deal(Deal.from_dict(d))
        return pipeline
