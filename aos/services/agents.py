"""Agents service — agent usage and status."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentStatus:
    """Agent status summary."""
    total_agents: int
    active_agents: int
    agents: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_agents": self.total_agents,
            "active_agents": self.active_agents,
            "agents": self.agents,
        }


def get_agents_status() -> AgentStatus:
    """Get agents status summary."""
    # Placeholder for future implementation
    return AgentStatus(
        total_agents=0,
        active_agents=0,
        agents=[],
    )
