"""Execution must require approval, not merely disappearance from pending."""
from unittest.mock import Mock

import pytest

from aos.approval_queue import ApprovalDecision, ApprovalQueue
from aos.graph import approval_gates_node, execute_node, should_execute


@pytest.mark.parametrize('decision', [ApprovalDecision.REJECT, ApprovalDecision.DEFER])
def test_nonapproval_cannot_release_handoffs(monkeypatch, decision):
    queue = ApprovalQueue()
    item = queue.add('agent', 'deploy', 'request', 'high')
    queue.decide(item.id, decision)
    cfg = {'configurable': {'approval_queue': queue}}
    monkeypatch.setattr('aos.graph.get_config', lambda: cfg)
    state = {'handoffs': [{'action': 'deploy'}], 'approval_queue': [{'id': item.id, 'action': 'deploy'}]}
    state.update(approval_gates_node(state))
    assert should_execute(state) == 'log'


def test_unknown_approval_cannot_release_handoffs(monkeypatch):
    monkeypatch.setattr('aos.graph.get_config', lambda: {'configurable': {'approval_queue': ApprovalQueue()}})
    state = {'handoffs': [{'action': 'deploy'}], 'approval_queue': [{'id': 'invented'}]}
    state.update(approval_gates_node(state))
    assert should_execute(state) == 'log'


def test_resolved_id_alone_is_not_authority():
    assert should_execute({'handoffs': [{}], 'approval_queue': [{'id': 'APR-1'}], 'resolved_approval_ids': ['APR-1']}) == 'log'


def test_execute_rechecks_queue_even_if_route_was_authorized(monkeypatch):
    gateway = Mock()
    monkeypatch.setattr('aos.graph.get_config', lambda: {'configurable': {'tool_gateway': gateway, 'approval_queue': ApprovalQueue()}})
    result = execute_node({'handoffs': [{'action': 'deploy'}], 'approval_queue': [{'id': 'invented'}], 'approval_gates_output': {'authorized': True}})
    gateway.execute.assert_not_called()
    assert result['execute_output']['executed'] == []


def test_explicit_approval_releases_matching_action(monkeypatch):
    queue = ApprovalQueue()
    item = queue.add('agent', 'deploy', 'request', 'high')
    queue.decide(item.id, ApprovalDecision.APPROVE)
    monkeypatch.setattr('aos.graph.get_config', lambda: {'configurable': {'approval_queue': queue}})
    state = {'handoffs': [{'action': 'deploy'}], 'approval_queue': [{'id': item.id, 'action': 'deploy'}]}
    state.update(approval_gates_node(state))
    assert should_execute(state) == 'execute'


def test_gate_reads_decision_from_another_queue_instance(tmp_path, monkeypatch):
    path = tmp_path / 'approvals.jsonl'
    queue = ApprovalQueue(persistence_path=path)
    item = queue.add('agent', 'deploy', 'request', 'high')
    other = ApprovalQueue(persistence_path=path)
    other.decide(item.id, ApprovalDecision.APPROVE)
    monkeypatch.setattr('aos.graph.get_config', lambda: {'configurable': {'approval_queue': queue}})
    state = {'handoffs': [{'action': 'deploy'}], 'approval_queue': [{'id': item.id, 'action': 'deploy'}]}
    state.update(approval_gates_node(state))
    assert should_execute(state) == 'execute'


def test_missing_persistence_cannot_reuse_old_approval(tmp_path, monkeypatch):
    path = tmp_path / 'approvals.jsonl'
    queue = ApprovalQueue(persistence_path=path)
    item = queue.add('agent', 'deploy', 'request', 'high')
    queue.decide(item.id, ApprovalDecision.APPROVE)
    path.unlink()
    monkeypatch.setattr('aos.graph.get_config', lambda: {'configurable': {'approval_queue': queue}})
    state = {'handoffs': [{}], 'approval_queue': [{'id': item.id}]}
    state.update(approval_gates_node(state))
    assert should_execute(state) == 'log'
