"""Tests for AOS context builder — full prompt construction."""

from __future__ import annotations

import pytest

from aos.context import build_prompt
from aos.schemas.agent import (
    Agent,
    AgentCriticality,
    AgentStatus,
    AllowedMemory,
)


@pytest.fixture
def cfo_agent() -> Agent:
    return Agent(
        id="AGT-EXEC-CFO",
        name="CFO Agent",
        harness="HAR-EXEC-001",
        status=AgentStatus.PRODUCTION,
        criticality=AgentCriticality.HIGH,
        mission="Maintain Netso Energy's financial health.",
        capabilities=["cash_flow_monitoring", "financial_forecasting"],
        allowed_memory=AllowedMemory(
            read=["ground_truth_constants", "financial_models"],
            write=["investor_update_drafts"],
            cannot_read=["founder_personal_notes"],
        ),
        financial_rules={
            "canonical_source": "GROUND_TRUTH_CONSTANTS.md",
            "hard_fails": [
                {
                    "description": "blended_rate_used_for_savings",
                    "correct_value": "True Variable Rate BDT 12.98/kWh",
                },
                {
                    "description": "scenario_b_without_nbr",
                    "correct_value": "Scenario A (BDT 55,000/kW)",
                },
            ],
            "constants_to_enforce": {
                "true_variable_rate": 12.98,
                "blended_rate": 14.81,
                "ppa_rate": 10.00,
                "customer_savings_pct": 23.0,
            },
        },
        reasoning_structure=[
            "retrieve_ground_truth_values",
            "cross_check_constants",
            "calculate",
            "validate_output",
        ],
        self_check=["Does every number match ground truth?"],
        constraints=["Never use blended rate for savings"],
    )


@pytest.fixture
def minimal_agent() -> Agent:
    return Agent(
        id="AGT-EXEC-COO",
        name="COO Agent",
        harness="HAR-EXEC-001",
        status=AgentStatus.PRODUCTION,
        criticality=AgentCriticality.HIGH,
        mission="Keep projects on track.",
        allowed_memory=AllowedMemory(
            read=["dashboard", "blockers"],
            write=["dashboard"],
            cannot_read=["founder_personal_notes"],
        ),
    )


# ---------------------------------------------------------------------------
# Identity + Mission
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_includes_agent_name(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "COO Agent" in prompt

    def test_includes_agent_id(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "AGT-EXEC-COO" in prompt

    def test_includes_mission(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "Keep projects on track." in prompt


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_lists_capabilities(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "dashboard" in prompt.lower() or "blocker" in prompt.lower()

    def test_cfo_capabilities_present(self, cfo_agent: Agent) -> None:
        prompt = build_prompt(cfo_agent, netso_financial=None)
        assert "cash_flow_monitoring" in prompt
        assert "financial_forecasting" in prompt


# ---------------------------------------------------------------------------
# Reasoning, self-check, constraints
# ---------------------------------------------------------------------------


class TestAgentContract:
    def test_includes_reasoning_structure(self, cfo_agent: Agent) -> None:
        prompt = build_prompt(cfo_agent, netso_financial=None)
        assert "REASONING PROCESS" in prompt

    def test_includes_self_check(self, cfo_agent: Agent) -> None:
        prompt = build_prompt(cfo_agent, netso_financial=None)
        assert "ground truth" in prompt.lower()

    def test_includes_constraints(self, cfo_agent: Agent) -> None:
        prompt = build_prompt(cfo_agent, netso_financial=None)
        assert "Never use blended rate" in prompt


# ---------------------------------------------------------------------------
# Memory permissions
# ---------------------------------------------------------------------------


class TestMemoryPermissions:
    def test_includes_read_permissions(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "dashboard" in prompt
        assert "blockers" in prompt

    def test_includes_write_permissions(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "dashboard" in prompt

    def test_includes_cannot_read(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "founder_personal_notes" in prompt


# ---------------------------------------------------------------------------
# Financial rules (CFO-specific)
# ---------------------------------------------------------------------------


class TestFinancialRules:
    def test_cfo_gets_financial_constants(self, cfo_agent: Agent) -> None:
        from aos.constants import NETSO_FINANCIAL

        prompt = build_prompt(cfo_agent, netso_financial=NETSO_FINANCIAL)
        assert "12.98" in prompt  # true_variable_rate
        assert "14.81" in prompt  # blended_rate
        assert "ppa_rate" in prompt  # ppa_rate key present (value may render as 10.0)

    def test_cfo_gets_hard_fail_rules(self, cfo_agent: Agent) -> None:
        from aos.constants import NETSO_FINANCIAL

        prompt = build_prompt(cfo_agent, netso_financial=NETSO_FINANCIAL)
        assert "HARD FAIL" in prompt
        assert "blended" in prompt.lower()

    def test_coo_does_not_get_financial_constants(self, minimal_agent: Agent) -> None:
        from aos.constants import NETSO_FINANCIAL

        prompt = build_prompt(minimal_agent, netso_financial=NETSO_FINANCIAL)
        assert "HARD FAIL" not in prompt

    def test_cfo_gets_scenario_b_rules(self, cfo_agent: Agent) -> None:
        from aos.constants import NETSO_FINANCIAL

        prompt = build_prompt(cfo_agent, netso_financial=NETSO_FINANCIAL)
        assert "scenario" in prompt.lower() or "SCENARIO" in prompt


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    def test_includes_json_output_instructions(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "JSON" in prompt or "json" in prompt

    def test_dispatcher_gets_routing_table(self) -> None:
        from aos.schemas.agent import RoutingEntry, RoutingTable

        dispatcher = Agent(
            id="AGT-EXEC-DISPATCH",
            name="Dispatcher",
            harness="HAR-EXEC-001",
            status=AgentStatus.PRODUCTION,
            criticality=AgentCriticality.CRITICAL,
            mission="Route work.",
            allowed_memory=AllowedMemory(read=[], write=[], cannot_read=[]),
            routing_table=RoutingTable(
                executive_internal=[
                    RoutingEntry(
                        task="financial_modeling", route_to="AGT-EXEC-CFO", sla="4h"
                    ),
                ],
            ),
        )
        prompt = build_prompt(dispatcher, netso_financial=None)
        assert "financial_modeling" in prompt
        assert "AGT-EXEC-CFO" in prompt


# ---------------------------------------------------------------------------
# Memory context injection
# ---------------------------------------------------------------------------


class TestMemoryContext:
    def test_memory_context_injected(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(
            minimal_agent,
            netso_financial=None,
            memory_context="Dashboard shows 3 blockers, cash runway 11.3 months.",
        )
        assert "Dashboard shows 3 blockers" in prompt

    def test_no_memory_context_ok(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None, memory_context=None)
        assert len(prompt) > 200


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_prompt_is_string(self, minimal_agent: Agent) -> None:
        result = build_prompt(minimal_agent, netso_financial=None)
        assert isinstance(result, str)
        assert len(result) > 200

    def test_minimal_agent_no_crash(self) -> None:
        agent = Agent(
            id="AGT-EXEC-COO",
            name="COO",
            harness="HAR-EXEC-001",
            status=AgentStatus.PRODUCTION,
            criticality=AgentCriticality.HIGH,
            mission="Track.",
            allowed_memory=AllowedMemory(read=[], write=[], cannot_read=[]),
        )
        prompt = build_prompt(agent, netso_financial=None)
        assert isinstance(prompt, str)
        assert len(prompt) > 50
