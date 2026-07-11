"""Human gate manager for the orchestrate pipeline.

Wraps the existing ApprovalQueue to provide phase-level gating:
- spec gate: approve spec before planning
- plan gate: approve plan before implementation
- review gate: approve review findings before ship
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from aos.approval_queue import ApprovalQueue, ApprovalDecision, ApprovalItem


class Gate(str, Enum):
    SPEC = "spec"
    PLAN = "plan"
    REVIEW = "review"
    SHIP = "ship"


class GateDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


@dataclass
class GateResult:
    gate: Gate
    decision: GateDecision
    item_id: Optional[str] = None
    founder_note: Optional[str] = None
    decided_at: Optional[str] = None


class GateManager:
    """Manages human-in-the-loop gates for the orchestrate pipeline.

    Each gate creates an ApprovalQueue entry and blocks until the
    founder approves, rejects, or the gate is configured to skip.
    """

    def __init__(
        self,
        queue: Optional[ApprovalQueue] = None,
        persistence_path: Optional[Path] = None,
        decision_log_path: Optional[Path] = None,
    ) -> None:
        self._queue = queue or ApprovalQueue(
            persistence_path=persistence_path,
            decision_log_path=decision_log_path,
        )

    def check(
        self,
        gate: Gate,
        summary: str,
        details: dict[str, Any],
        auto_approve: bool = False,
    ) -> GateResult:
        """Evaluate a gate.

        Args:
            gate: Which gate to evaluate.
            summary: One-line summary for the approval item.
            details: Structured details (stored in rationale for audit).
            auto_approve: If True, skip queue and approve immediately.

        Returns:
            GateResult with the decision.
        """
        if auto_approve:
            return GateResult(gate=gate, decision=GateDecision.APPROVED)

        # Check for pending approvals — if one exists for this gate, it's
        # already been submitted and we should prompt the user to decide.
        pending = self._queue.pending()
        for item in pending:
            if f"[{gate.value} gate]" in item.action:
                self._print_pending(item)
                decision = self._prompt_decision(item.id)
                return GateResult(
                    gate=gate,
                    decision=GateDecision.APPROVED
                    if decision == ApprovalDecision.APPROVE
                    else GateDecision.REJECTED,
                    item_id=item.id,
                    decided_at=datetime.now().isoformat(),
                )

        # No pending item — create one
        rationale = f"{summary}\n\nDetails: {self._fmt_details(details)}"
        item = self._queue.add(
            agent_id="orchestrate",
            action=f"[{gate.value} gate] {summary}",
            rationale=rationale,
            risk_assessment="low" if gate == Gate.SPEC else "medium",
        )

        print(f"\n{'='*60}")
        print(f"  GATE: {gate.value.upper()} — approval required")
        print(f"{'='*60}")
        print(f"  Item:  {item.id}")
        print(f"  {summary}")
        print(f"  Risk:  {item.risk_assessment}")
        print(f"{'='*60}")
        print(f"  Run:   python -m tazos approvals approve {item.id}  # or reject")
        print(f"  Or:    python -m tazos approvals list")
        print(f"{'='*60}\n")

        return GateResult(
            gate=gate,
            decision=GateDecision.SKIPPED,  # pending — will be resolved on next check
            item_id=item.id,
        )

    def resolve_pending(self, gate: Gate) -> Optional[GateResult]:
        """Check if a pending gate has been decided and return the result.

        Returns None if still pending.
        """
        for item in self._queue.all():
            if f"[{gate.value} gate]" in item.action and item.status == "decided":
                approved = item.decision == ApprovalDecision.APPROVE.value
                return GateResult(
                    gate=gate,
                    decision=GateDecision.APPROVED if approved else GateDecision.REJECTED,
                    item_id=item.id,
                    founder_note=item.founder_note,
                    decided_at=item.decided_at,
                )
        return None

    def is_approved(self, gate: Gate) -> bool:
        """Check if a gate has been approved (either auto or manual)."""
        result = self.resolve_pending(gate)
        return result is not None and result.decision == GateDecision.APPROVED

    def is_rejected(self, gate: Gate) -> bool:
        """Check if a gate has been rejected."""
        result = self.resolve_pending(gate)
        return result is not None and result.decision == GateDecision.REJECTED

    def wait_for_decision(
        self,
        item_id: str,
        gate: Gate,
        timeout_s: float = 300,
        poll_interval: float = 2.0,
    ) -> GateResult:
        """Block until the pending gate item is decided or timeout.

        Polls the approval queue for the item to transition from "pending"
        to "decided". Prints status so the user knows we're waiting.

        Returns GateResult with APPROVED/REJECTED if decided, SKIPPED on timeout.
        """
        deadline = time.monotonic() + timeout_s
        print(f"\n  ⏳ Waiting for founder decision on {gate.value} gate ({item_id})...")
        print(f"     Run: python -m tazos approvals approve {item_id}")
        print(f"     Or:  python -m tazos approvals reject {item_id}")
        print(f"     Timeout: {timeout_s:.0f}s\n")

        while time.monotonic() < deadline:
            resolved = self._queue.all()
            for item in resolved:
                if item.id == item_id and item.status == "decided":
                    approved = item.decision == ApprovalDecision.APPROVE.value
                    decision = GateDecision.APPROVED if approved else GateDecision.REJECTED
                    print(f"  ✓ Gate {gate.value} {decision.value} by founder.")
                    return GateResult(
                        gate=gate,
                        decision=decision,
                        item_id=item.id,
                        founder_note=item.founder_note,
                        decided_at=item.decided_at,
                    )
            time.sleep(poll_interval)

        print(f"  ⏰ Gate {gate.value} timed out after {timeout_s:.0f}s. Pipeline stopping.")
        return GateResult(gate=gate, decision=GateDecision.SKIPPED, item_id=item_id)

    def _print_pending(self, item: ApprovalItem) -> None:
        print(f"\n{'='*60}")
        print(f"  PENDING approval: {item.id}")
        print(f"  {item.action}")
        print(f"  Rationale: {item.rationale[:120]}...")
        print(f"{'='*60}\n")

    def _prompt_decision(self, item_id: str) -> ApprovalDecision:
        """Block and wait for a terminal decision on the item."""
        while True:
            raw = input(f"Decision for {item_id} [approve/reject]: ").strip().lower()
            if raw in ("approve", "a", "yes", "y"):
                return ApprovalDecision.APPROVE
            if raw in ("reject", "r", "no", "n"):
                return ApprovalDecision.REJECT
            print("Enter 'approve' or 'reject'.")

    @staticmethod
    def _fmt_details(details: dict[str, Any]) -> str:
        parts = []
        for k, v in details.items():
            parts.append(f"{k}={v}")
        return "; ".join(parts) if parts else "none"
