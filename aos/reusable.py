"""Declarative reusable-system assets built from existing AOS primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml


@dataclass(frozen=True)
class ReusableSystem:
    id: str
    name: str
    purpose: str
    trigger: str
    inputs: list[str]
    tools: list[str]
    steps: list[dict[str, Any]]
    quality_checks: list[str] = field(default_factory=list)
    approval_points: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    retry_policy: dict[str, Any] = field(default_factory=dict)
    escalation_policy: dict[str, Any] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("reusable system id and name are required")
        if not self.steps:
            raise ValueError("reusable system must define at least one step")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReusableSystem":
        return cls(**{k: data.get(k, v) for k, v in {
            "id": "", "name": "", "purpose": "", "trigger": "", "inputs": [],
            "tools": [], "steps": [], "quality_checks": [], "approval_points": [],
            "outputs": [], "retry_policy": {}, "escalation_policy": {}, "examples": [],
        }.items()})

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ReusableSystem":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(data.get("reusable_system", data))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReusableSystemRegistry:
    def __init__(self, systems: list[ReusableSystem] | None = None) -> None:
        self._systems = {s.id: s for s in systems or []}

    def register(self, system: ReusableSystem) -> None:
        if system.id in self._systems:
            raise ValueError(f"reusable system already registered: {system.id}")
        self._systems[system.id] = system

    def get(self, system_id: str) -> ReusableSystem:
        try:
            return self._systems[system_id]
        except KeyError as exc:
            raise KeyError(f"unknown reusable system: {system_id}") from exc

    def list(self) -> list[ReusableSystem]:
        return [self._systems[key] for key in sorted(self._systems)]

    @classmethod
    def load_dir(cls, directory: str | Path) -> "ReusableSystemRegistry":
        registry = cls()
        for path in sorted(Path(directory).glob("*.y*ml")):
            registry.register(ReusableSystem.from_yaml(path))
        return registry

    def invoke(self, system_id: str, runner: Callable[[dict[str, Any], dict[str, Any]], Any],
               inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        system = self.get(system_id)
        context: dict[str, Any] = {"system_id": system.id, "inputs": inputs or {}, "steps": []}
        for index, step in enumerate(system.steps, 1):
            result = runner(step, context)
            context["steps"].append({"number": index, "step": step, "result": result})
        return context
