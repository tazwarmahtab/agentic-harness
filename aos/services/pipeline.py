"""Pipeline service — status and control endpoints."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PipelineStatus:
    """Pipeline execution status."""
    active: bool
    current_step: str | None
    progress: float  # 0.0 to 1.0
    total_steps: int
    completed_steps: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "current_step": self.current_step,
            "progress": self.progress,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
        }


def get_pipeline_status() -> PipelineStatus:
    """Get current pipeline execution status."""
    # For now, return a default status
    # In production, this would query the actual pipeline state
    return PipelineStatus(
        active=False,
        current_step=None,
        progress=0.0,
        total_steps=0,
        completed_steps=0,
    )


def get_pipeline_history() -> list[dict[str, Any]]:
    """Get pipeline execution history."""
    # Placeholder for future implementation
    return []
