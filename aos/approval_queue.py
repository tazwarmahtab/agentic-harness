"""Approval queue — interactive approval management for gated actions.

Agents submit approval requests. The queue bundles them for founder review.
Founder can approve individually, approve all, reject, or review with notes.
Decisions are persisted to disk for audit trail.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"


@dataclass
class ApprovalItem:
    """A single approval request."""

    id: str
    agent_id: str
    action: str
    rationale: str
    risk_assessment: str
    status: str = "pending"
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    decided_at: Optional[str] = None
    founder_note: Optional[str] = None
    decision: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "action": self.action,
            "rationale": self.rationale,
            "risk_assessment": self.risk_assessment,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "decided_at": self.decided_at,
            "founder_note": self.founder_note,
            "decision": self.decision,
        }


@dataclass
class ApprovalResult:
    """Result of a decision on an approval item."""

    item_id: str
    approved: bool
    decision: str
    founder_note: Optional[str] = None
    decided_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ApprovalQueue:
    """Interactive approval queue with persistence."""

    def __init__(
        self,
        persistence_path: Optional[Path] = None,
        decision_log_path: Optional[Path] = None,
    ):
        self._items: dict[str, ApprovalItem] = {}
        self._counter = 0
        self._lock = threading.Lock()
        self._persistence_path = persistence_path
        self._decision_log_path = decision_log_path

        # Load existing state if file exists
        if persistence_path and persistence_path.exists():
            self._load()

    def _next_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"APR-{self._counter:04d}"

    def add(
        self,
        agent_id: str,
        action: str,
        rationale: str,
        risk_assessment: str,
    ) -> ApprovalItem:
        """Add a new approval request to the queue. Thread-safe."""
        item = ApprovalItem(
            id=self._next_id(),
            agent_id=agent_id,
            action=action,
            rationale=rationale,
            risk_assessment=risk_assessment,
        )
        with self._lock:
            self._items[item.id] = item
        self._save()
        return item

    def pending(self) -> list[ApprovalItem]:
        """Return all pending approval items."""
        return [item for item in self._items.values() if item.status == "pending"]

    def all(self) -> list[ApprovalItem]:
        """Return all approval items (pending and decided)."""
        return list(self._items.values())

    def decide(
        self,
        item_id: str,
        decision: ApprovalDecision,
        founder_note: Optional[str] = None,
    ) -> Optional[ApprovalResult]:
        """Make a decision on a pending approval item."""
        item = self._items.get(item_id)
        if not item or item.status != "pending":
            return None

        item.status = "decided"
        item.decision = decision.value
        item.founder_note = founder_note
        item.decided_at = datetime.now().isoformat()

        result = ApprovalResult(
            item_id=item_id,
            approved=(decision == ApprovalDecision.APPROVE),
            decision=decision.value,
            founder_note=founder_note,
        )

        # Log decision
        self._log_decision(item, result)
        self._save()

        return result

    def approve_all(self, founder_note: Optional[str] = None) -> list[ApprovalResult]:
        """Approve all pending items."""
        results = []
        for item in self.pending():
            result = self.decide(item.id, ApprovalDecision.APPROVE, founder_note)
            if result:
                results.append(result)
        return results

    def reject_all(self, founder_note: Optional[str] = None) -> list[ApprovalResult]:
        """Reject all pending items."""
        results = []
        for item in self.pending():
            result = self.decide(item.id, ApprovalDecision.REJECT, founder_note)
            if result:
                results.append(result)
        return results

    def summary(self) -> str:
        """Return a summary of the queue state."""
        pending = self.pending()
        total = len(self._items)
        decided = total - len(pending)

        lines = [
            f"Approval Queue: {len(pending)} pending, {decided} decided, {total} total",
        ]

        if pending:
            lines.append("\nPending approvals:")
            for item in pending:
                lines.append(f"  [{item.id}] {item.action}")
                lines.append(f"    Agent: {item.agent_id}")
                lines.append(f"    Risk: {item.risk_assessment}")
                lines.append(f"    Rationale: {item.rationale[:80]}...")

        return "\n".join(lines)

    def _save(self) -> None:
        """Persist queue state to disk."""
        if not self._persistence_path:
            return

        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._persistence_path, "w") as f:
            for item in self._items.values():
                f.write(json.dumps(item.to_dict()) + "\n")

    def _load(self) -> None:
        """Load queue state from disk."""
        if not self._persistence_path or not self._persistence_path.exists():
            return

        with open(self._persistence_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                item = ApprovalItem(
                    id=data["id"],
                    agent_id=data["agent_id"],
                    action=data["action"],
                    rationale=data["rationale"],
                    risk_assessment=data["risk_assessment"],
                    status=data["status"],
                    submitted_at=data["submitted_at"],
                    decided_at=data.get("decided_at"),
                    founder_note=data.get("founder_note"),
                    decision=data.get("decision"),
                )
                self._items[item.id] = item
                # Update counter
                num = int(item.id.split("-")[1])
                if num > self._counter:
                    self._counter = num

    def _log_decision(self, item: ApprovalItem, result: ApprovalResult) -> None:
        """Append decision to audit log."""
        if not self._decision_log_path:
            return

        self._decision_log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "item_id": item.id,
            "agent_id": item.agent_id,
            "action": item.action,
            "decision": result.decision,
            "founder_note": result.founder_note,
            "decided_at": result.decided_at,
            "submitted_at": item.submitted_at,
        }
        with open(self._decision_log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
