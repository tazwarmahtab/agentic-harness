"""System status service — health and metrics."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from aos.health import check_system_health


@dataclass(frozen=True)
class SystemStatus:
    """System status with health score."""
    health_score: float  # 0.0 to 1.0
    uptime: float
    memory_usage_mb: float
    cpu_usage_percent: float
    components: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_score": self.health_score,
            "uptime": self.uptime,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "components": self.components,
        }


# Track start time for uptime calculation
_start_time = time.time()


def get_system_status() -> SystemStatus:
    """Get system status with health score."""
    health = check_system_health()
    uptime = time.time() - _start_time

    # Calculate health score based on component status
    total_components = len(health.components)
    healthy_components = sum(
        1 for c in health.components if c.status == "ok"
    )
    health_score = healthy_components / total_components if total_components > 0 else 0.0

    return SystemStatus(
        health_score=health_score,
        uptime=uptime,
        memory_usage_mb=0.0,  # Placeholder
        cpu_usage_percent=0.0,  # Placeholder
        components=[
            {"name": c.name, "status": c.status, "details": c.details}
            for c in health.components
        ],
    )
