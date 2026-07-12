"""Usage tracker — captures token usage per agent per cycle.

Every LLMResponse already carries usage dict. This module accumulates
them into a report for cost visibility and optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UsageReport:
    """Aggregated usage report for one cycle."""

    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    by_agent: dict[str, dict[str, int]] = field(default_factory=dict)
    by_model: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    def summary(self) -> str:
        lines = [
            f"{self.total_calls} calls, {self.total_tokens} tokens",
        ]
        for agent_id, data in self.by_agent.items():
            tokens = data["prompt_tokens"] + data["completion_tokens"]
            lines.append(f"  {agent_id}: {tokens} tokens")
        return "\n".join(lines)


class UsageTracker:
    """Accumulates LLM usage across a cycle."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(
        self,
        agent_id: str,
        model: str,
        usage: dict[str, Any],
    ) -> None:
        """Record one LLM call's usage."""
        prompt = usage.get("prompt_tokens", 0) or 0
        completion = usage.get("completion_tokens", 0) or 0
        self._records.append(
            {
                "agent_id": agent_id,
                "model": model,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
            }
        )

    def report(self) -> UsageReport:
        """Generate aggregated report."""
        report = UsageReport()

        for rec in self._records:
            report.total_calls += 1
            report.total_prompt_tokens += rec["prompt_tokens"]
            report.total_completion_tokens += rec["completion_tokens"]

            # By agent
            agent = rec["agent_id"]
            if agent not in report.by_agent:
                report.by_agent[agent] = {"prompt_tokens": 0, "completion_tokens": 0}
            report.by_agent[agent]["prompt_tokens"] += rec["prompt_tokens"]
            report.by_agent[agent]["completion_tokens"] += rec["completion_tokens"]

            # By model
            model = rec["model"]
            if model not in report.by_model:
                report.by_model[model] = {"prompt_tokens": 0, "completion_tokens": 0}
            report.by_model[model]["prompt_tokens"] += rec["prompt_tokens"]
            report.by_model[model]["completion_tokens"] += rec["completion_tokens"]

        return report
