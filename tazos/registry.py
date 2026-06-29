"""Manifest registry — loads all manifests into typed objects and resolves cross-references."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tazos.schemas.harness import Harness
from tazos.schemas.agent import Agent
from tazos.schemas.venture import Venture
from tazos.schemas.memory import Memory
from tazos.schemas.tool import ToolRegistry
from tazos.schemas.evaluation import Evaluation
from tazos.schemas.sop import SOP
from tazos.schemas.policy_collection import PolicyCollection
from tazos.loader import (
    load_harness,
    load_agent,
    load_venture,
    load_memory,
    load_tool_registry,
    load_evaluation,
    load_sop,
    load_policy_collection,
)


@dataclass
class HarnessBundle:
    """All manifests belonging to a single harness."""
    harness: Harness
    planner: Agent | None = None
    dispatcher: Agent | None = None
    specialists: dict[str, Agent] = field(default_factory=dict)
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


def load_registry(
    harness_dir: Path,
    venture_path: Path | None = None,
) -> Registry:
    """Load all manifests from a harness directory into a typed registry."""
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

        registry.harnesses[harness.id] = bundle

    return registry
