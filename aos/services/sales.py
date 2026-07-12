"""Sales service — sales graph status."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SalesStatus:
    """Sales graph status."""
    total_customers: int
    active_deals: int
    pipeline_value: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_customers": self.total_customers,
            "active_deals": self.active_deals,
            "pipeline_value": self.pipeline_value,
        }


def get_sales_status() -> SalesStatus:
    """Get sales graph status."""
    # Placeholder for future implementation
    return SalesStatus(
        total_customers=0,
        active_deals=0,
        pipeline_value=0.0,
    )
