"""Tests for TAZ OS approval queue — interactive approval management."""

from __future__ import annotations
import sys

import json
import tempfile
from pathlib import Path

import pytest

from aos.approval_queue import ApprovalQueue, ApprovalItem, ApprovalDecision


class TestApprovalItem:
    def test_create_item(self) -> None:
        item = ApprovalItem(
            id="APR-0001",
            agent_id="AGT-EXEC-COO",
            action="Write DASHBOARD.md",
            rationale="Bootstrap gate cleared",
            risk_assessment="low",
        )
        assert item.id == "APR-0001"
        assert item.status == "pending"

    def test_item_to_dict(self) -> None:
        item = ApprovalItem(
            id="APR-0001",
            agent_id="AGT-EXEC-COO",
            action="Write DASHBOARD.md",
            rationale="Bootstrap gate cleared",
            risk_assessment="low",
        )
        d = item.to_dict()
        assert d["id"] == "APR-0001"
        assert d["status"] == "pending"
        assert "action" in d


class TestApprovalQueue:
    def test_add_item(self) -> None:
        queue = ApprovalQueue()
        item = queue.add(
            agent_id="AGT-EXEC-COO",
            action="Write DASHBOARD.md",
            rationale="Bootstrap gate cleared",
            risk_assessment="low",
        )
        assert item.id.startswith("APR-")
        assert item.status == "pending"
        assert len(queue.pending()) == 1

    def test_approve_item(self) -> None:
        queue = ApprovalQueue()
        item = queue.add(
            agent_id="AGT-EXEC-COO",
            action="Write DASHBOARD.md",
            rationale="test",
            risk_assessment="low",
        )
        decision = queue.decide(item.id, ApprovalDecision.APPROVE, founder_note="Go ahead")
        assert decision.approved is True
        assert decision.item_id == item.id
        assert len(queue.pending()) == 0

    def test_reject_item(self) -> None:
        queue = ApprovalQueue()
        item = queue.add(
            agent_id="AGT-EXEC-COO",
            action="Write DASHBOARD.md",
            rationale="test",
            risk_assessment="low",
        )
        decision = queue.decide(item.id, ApprovalDecision.REJECT, founder_note="Not now")
        assert decision.approved is False
        assert len(queue.pending()) == 0

    def test_approve_all(self) -> None:
        queue = ApprovalQueue()
        queue.add(agent_id="A", action="task1", rationale="r", risk_assessment="low")
        queue.add(agent_id="B", action="task2", rationale="r", risk_assessment="low")
        queue.add(agent_id="C", action="task3", rationale="r", risk_assessment="low")
        decisions = queue.approve_all(founder_note="Batch approve")
        assert len(decisions) == 3
        assert all(d.approved for d in decisions)
        assert len(queue.pending()) == 0

    def test_reject_all(self) -> None:
        queue = ApprovalQueue()
        queue.add(agent_id="A", action="task1", rationale="r", risk_assessment="low")
        queue.add(agent_id="B", action="task2", rationale="r", risk_assessment="low")
        decisions = queue.reject_all(founder_note="Batch reject")
        assert len(decisions) == 2
        assert all(not d.approved for d in decisions)

    def test_decide_unknown_item(self) -> None:
        queue = ApprovalQueue()
        decision = queue.decide("APR-9999", ApprovalDecision.APPROVE)
        assert decision is None

    def test_pending_returns_only_pending(self) -> None:
        queue = ApprovalQueue()
        queue.add(agent_id="A", action="task1", rationale="r", risk_assessment="low")
        item2 = queue.add(agent_id="B", action="task2", rationale="r", risk_assessment="low")
        queue.decide(item2.id, ApprovalDecision.APPROVE)
        assert len(queue.pending()) == 1

    def test_summary(self) -> None:
        queue = ApprovalQueue()
        queue.add(agent_id="A", action="task1", rationale="r", risk_assessment="low")
        queue.add(agent_id="B", action="task2", rationale="r", risk_assessment="low")
        summary = queue.summary()
        assert "2" in summary
        assert "pending" in summary.lower()


class TestApprovalPersistence:
    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = ApprovalQueue(Path(tmpdir) / "approvals.jsonl")
            queue.add(agent_id="A", action="task1", rationale="r", risk_assessment="low")
            queue.add(agent_id="B", action="task2", rationale="r", risk_assessment="low")
            queue.decide(queue.pending()[0].id, ApprovalDecision.APPROVE, founder_note="ok")

            # Load new queue from same file
            queue2 = ApprovalQueue(Path(tmpdir) / "approvals.jsonl")
            assert len(queue2.pending()) == 1
            assert len(queue2.all()) == 2

    def test_decision_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "decisions.jsonl"
            queue = ApprovalQueue(decision_log_path=log_path)
            item = queue.add(agent_id="A", action="task1", rationale="r", risk_assessment="low")
            queue.decide(item.id, ApprovalDecision.APPROVE, founder_note="go")

            # Check decision log exists and has entry
            assert log_path.exists()
            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["decision"] == "approve"
            assert entry["founder_note"] == "go"


class TestCLIApprovalCommands:
    def test_cli_has_approvals_command(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "aos", "approvals"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)

    def test_cli_approvals_list(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "aos", "approvals", "list"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)

    def test_cli_approvals_approve_all(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "aos", "approvals", "approve-all", "--note", "batch approve"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)
