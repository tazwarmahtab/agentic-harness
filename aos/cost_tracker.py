"""Per-harness cost tracking (tokens -> dollar estimates)."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict

MODEL_COSTS: dict[str, dict[str, float]] = {
    "claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "free": {"input": 0.0, "output": 0.0},
    "_default": {"input": 3.0, "output": 15.0},
}

@dataclass(frozen=True)
class CostRecord:
    harness: str
    agent: str
    model: str
    input_tokens: int
    output_tokens: int

class CostTracker:
    def __init__(self) -> None:
        self._records: list[CostRecord] = []

    def record(self, rec: CostRecord) -> None:
        self._records.append(rec)

    def total_cost(self) -> float:
        return sum(self._cost(r) for r in self._records)

    def cost_by_harness(self) -> dict[str, float]:
        costs: dict[str, float] = defaultdict(float)
        for r in self._records:
            costs[r.harness] += self._cost(r)
        return dict(costs)

    def _cost(self, rec: CostRecord) -> float:
        prices = MODEL_COSTS.get(rec.model, MODEL_COSTS["_default"])
        return (rec.input_tokens / 1_000_000 * prices["input"] +
                rec.output_tokens / 1_000_000 * prices["output"])
