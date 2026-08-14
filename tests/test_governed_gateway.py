from __future__ import annotations

import pytest

from aos.integrations.governed_gateway import GovernedToolGateway
from aos.integrations.policy import create_founder_approval_token
from aos.tools import ToolDef


def _gateway() -> GovernedToolGateway:
    gateway = GovernedToolGateway()
    gateway.register_tool(
        ToolDef(
            id="TOOL-001",
            name="internal task",
            capability="internal_task",
            category="internal",
            status="active",
            execute_agents=["AGT-EXEC-CEO"],
        )
    )
    return gateway


def test_high_impact_call_is_denied_without_approval():
    gateway = _gateway()
    result = gateway.call(
        "internal_task",
        {"_action_class": "money_movement"},
        agent_id="AGT-EXEC-CEO",
    )
    assert result.status == "denied"
    assert result.approval_required is True
    assert "Verified founder approval required" in (result.error or "")


def test_untrusted_approval_flag_cannot_bypass_gate():
    gateway = _gateway()
    result = gateway.call(
        "internal_task",
        {
            "_action_class": "money_movement",
            "_approval_granted": True,
        },
        agent_id="AGT-EXEC-CEO",
    )
    assert result.status == "denied"


def test_reversible_call_reaches_normal_gateway():
    gateway = _gateway()
    result = gateway.call(
        "internal_task",
        {},
        agent_id="AGT-EXEC-CEO",
    )
    assert result.status == "error"
    assert "No provider" in (result.error or "")


def test_high_impact_concrete_action_is_denied_before_execution():
    gateway = _gateway()
    result = gateway.execute(
        {
            "action_type": "shell",
            "command": "echo should-not-run",
            "action_class": "contract_execution",
        }
    )
    assert result["ok"] is False
    assert result["status"] == "denied"
    assert result["required_level"] == 5


def test_tampered_or_missing_token_is_denied(monkeypatch):
    gateway = _gateway()
    monkeypatch.setenv("AOS_APPROVAL_SIGNING_SECRET", "test-secret")
    token = create_founder_approval_token(
        approval_id="APR-001",
        action_class="regulatory_submission",
    )
    gateway.register_approval_token(approval_id="APR-001", token=token + "tampered")
    result = gateway.execute(
        {
            "action_type": "shell",
            "command": "echo should-not-run",
            "action_class": "regulatory_submission",
            "approval_id": "APR-001",
        }
    )
    assert result["ok"] is False
    assert result["status"] == "denied"


def test_signed_founder_approval_can_reach_executor(monkeypatch):
    gateway = _gateway()
    monkeypatch.setenv("AOS_APPROVAL_SIGNING_SECRET", "test-secret")
    token = create_founder_approval_token(
        approval_id="APR-001",
        action_class="regulatory_submission",
    )
    gateway.register_approval_token(approval_id="APR-001", token=token)
    result = gateway.execute(
        {
            "action_type": "shell",
            "command": "printf 'approved'",
            "action_class": "regulatory_submission",
            "approval_id": "APR-001",
        }
    )
    assert result["ok"] is True
    assert result["stdout"] == "approved"


def test_token_is_bound_to_action_class(monkeypatch):
    gateway = _gateway()
    monkeypatch.setenv("AOS_APPROVAL_SIGNING_SECRET", "test-secret")
    token = create_founder_approval_token(
        approval_id="APR-001",
        action_class="regulatory_submission",
    )
    gateway.register_approval_token(approval_id="APR-001", token=token)
    result = gateway.execute(
        {
            "action_type": "shell",
            "command": "echo should-not-run",
            "action_class": "money_movement",
            "approval_id": "APR-001",
        }
    )
    assert result["ok"] is False
    assert result["status"] == "denied"
