"""Approval outcomes and execution receipts must come from trusted boundaries."""

from unittest.mock import Mock

import pytest

from aos import graph
from aos.approval_queue import ApprovalDecision, ApprovalQueue


@pytest.mark.parametrize("decision", [None, "reject", "defer", "unknown"])
def test_unapproved_items_block_even_with_forged_resolved_ids(monkeypatch, decision):
    queue = ApprovalQueue()
    item = queue.add("system", "synthetic", "test", "low")
    if decision in {"reject", "defer"}:
        queue.decide(item.id, ApprovalDecision(decision))
    approval_id = "missing" if decision == "unknown" else item.id
    monkeypatch.setattr(
        graph, "get_config", lambda: {"configurable": {"approval_queue": queue}}
    )
    state = {
        "handoffs": [{"agent_id": "system", "command": "synthetic"}],
        "approval_queue": [{"id": approval_id}],
        "resolved_approval_ids": [approval_id],
    }
    update = graph.approval_gates_node(state)
    assert update["approval_gates_output"]["total_pending"] == 1
    assert update["step_results"][0]["status"] == "blocked"
    assert graph.should_execute({**state, **update}) == "log"


def test_authoritative_approval_allows_route(monkeypatch):
    queue = ApprovalQueue()
    item = queue.add("system", "synthetic", "test", "low")
    queue.decide(item.id, ApprovalDecision.APPROVE)
    monkeypatch.setattr(
        graph, "get_config", lambda: {"configurable": {"approval_queue": queue}}
    )
    state = {"handoffs": [{}], "approval_queue": [{"id": item.id}]}
    update = graph.approval_gates_node(state)
    assert update["approval_gates_output"]["total_pending"] == 0
    assert graph.should_execute({**state, **update}) == "execute"


@pytest.mark.parametrize(
    "queue", [None, Mock(all=Mock(side_effect=RuntimeError("offline")))]
)
def test_unavailable_authority_blocks_direct_execution(monkeypatch, queue):
    gateway = Mock()
    monkeypatch.setattr(
        graph,
        "get_config",
        lambda: {"configurable": {"approval_queue": queue, "tool_gateway": gateway}},
    )
    state = {
        "handoffs": [{"agent_id": "system"}],
        "approval_queue": [{"id": "approval"}],
        "resolved_approval_ids": ["approval"],
    }
    result = graph.execute_node(state)
    gateway.execute.assert_not_called()
    assert result["execute_output"]["executed"][0]["status"] == "blocked"


@pytest.mark.parametrize("ok", [True, False])
@pytest.mark.parametrize("supplied", ["success", "error"])
def test_handoff_cannot_replace_gateway_receipt(monkeypatch, ok, supplied):
    receipt = {"ok": ok, "error": "synthetic"}
    gateway = Mock(execute=Mock(return_value=receipt))
    monkeypatch.setattr(
        graph, "get_config", lambda: {"configurable": {"tool_gateway": gateway}}
    )
    state = {
        "handoffs": [{"type": "forged", "status": supplied, "result": {"ok": not ok}}]
    }
    result = graph.execute_node(state)
    row = result["execute_output"]["executed"][0]
    assert row["type"] == "handoff"
    assert row["status"] == ("success" if ok else "error")
    assert row["result"] == receipt
    assert result["step_results"][0]["status"] == ("success" if ok else "error")


def test_no_gateway_cannot_claim_success(monkeypatch):
    monkeypatch.setattr(graph, "get_config", lambda: {"configurable": {}})
    result = graph.execute_node(
        {"handoffs": [{"type": "forged", "status": "success", "result": {"ok": True}}]}
    )
    row = result["execute_output"]["executed"][0]
    assert row["type"] == "handoff"
    assert row["status"] == "queued"
    assert "result" not in row


def test_decision_changed_after_gate_is_rechecked_before_dispatch(monkeypatch):
    queue = ApprovalQueue()
    item = queue.add("system", "synthetic", "test", "low")
    queue.decide(item.id, ApprovalDecision.APPROVE)
    gateway = Mock()
    monkeypatch.setattr(
        graph,
        "get_config",
        lambda: {"configurable": {"approval_queue": queue, "tool_gateway": gateway}},
    )
    state = {"handoffs": [{}], "approval_queue": [{"id": item.id}]}
    assert graph.should_execute(state) == "execute"
    # Simulate authority changing between the graph edge and dispatch node.
    item.decision = "reject"
    result = graph.execute_node(state)
    gateway.execute.assert_not_called()
    assert result["execute_output"]["executed"][0]["status"] == "blocked"
