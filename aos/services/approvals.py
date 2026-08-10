"""Approvals service — approval queue management.

Wired to real ApprovalQueue from aos/approval_queue.py.
Persists to aos/approvals.jsonl for cross-run state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aos.approval_queue import ApprovalQueue, ApprovalDecision


def _get_queue() -> ApprovalQueue:
    """Get the approval queue with persistence."""
    queue_path = Path(__file__).parent.parent / "approvals.jsonl"
    log_path = Path(__file__).parent.parent / "decisions.jsonl"
    return ApprovalQueue(persistence_path=queue_path, decision_log_path=log_path)


@dataclass(frozen=True)
class Approval:
    """Single approval request."""

    id: str
    title: str
    description: str
    status: str  # "pending" | "approved" | "rejected"
    created_at: str
    updated_at: str | None
    agent_id: str | None = None
    risk_assessment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "agent_id": self.agent_id,
            "risk_assessment": self.risk_assessment,
        }


def get_pending_approvals() -> list[Approval]:
    """Get all pending approvals from the real queue."""
    queue = _get_queue()
    return [
        Approval(
            id=item.id,
            title=item.action,
            description=item.rationale,
            status=item.status,
            created_at=item.submitted_at,
            updated_at=item.decided_at,
            agent_id=item.agent_id,
            risk_assessment=item.risk_assessment,
        )
        for item in queue.pending()
    ]


def get_all_approvals() -> list[Approval]:
    """Get all approvals (pending and decided)."""
    queue = _get_queue()
    return [
        Approval(
            id=item.id,
            title=item.action,
            description=item.rationale,
            status=item.status,
            created_at=item.submitted_at,
            updated_at=item.decided_at,
            agent_id=item.agent_id,
            risk_assessment=item.risk_assessment,
        )
        for item in queue.all()
    ]


def approve_request(approval_id: str, note: str | None = None) -> dict[str, Any]:
    """Approve a pending request."""
    queue = _get_queue()
    result = queue.decide(approval_id, ApprovalDecision.APPROVE, founder_note=note)
    if result:
        return {
            "id": result.item_id,
            "status": "approved",
            "message": f"Approval {result.item_id} approved",
        }
    return {
        "id": approval_id,
        "status": "error",
        "message": f"Item {approval_id} not found or already decided",
    }


def reject_request(
    approval_id: str, reason: str = "", note: str | None = None
) -> dict[str, Any]:
    """Reject a pending request."""
    queue = _get_queue()
    founder_note = note or reason
    result = queue.decide(approval_id, ApprovalDecision.REJECT, founder_note=founder_note)
    if result:
        return {
            "id": result.item_id,
            "status": "rejected",
            "reason": reason,
            "message": f"Approval {result.item_id} rejected",
        }
    return {
        "id": approval_id,
        "status": "error",
        "message": f"Item {approval_id} not found or already decided",
    }


def approve_all(note: str | None = None) -> list[dict[str, Any]]:
    """Approve all pending requests."""
    queue = _get_queue()
    results = queue.approve_all(founder_note=note)
    return [
        {"id": r.item_id, "status": "approved", "message": f"Approved {r.item_id}"}
        for r in results
    ]


def reject_all(note: str | None = None) -> list[dict[str, Any]]:
    """Reject all pending requests."""
    queue = _get_queue()
    results = queue.reject_all(founder_note=note)
    return [
        {"id": r.item_id, "status": "rejected", "message": f"Rejected {r.item_id}"}
        for r in results
    ]


def get_resolved_ids() -> list[str]:
    """Get all resolved (approved/rejected) item IDs for cross-run state."""
    queue = _get_queue()
    return [item.id for item in queue.all() if item.status == "decided"]
