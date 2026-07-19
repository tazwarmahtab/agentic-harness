"""Tests for graph.py H4 cross-harness fallback paths.

Verifies that:
  - review_node, summarize_node, approval_gates_node fall back to registry
    when the target specialist is missing from the local bundle
  - specialists_node warns when an agent can't be resolved
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


from aos.registry import Registry, HarnessBundle, load_registry


def _build_registry() -> Registry:
    """Load executive + finance bundles into a registry."""
    root = Path("aos/harnesses")
    registry = Registry()
    for name in ("executive", "finance"):
        harness_dir = root / name
        if harness_dir.exists() and (harness_dir / "harness.yml").exists():
            r = load_registry(harness_dir)
            for hid, bundle in r.harnesses.items():
                registry.harnesses[hid] = bundle
    return registry


def _make_bundle_without_coo() -> HarnessBundle:
    """Executive bundle with COO removed to force registry fallback."""
    registry = _build_registry()
    exec_bundle = registry.harnesses.get("HAR-EXEC-001")
    assert exec_bundle is not None
    # Remove COO from local specialists
    filtered = {k: v for k, v in exec_bundle.specialists.items() if k != "AGT-EXEC-COO"}
    return HarnessBundle(
        harness=exec_bundle.harness,
        specialists=filtered,
        teams=exec_bundle.teams,
        dispatcher=exec_bundle.dispatcher,
    )


def _make_bundle_without_chief() -> HarnessBundle:
    """Executive bundle with Chief of Staff removed to force registry fallback."""
    registry = _build_registry()
    exec_bundle = registry.harnesses.get("HAR-EXEC-001")
    assert exec_bundle is not None
    filtered = {
        k: v for k, v in exec_bundle.specialists.items() if k != "AGT-EXEC-CHIEFOFSTAFF"
    }
    return HarnessBundle(
        harness=exec_bundle.harness,
        specialists=filtered,
        teams=exec_bundle.teams,
        dispatcher=exec_bundle.dispatcher,
    )


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Build a minimal CycleState-compatible dict."""
    state = {
        "cycle_id": "test-cycle-001",
        "venture_id": "netso",
        "iteration_count": 0,
        "step_results": [],
        "errors": [],
        "handoffs": [],
        "approval_queue": [],
        "resolved_approval_ids": [],
        "review_output": {},
        "specialists_output": {},
        "approval_output": {},
    }
    state.update(overrides)
    return state


class TestReviewNodeRegistryFallback:
    """review_node falls back to registry when COO not in bundle."""

    def test_falls_back_to_registry_for_coo(self):
        from aos.graph import review_node

        bundle = _make_bundle_without_coo()
        registry = _build_registry()
        llm = MagicMock()
        llm.chat.return_value = {"content": "Review complete"}

        config = {
            "configurable": {
                "bundle": bundle,
                "llm": llm,
                "registry": registry,
                "memory_store": None,
                "usage_tracker": None,
                "venture_constants": None,
            }
        }

        state = _make_state(
            artifacts={"review_input": "test data"},
        )

        with patch("aos.graph.get_config", return_value=config):
            result = review_node(state)

        # Should NOT have error about COO not found
        errors = result.get("errors", [])
        coo_missing = [e for e in errors if "COO specialist not found" in e]
        assert len(coo_missing) == 0, f"Expected no COO-missing error, got: {errors}"

    def test_errors_when_no_registry_and_no_bundle_coo(self):
        from aos.graph import review_node

        bundle = _make_bundle_without_coo()

        config = {
            "configurable": {
                "bundle": bundle,
                "llm": MagicMock(),
                "registry": None,
                "memory_store": None,
                "usage_tracker": None,
                "venture_constants": None,
            }
        }

        state = _make_state(artifacts={"review_input": "test"})

        with patch("aos.graph.get_config", return_value=config):
            result = review_node(state)

        errors = result.get("errors", [])
        assert any("COO specialist not found" in e for e in errors)


