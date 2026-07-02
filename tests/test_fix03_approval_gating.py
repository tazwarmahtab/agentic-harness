"""Tests for FIX-03: approval_queue → should_execute gating.

The core bug: approval_queue accumulates via operator.add but was never
pruned. should_execute() saw ALL historical items and blocked execution
permanently.

The fix: resolved_approval_ids tracks which items were approved/rejected.
should_execute() only blocks on genuinely pending items.
"""
from __future__ import annotations

import pytest
from tazos.graph import should_execute, approval_gates_node
from tazos.approval_queue import ApprovalQueue, ApprovalDecision


# ---------------------------------------------------------------------------
# should_execute — the conditional edge
# ---------------------------------------------------------------------------

class TestShouldExecute:
    """Tests for the should_execute conditional routing function."""

    def test_no_handoffs_returns_log(self) -> None:
        state = {"handoffs": []}
        assert should_execute(state) == "log"

    def test_no_handoffs_no_approvals_returns_log(self) -> None:
        state = {"handoffs": [], "approval_queue": [], "resolved_approval_ids": []}
        assert should_execute(state) == "log"

    def test_handoffs_no_approvals_returns_execute(self) -> None:
        state = {
            "handoffs": [{"type": "task", "agent_id": "A"}],
            "approval_queue": [],
            "resolved_approval_ids": [],
        }
        assert should_execute(state) == "execute"

    def test_handoffs_with_pending_approvals_returns_log(self) -> None:
        state = {
            "handoffs": [{"type": "task", "agent_id": "A"}],
            "approval_queue": [
                {"id": "APR-0001", "action": "deploy to prod", "status": "pending"},
            ],
            "resolved_approval_ids": [],
        }
        assert should_execute(state) == "log"

    def test_handoffs_with_resolved_approvals_returns_execute(self) -> None:
        """FIX-03: resolved approvals should NOT block execution."""
        state = {
            "handoffs": [{"type": "task", "agent_id": "A"}],
            "approval_queue": [
                {"id": "APR-0001", "action": "deploy to prod", "status": "pending"},
            ],
            "resolved_approval_ids": ["APR-0001"],
        }
        assert should_execute(state) == "execute"

    def test_mixed_pending_and_resolved_returns_log(self) -> None:
        """Only genuinely pending items block execution."""
        state = {
            "handoffs": [{"type": "task", "agent_id": "A"}],
            "approval_queue": [
                {"id": "APR-0001", "action": "task 1", "status": "pending"},
                {"id": "APR-0002", "action": "task 2", "status": "pending"},
            ],
            "resolved_approval_ids": ["APR-0001"],
        }
        assert should_execute(state) == "log"

    def test_all_resolved_returns_execute(self) -> None:
        state = {
            "handoffs": [{"type": "task", "agent_id": "A"}],
            "approval_queue": [
                {"id": "APR-0001", "action": "task 1", "status": "pending"},
                {"id": "APR-0002", "action": "task 2", "status": "pending"},
            ],
            "resolved_approval_ids": ["APR-0001", "APR-0002"],
        }
        assert should_execute(state) == "execute"

    def test_empty_handoffs_with_resolved_approvals_returns_log(self) -> None:
        """No handoffs = skip to log regardless of approval status."""
        state = {
            "handoffs": [],
            "approval_queue": [
                {"id": "APR-0001", "action": "task 1", "status": "pending"},
            ],
            "resolved_approval_ids": ["APR-0001"],
        }
        assert should_execute(state) == "log"

    def test_missing_resolved_ids_defaults_to_blocking(self) -> None:
        """If resolved_approval_ids is absent, treat all as pending."""
        state = {
            "handoffs": [{"type": "task", "agent_id": "A"}],
            "approval_queue": [
                {"id": "APR-0001", "action": "task 1", "status": "pending"},
            ],
        }
        assert should_execute(state) == "log"

    def test_item_without_id_is_not_resolved(self) -> None:
        """Items without an 'id' field cannot be resolved and block."""
        state = {
            "handoffs": [{"type": "task", "agent_id": "A"}],
            "approval_queue": [
                {"action": "task 1", "status": "pending"},  # no id
            ],
            "resolved_approval_ids": [],
        }
        assert should_execute(state) == "log"


