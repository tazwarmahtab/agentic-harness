"""Manifest registry — loads all manifests into typed objects and resolves cross-references."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from aos.schemas.harness import Harness, AgentTeam
from aos.schemas.agent import Agent
from aos.schemas.venture import Venture
from aos.schemas.memory import Memory
from aos.schemas.tool import ToolRegistry
from aos.schemas.evaluation import Evaluation
from aos.schemas.sop import SOP
from aos.schemas.policy_collection import PolicyCollection
from aos.loader import (
    load_harness,
    load_agent,
    load_venture,
    load_memory,
    load_tool_registry,
    load_evaluation,
    load_sop,
    load_policy_collection,
)

logger = logging.getLogger(__name__)


@dataclass
class HarnessBundle:
    """All manifests belonging to a single harness."""
    harness: Harness
    planner: Agent | None = None
    dispatcher: Agent | None = None
    specialists: dict[str, Agent] = field(default_factory=dict)
    teams: dict[str, AgentTeam] = field(default_factory=dict)
    memory: Memory | None = None
    tools: ToolRegistry | None = None
    approvals: PolicyCollection | None = None
    evaluation: Evaluation | None = None
    sops: dict[str, SOP] = field(default_factory=dict)


@dataclass
class Registry:
    """Complete registry of all loaded manifests."""
    venture: Venture | None = None
    harnesses: dict[str, HarnessBundle] = field(default_factory=dict)

    def get_harness(self, harness_id: str) -> HarnessBundle | None:
        return self.harnesses.get(harness_id)

    def get_agent(self, agent_id: str) -> Agent | None:
        for bundle in self.harnesses.values():
            if bundle.planner and bundle.planner.id == agent_id:
                return bundle.planner
            if bundle.dispatcher and bundle.dispatcher.id == agent_id:
                return bundle.dispatcher
            if agent_id in bundle.specialists:
                return bundle.specialists[agent_id]
        return None

    def resolve_agent(self, agent_id: str) -> tuple[Agent, HarnessBundle] | None:
        """Resolve an agent ID to its Agent object and the bundle it belongs to.

        Returns (agent, bundle) tuple for cross-harness dispatch, or None if not found.
        """
        for bundle in self.harnesses.values():
            if bundle.planner and bundle.planner.id == agent_id:
                return bundle.planner, bundle
            if bundle.dispatcher and bundle.dispatcher.id == agent_id:
                return bundle.dispatcher, bundle
            if agent_id in bundle.specialists:
                return bundle.specialists[agent_id], bundle
        return None

    def find_bundle_for_agent(self, agent_id: str) -> HarnessBundle | None:
        """Find which bundle contains a given agent."""
        result = self.resolve_agent(agent_id)
        return result[1] if result else None

    def all_agents(self) -> list[Agent]:
        agents = []
        for bundle in self.harnesses.values():
            if bundle.planner:
                agents.append(bundle.planner)
            if bundle.dispatcher:
                agents.append(bundle.dispatcher)
            agents.extend(bundle.specialists.values())
        return agents

    def summary(self) -> str:
        lines = ["Registry Summary:"]
        if self.venture:
            lines.append(f"  Venture: {self.venture.name} ({self.venture.id})")
        for hid, bundle in self.harnesses.items():
            specialist_count = len(bundle.specialists)
            sop_count = len(bundle.sops)
            lines.append(f"  Harness: {bundle.harness.name} ({hid})")
            lines.append(f"    Planner: {bundle.planner.name if bundle.planner else 'none'}")
            lines.append(f"    Dispatcher: {bundle.dispatcher.name if bundle.dispatcher else 'none'}")
            lines.append(f"    Specialists: {specialist_count}")
            lines.append(f"    Memory: {'yes' if bundle.memory else 'no'}")
            lines.append(f"    Tools: {'yes' if bundle.tools else 'no'}")
            lines.append(f"    Approvals: {'yes' if bundle.approvals else 'no'}")
            lines.append(f"    Evaluation: {'yes' if bundle.evaluation else 'no'}")
            lines.append(f"    SOPs: {sop_count}")
        lines.append(f"  Total agents: {len(self.all_agents())}")
        return "\n".join(lines)



    def live_status(self) -> dict[str, dict]:
        """Return live status of all loaded harnesses.

        Returns a dict keyed by harness_id with status, agent count,
        and component availability.
        """
        result: dict[str, dict] = {}
        for hid, bundle in self.harnesses.items():
            result[hid] = {
                "id": hid,
                "name": bundle.harness.name,
                "status": bundle.harness.status,
                "criticality": bundle.harness.criticality,
                "agents": len(bundle.specialists)
                    + (1 if bundle.planner else 0)
                    + (1 if bundle.dispatcher else 0),
                "has_memory": bundle.memory is not None,
                "has_tools": bundle.tools is not None,
                "has_approvals": bundle.approvals is not None,
                "has_evaluation": bundle.evaluation is not None,
                "sop_count": len(bundle.sops),
            }
        return result

def load_registry(
    harness_dir: Path,
    venture_path: Path | None = None,
) -> Registry:
    """Load all manifests from a harness directory into a typed registry."""
    # Reject traversal in user-supplied paths
    if ".." in harness_dir.parts:
        raise ValueError(f"Path traversal detected in harness directory: {harness_dir}")
    if venture_path is not None and ".." in venture_path.parts:
        raise ValueError(f"Path traversal detected in venture path: {venture_path}")

    registry = Registry()

    # Load venture
    if venture_path and venture_path.exists():
        registry.venture = load_venture(venture_path)

    # Load harness
    harness_yml = harness_dir / "harness.yml"
    if harness_yml.exists():
        harness = load_harness(harness_yml)
        bundle = HarnessBundle(harness=harness)

        # Load planner
        planner_yml = harness_dir / "planner.yml"
        if planner_yml.exists():
            bundle.planner = load_agent(planner_yml)

        # Load dispatcher
        dispatcher_yml = harness_dir / "dispatcher.yml"
        if dispatcher_yml.exists():
            bundle.dispatcher = load_agent(dispatcher_yml)

        # Load specialists
        specialists_dir = harness_dir / "specialists"
        if specialists_dir.exists():
            for yml in sorted(specialists_dir.glob("*.yml")):
                agent = load_agent(yml)
                bundle.specialists[agent.id] = agent

        # Load memory
        memory_yml = harness_dir / "memory.yml"
        if memory_yml.exists():
            bundle.memory = load_memory(memory_yml)

        # Load tools
        tools_yml = harness_dir / "tools.yml"
        if tools_yml.exists():
            bundle.tools = load_tool_registry(tools_yml)

        # Load approvals
        approvals_yml = harness_dir / "approvals.yml"
        if approvals_yml.exists():
            bundle.approvals = load_policy_collection(approvals_yml)

        # Load evaluation
        evaluation_yml = harness_dir / "evaluation.yml"
        if evaluation_yml.exists():
            bundle.evaluation = load_evaluation(evaluation_yml)

        # Load SOPs
        sops_dir = harness_dir / "sops"
        if sops_dir.exists():
            for yml in sorted(sops_dir.glob("*.yml")):
                sop = load_sop(yml)
                bundle.sops[sop.id] = sop

        # Load teams from harness manifest
        if harness.teams:
            for team in harness.teams:
                bundle.teams[team.id] = team

        registry.harnesses[harness.id] = bundle

    return registry