class TestSpecialistsNodeTeamShadowing:
    """P0-2: specialists_node must NOT discard team results when solo specialists also run.

    Regression test for the variable shadowing bug where lines 1331-1334
    re-declared specialist_results, new_errors, new_approvals, new_handoffs,
    discarding team results accumulated at lines 1224-1227.
    """

    def test_team_results_preserved_with_solo(self):
        """Team results must appear in specialist_results alongside solo results."""
        from aos.graph import specialists_node

        bundle = _build_registry().harnesses.get("HAR-EXEC-001")
        assert bundle is not None

        # Create a team with 2 members
        team_member_ids = list(bundle.teams.values())[0].members[:2]
        team_agent_ids = [m.agent_id for m in team_member_ids]

        # Assignments: 2 agents in a team + 1 solo agent
        solo_agent_id = [
            k for k in bundle.specialists.keys() if k not in team_agent_ids
        ][0]

        assignments = [
            {"agent_id": team_agent_ids[0], "task": "team task 1"},
            {"agent_id": team_agent_ids[1], "task": "team task 2"},
            {"agent_id": solo_agent_id, "task": "solo task"},
        ]

        # Mock team execution to return results
        team_result = {
            "status": "success",
            "results": [
                {"output": {"status": "done", "summary": "team member 1 done"}},
                {"output": {"status": "done", "summary": "team member 2 done"}},
            ],
            "errors": [],
        }

        # Mock solo execution
        solo_result = {
            "step": "run_specialists",
            "status": "success",
            "output": {"status": "done", "summary": "solo done"},
        }

        state = _make_state(
            delegate_output={"assignments": assignments},
        )

        config = {
            "configurable": {
                "bundle": bundle,
                "llm": MagicMock(),
                "registry": None,
                "memory_store": None,
                "usage_tracker": None,
                "venture_constants": None,
            }
        }

        with (
            patch("aos.graph.get_config", return_value=config),
            patch("aos.graph._run_team", return_value=team_result),
            patch("aos.graph._run_parallel", return_value=[(solo_agent_id, solo_result)]),
            patch("aos.graph._run_agent_node", return_value=solo_result),
        ):
            result = specialists_node(state)

        specialist_results = result.get("specialists_output", {}).get("specialist_results", [])

        # CRITICAL: team results MUST be present (was the bug — they were discarded)
        team_results = [r for r in specialist_results if r.get("agent_id", "").startswith("TEAM:")]
        solo_results = [r for r in specialist_results if not r.get("agent_id", "").startswith("TEAM:")]

        assert len(team_results) >= 1, (
            f"Team results were discarded! Got {len(specialist_results)} total results "
            f"but 0 TEAM: prefixed. specialist_results={specialist_results}"
        )
        assert len(solo_results) >= 1, (
            f"Solo results missing! Got {len(specialist_results)} total results "
            f"but 0 non-TEAM results."
        )


class TestSummarizeNodeRegistryFallback:
    """summarize_node falls back to registry when Chief of Staff not in bundle."""

    def test_falls_back_to_registry_for_chief(self):
        from aos.graph import summarize_node

        bundle = _make_bundle_without_chief()
        registry = _build_registry()
        llm = MagicMock()
        llm.chat.return_value = {"content": "Summary complete"}

        config = {
            "configurable": {
                "bundle": bundle,
                "llm": llm,
                "registry": registry,
                "memory_store": None,
                "usage_tracker": None,
                "venture_constants": None,
            }
        }

        state = _make_state(
            step_results=[{"step": "review", "status": "success"}],
        )

        with patch("aos.graph.get_config", return_value=config):
            result = summarize_node(state)

        errors = result.get("errors", [])
        chief_missing = [e for e in errors if "Chief of Staff not found" in e]
        assert len(chief_missing) == 0, (
            f"Expected no chief-missing error, got: {errors}"
        )


class TestApprovalGatesNodeRegistryFallback:
    """approval_gates_node falls back to registry when Chief of Staff not in bundle."""

    def test_falls_back_to_registry_for_chief(self):
        from aos.graph import approval_gates_node

        bundle = _make_bundle_without_chief()
        registry = _build_registry()
        llm = MagicMock()
        llm.chat.return_value = {"content": "Approved"}

        config = {
            "configurable": {
                "bundle": bundle,
                "llm": llm,
                "registry": registry,
                "memory_store": None,
                "usage_tracker": None,
                "venture_constants": None,
            }
        }

        state = _make_state(
            approval_queue=[
                {"id": "ap-1", "description": "Test approval", "status": "pending"}
            ],
        )

        with patch("aos.graph.get_config", return_value=config):
            result = approval_gates_node(state)

        # Should not error out — chief resolved via registry
        assert "approval_gates_output" in result


class TestSpecialistsNodeAgentDropWarning:
    """specialists_node warns when agent can't be resolved."""

    def test_warns_on_unresolvable_agent(self, caplog):
        from aos.graph import specialists_node

        bundle = _make_bundle_without_coo()
        registry = _build_registry()
        llm = MagicMock()

        config = {
            "configurable": {
                "bundle": bundle,
                "llm": llm,
                "registry": registry,
                "memory_store": None,
                "usage_tracker": None,
                "venture_constants": None,
            }
        }

        # Assign a non-existent agent via delegate_output (how the graph actually works)
        state = _make_state(
            delegate_output={
                "assignments": [
                    {"agent_id": "AGT-FAKE-NONEXISTENT", "task": "do something"}
                ]
            },
        )

        with patch("aos.graph.get_config", return_value=config):
            with caplog.at_level("WARNING", logger="aos.graph"):
                specialists_node(state)

        assert any("AGT-FAKE-NONEXISTENT" in r.message for r in caplog.records)