# ---------------------------------------------------------------------------
# approval_gates_node — cross-references against ApprovalQueue
# ---------------------------------------------------------------------------

class TestApprovalGatesNode:
    """Tests for approval_gates_node resolving items against ApprovalQueue.

    approval_gates_node calls get_config() which requires a LangGraph
    runtime context. We mock it with a minimal config dict.
    """

    def _make_config(self, approval_queue: ApprovalQueue | None = None) -> dict:
        """Build a fake LangGraph config with a mock bundle and optional queue."""
        class _FakeBundle:
            specialists = {}
        cfg = {"configurable": {"bundle": _FakeBundle()}}
        if approval_queue:
            cfg["configurable"]["approval_queue"] = approval_queue
        return cfg

    def _make_state(
        self,
        approval_queue: list[dict] | None = None,
        resolved_approval_ids: list[str] | None = None,
    ) -> dict:
        return {
            "approval_queue": approval_queue or [],
            "resolved_approval_ids": resolved_approval_ids or [],
            "step_results": [],
            "approval_gates_output": {},
        }

    def test_empty_queue_returns_no_pending(self) -> None:
        state = self._make_state()
        cfg = self._make_config()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("tazos.graph.get_config", lambda: cfg)
            result = approval_gates_node(state)
        assert result["approval_gates_output"]["total_pending"] == 0

    def test_items_not_in_queue_are_filtered(self) -> None:
        """Items whose IDs are in resolved_approval_ids should be filtered."""
        state = self._make_state(
            approval_queue=[
                {"id": "APR-0001", "action": "task 1"},
                {"id": "APR-0002", "action": "task 2"},
            ],
            resolved_approval_ids=["APR-0001"],
        )
        cfg = self._make_config()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("tazos.graph.get_config", lambda: cfg)
            result = approval_gates_node(state)
        output = result["approval_gates_output"]
        assert output["total_pending"] == 1
        assert output["items"][0]["id"] == "APR-0002"

    def test_all_resolved_returns_zero_pending(self) -> None:
        state = self._make_state(
            approval_queue=[
                {"id": "APR-0001", "action": "task 1"},
                {"id": "APR-0002", "action": "task 2"},
            ],
            resolved_approval_ids=["APR-0001", "APR-0002"],
        )
        cfg = self._make_config()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("tazos.graph.get_config", lambda: cfg)
            result = approval_gates_node(state)
        assert result["approval_gates_output"]["total_pending"] == 0

    def test_emits_newly_resolved_ids(self) -> None:
        """Items in queue but not in pending list → emitted as newly_resolved."""
        queue = ApprovalQueue()
        item = queue.add(
            agent_id="AGT-EXEC-CFO",
            action="[spec gate] deploy",
            rationale="test",
            risk_assessment="low",
        )
        queue.decide(item.id, ApprovalDecision.APPROVE)

        state = self._make_state(
            approval_queue=[{"id": item.id, "action": "[spec gate] deploy"}],
        )
        cfg = self._make_config(approval_queue=queue)
        with pytest.MonkeyPatch.context() as m:
            m.setattr("tazos.graph.get_config", lambda: cfg)
            result = approval_gates_node(state)
        # Should emit the resolved ID
        assert item.id in result.get("resolved_approval_ids", [])

    def test_no_queue_configured_falls_back_to_resolved_ids(self) -> None:
        """When no ApprovalQueue is in config, only resolved_approval_ids is used."""
        state = self._make_state(
            approval_queue=[
                {"id": "APR-0001", "action": "task 1"},
                {"id": "APR-0002", "action": "task 2"},
            ],
            resolved_approval_ids=["APR-0001"],
        )
        cfg = self._make_config()  # no approval_queue in config
        with pytest.MonkeyPatch.context() as m:
            m.setattr("tazos.graph.get_config", lambda: cfg)
            result = approval_gates_node(state)
        output = result["approval_gates_output"]
        assert output["total_pending"] == 1
        assert output["items"][0]["id"] == "APR-0002"
