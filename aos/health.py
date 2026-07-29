"""AOS System Health — aggregates platform component health.

Used by /health/ready and startup checks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentHealth:
    name: str
    status: str  # "ok" | "degraded" | "down"
    details: str = ""
    required: bool = True


@dataclass
class SystemHealth:
    components: list[ComponentHealth] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(c.status == "down" and c.required for c in self.components):
            return "down"
        if any(c.status == "degraded" for c in self.components):
            return "degraded"
        return "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "components": [
                {"name": c.name, "status": c.status, "details": c.details}
                for c in self.components
            ],
        }


def check_system_health(memory_store=None) -> SystemHealth:
    """Run all component health checks and return aggregated result."""
    health = SystemHealth()

    # LLM providers
    anthropic_ok = bool(
        os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    )
    local_ok = bool(os.getenv("AOS_LLM_BASE_URL"))
    nvidia_ok = bool(os.getenv("NVIDIA_NIM_API_KEY"))

    if anthropic_ok or local_ok or nvidia_ok:
        active = ", ".join(
            p
            for p, ok in [
                ("anthropic", anthropic_ok),
                ("local", local_ok),
                ("nvidia", nvidia_ok),
            ]
            if ok
        )
        health.components.append(
            ComponentHealth("llm_provider", "ok", f"active: {active}")
        )
    else:
        health.components.append(
            ComponentHealth(
                "llm_provider",
                "down",
                "No LLM provider configured",
                required=False,
            )
        )

    # Auth token
    token = os.getenv("AOS_API_TOKEN")
    health.components.append(
        ComponentHealth(
            "api_token",
            "ok" if token else "degraded",
            "" if token else "AOS_API_TOKEN not set — WebSocket unauthenticated",
            required=False,
        )
    )

    # Memory store
    if memory_store is not None:
        try:
            count = sum(
                len(entries)
                for layer in memory_store.layers.values()
                for entries in layer.values()
            )
            health.components.append(
                ComponentHealth("memory_store", "ok", f"{count} entries loaded")
            )
        except Exception as exc:
            health.components.append(
                ComponentHealth("memory_store", "degraded", str(exc))
            )
    else:
        health.components.append(
            ComponentHealth("memory_store", "ok", "lazy init", required=False)
        )

    return health
