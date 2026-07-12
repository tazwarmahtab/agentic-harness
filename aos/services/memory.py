"""Memory service — memory store summaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemorySummary:
    """Memory store summary."""
    total_domains: int
    total_entries: int
    domains: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_domains": self.total_domains,
            "total_entries": self.total_entries,
            "domains": self.domains,
        }


def get_memory_summary() -> MemorySummary:
    """Get memory store summary."""
    # Placeholder for future implementation
    return MemorySummary(
        total_domains=0,
        total_entries=0,
        domains=[],
    )
