"""Baseline evaluation harness for TAZ OS.

Measures:
  - financial_accuracy_rate: % of CFO/Rsk outputs pass validation
  - token_cost_per_cycle: total prompt+completion tokens per harness cycle
  - output_quality_score: pass/fail on required JSON structure

Usage:
  python -m aos.evaluator_harness --harness executive --samples 5
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from aos.evaluator import validate_output
from aos.llm import create_llm_client, resolve_model
from aos.registry import HarnessBundle, load_registry
from aos.memory import MemoryStore
from aos.usage import UsageTracker


@dataclass
class EvalResult:
    harness_id: str
    cycle_id: str
    status: str  # "pass" | "fail"
    financial_accuracy: bool | None = None
    financial_violations: list[str] = field(default_factory=list)
    tokens_prompt: int = 0
    tokens_completion: int = 0
    duration_ms: int = 0
    output_keys: list[str] = field(default_factory=list)


class BaselineEvaluator:
    """Runs a single agent through validation and usage tracking."""

    def __init__(self, llm, memory: MemoryStore | None = None) -> None:
        self.llm = llm
        self.memory = memory
        self.tracker = UsageTracker()

    def evaluate(self, agent_id: str, output: dict[str, Any], model: str = "sonnet", constants: dict | None = None) -> EvalResult:
        start = time.monotonic()
        validation = validate_output(output, agent_id, constants)
        usage = self.llm.usage() if hasattr(self.llm, "usage") else {}
        elapsed = int((time.monotonic() - start) * 1000)

        # When no constants, financial checks were skipped — mark as not applicable
        financial_acc = None if constants is None else validation.passed

        return EvalResult(
            harness_id="eval",
            cycle_id=f"eval-{agent_id}",
            status="error" if not validation.passed and validation.violations else "pass",
            financial_accuracy=financial_acc,
            financial_violations=validation.violations,
            tokens_prompt=usage.get("prompt_tokens", 0),
            tokens_completion=usage.get("completion_tokens", 0),
            duration_ms=elapsed,
            output_keys=list(output.keys()),
        )

    def report(self, results: list[EvalResult], has_financial_constants: bool = True) -> dict[str, Any]:
        total = len(results)
        acc = [r for r in results if r.financial_accuracy is not None]
        rate = sum(1 for r in acc if r.financial_accuracy) / max(len(acc), 1)
        total_tokens = sum(r.tokens_prompt + r.tokens_completion for r in results)
        by_status: Counter = Counter(r.status for r in results)
        report: dict[str, Any] = {
            "total_runs": total,
            "financial_accuracy_rate": round(rate, 4) if has_financial_constants else None,
            "total_tokens": total_tokens,
            "by_status": dict(by_status),
            "violations": [v for r in results for v in r.financial_violations],
        }
        if not has_financial_constants:
            report["financial_note"] = "Skipped: venture has no financial constants"
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="AOS baseline evaluation")
    parser.add_argument("--harness", required=True)
    parser.add_argument("--samples", type=int, default=1)
    args = parser.parse_args()

    llm = create_llm_client()
    ev = BaselineEvaluator(llm)

    cases = [
        # Positive cases (should pass)
        {"agent_id": "AGT-EXEC-CFO", "output": {"savings_pct": 23.0, "rate_used": 12.98, "ppa_rate": 10.0, "dscr": 2.25, "capex_per_kw": 55000}},
        # Negative cases (should fail)
        {"agent_id": "AGT-EXEC-CFO", "output": {"savings_pct": 14.0, "rate_used": 14.81}},
        {"agent_id": "AGT-EXEC-CFO", "output": {"savings_pct": 23.0, "dscr": 1.5}},
        {"agent_id": "AGT-EXEC-CFO", "output": {"ppa_rate": 12.0, "savings_pct": 23.0}},
    ]

    results = [ev.evaluate(**c) for c in cases[: args.samples]]
    report = ev.report(results)
    print(json.dumps(report, indent=2))
    return 0 if report["financial_accuracy_rate"] >= 0.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
