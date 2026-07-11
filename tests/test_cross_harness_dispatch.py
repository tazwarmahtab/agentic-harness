"""Tests for H4: Cross-harness dispatch — runtime agent resolution across bundles."""

from __future__ import annotations
import sys

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aos.registry import Registry, HarnessBundle, load_registry


def _build_multi_bundle_registry() -> Registry:
    """Load executive + finance + sales + operations into one registry."""
    root = Path("tazos/harnesses")
    registry = Registry()
    for name in ("executive", "finance", "sales", "operations"):
        harness_dir = root / name
        if harness_dir.exists() and (harness_dir / "harness.yml").exists():
            r = load_registry(harness_dir)
            for hid, bundle in r.harnesses.items():
                registry.harnesses[hid] = bundle
    return registry


class TestRegistryResolveAgent:
    """Registry.resolve_agent() returns (agent, bundle) or None."""

    def test_resolve_local_agent(self):
        registry = _build_multi_bundle_registry()
        result = registry.resolve_agent("AGT-EXEC-COO")
        assert result is not None
        agent, bundle = result
        assert agent.id == "AGT-EXEC-COO"
        assert bundle.harness.id == "HAR-EXEC-001"

    def test_resolve_cross_harness_finance(self):
        registry = _build_multi_bundle_registry()
        result = registry.resolve_agent("AGT-FIN-UNIT")
        assert result is not None
        agent, bundle = result
        assert agent.id == "AGT-FIN-UNIT"
        assert bundle.harness.id == "HAR-FIN-001"

    def test_resolve_cross_harness_sales(self):
        registry = _build_multi_bundle_registry()
        result = registry.resolve_agent("AGT-SAL-PROP")
        assert result is not None
        agent, bundle = result
        assert agent.id == "AGT-SAL-PROP"
        assert bundle.harness.id == "HAR-SAL-001"

    def test_resolve_cross_harness_operations(self):
        registry = _build_multi_bundle_registry()
        result = registry.resolve_agent("AGT-OPS-PROC")
        assert result is not None
        agent, bundle = result
        assert agent.id == "AGT-OPS-PROC"
        assert bundle.harness.id == "HAR-OPS-001"

    def test_resolve_nonexistent_returns_none(self):
        registry = _build_multi_bundle_registry()
        assert registry.resolve_agent("AGT-NONEXISTENT") is None

    def test_resolve_empty_registry_returns_none(self):
        registry = Registry()
        assert registry.resolve_agent("AGT-EXEC-COO") is None


class TestFindBundleForAgent:
    """Registry.find_bundle_for_agent() returns the bundle containing the agent."""

    def test_find_bundle_local(self):
        registry = _build_multi_bundle_registry()
        bundle = registry.find_bundle_for_agent("AGT-EXEC-COO")
        assert bundle is not None
        assert bundle.harness.id == "HAR-EXEC-001"

    def test_find_bundle_cross_harness(self):
        registry = _build_multi_bundle_registry()
        bundle = registry.find_bundle_for_agent("AGT-FIN-UNIT")
        assert bundle is not None
        assert bundle.harness.id == "HAR-FIN-001"

    def test_find_bundle_nonexistent_returns_none(self):
        registry = _build_multi_bundle_registry()
        assert registry.find_bundle_for_agent("AGT-GHOST") is None


class TestAllAgentsCrossHarness:
    """Registry.all_agents() returns agents from all loaded bundles."""

    def test_all_agents_includes_all_harnesses(self):
        registry = _build_multi_bundle_registry()
        all_ids = [a.id for a in registry.all_agents()]
        # Should have agents from at least 3 harnesses
        assert any(aid.startswith("AGT-EXEC-") for aid in all_ids)
        assert any(aid.startswith("AGT-FIN-") for aid in all_ids)
        assert any(aid.startswith("AGT-SAL-") for aid in all_ids)

    def test_all_agents_deduplicates(self):
        registry = _build_multi_bundle_registry()
        all_ids = [a.id for a in registry.all_agents()]
        assert len(all_ids) == len(set(all_ids))


class TestGraphConfigRegistry:
    """GraphConfig accepts and exposes the registry field."""

    def test_graph_config_with_registry(self):
        from aos.graph import GraphConfig
        from aos.llm import LLMClient
        from aos.registry import Registry

        bundle = MagicMock(spec=HarnessBundle)
        llm = MagicMock(spec=LLMClient)
        registry = Registry()

        config = GraphConfig(bundle=bundle, llm=llm, registry=registry)
        assert config.registry is registry

    def test_graph_config_without_registry_defaults_none(self):
        from aos.graph import GraphConfig
        from aos.llm import LLMClient

        bundle = MagicMock(spec=HarnessBundle)
        llm = MagicMock(spec=LLMClient)

        config = GraphConfig(bundle=bundle, llm=llm)
        assert config.registry is None


class TestFallbackRoutingCrossHarness:
    """_fallback_routing matches cross-harness agent IDs."""

    def test_matches_finance_agent(self):
        from aos.graph import _fallback_routing

        text = "Route to AGT-FIN-UNIT for unit economics analysis"
        result = _fallback_routing(text, None, ["AGT-FIN-UNIT"])
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["agent_id"] == "AGT-FIN-UNIT"

    def test_matches_sales_agent(self):
        from aos.graph import _fallback_routing

        text = "Assign AGT-SAL-PROP to write the proposal"
        result = _fallback_routing(text, None, ["AGT-SAL-PROP"])
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["agent_id"] == "AGT-SAL-PROP"

    def test_skips_unknown_agents(self):
        from aos.graph import _fallback_routing

        text = "Route to AGT-UNKNOWN-XYZ for something"
        result = _fallback_routing(text, None, ["AGT-FIN-UNIT"])
        assert len(result["assignments"]) == 0

    def test_matches_multiple_cross_harness_agents(self):
        from aos.graph import _fallback_routing

        text = "AGT-FIN-UNIT handles finance, AGT-SAL-PROP handles sales"
        available = ["AGT-FIN-UNIT", "AGT-SAL-PROP"]
        result = _fallback_routing(text, None, available)
        assert len(result["assignments"]) == 2
        agent_ids = {a["agent_id"] for a in result["assignments"]}
        assert agent_ids == {"AGT-FIN-UNIT", "AGT-SAL-PROP"}


class TestCLIMultiHarnessLoading:
    """CLI loads sibling harnesses for cross-harness dispatch."""

    def test_dry_run_loads_multiple_harnesses(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "run", "--venture", "netso", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "HAR-EXEC-001" in result.stdout or "executive" in result.stdout.lower()

    def test_dry_run_cross_harness_harness_loaded(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "run", "--venture", "netso", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        # Multi-harness loading should not break the cycle
        assert result.returncode == 0
        assert "0 errors" in result.stdout.lower() or "Errors: 0" in result.stdout
