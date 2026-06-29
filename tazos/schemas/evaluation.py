"""Evaluation schema — harness-level and per-specialist evaluation metrics."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class HarnessMetric(BaseModel):
    name: str
    target: str
    frequency: str
    owner: str
    measurement: str


class ImprovementCycleStep(BaseModel):
    step: str
    owner: str
    input: str
    output: str
    artifacts_affected: Optional[list[str]] = None
    artifact: Optional[str] = None
    frequency: Optional[str] = None


class ContinuousImprovement(BaseModel):
    cycle: list[ImprovementCycleStep]
    improvement_sources: list[Any]
    metrics_tracked: list[str]
    review_cadence: Optional[dict[str, list[str]]] = None


class EvaluationPipeline(BaseModel):
    agent_completes_task: Optional[dict[str, str]] = None
    self_check_passes: Optional[dict[str, str]] = None
    evaluator_scores: Optional[dict[str, str]] = None
    result: Optional[dict[str, str]] = None


_EVAL_ID_PATTERN = re.compile(r"^EVAL-[A-Z]+-[0-9]{3}$")


class Evaluation(BaseModel):
    """Harness-level and per-specialist evaluation metrics."""

    id: str
    name: str
    harness: str
    version: str = "1.0.0"
    harness_metrics: list[HarnessMetric]
    specialist_metrics: Optional[dict[str, Any]] = None
    continuous_improvement: ContinuousImprovement
    evaluation_pipeline: Optional[EvaluationPipeline] = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _EVAL_ID_PATTERN.match(v):
            raise ValueError(f"Evaluation ID must match EVAL-XXX-NNN: {v}")
        return v
