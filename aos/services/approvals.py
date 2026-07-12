"""Approvals service — approval queue management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Approval:
    """Single approval request."""

    id: str
    title: str
    description: str
    status: str  # "pending" | "approved" | "rejected"
    created_at: str
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def get_pending_approvals() -> list[Approval]:
    """Get all pending approvals."""
    # Placeholder for future implementation
    return []


def approve_request(approval_id: str) -> dict[str, Any]:
    """Approve a pending request."""
    return {
        "id": approval_id,
        "status": "approved",
        "message": f"Approval {approval_id} approved",
    }


def reject_request(approval_id: str, reason: str = "") -> dict[str, Any]:
    """Reject a pending request."""
    return {
        "id": approval_id,
        "status": "rejected",
        "reason": reason,
        "message": f"Approval {approval_id} rejected",
    }
