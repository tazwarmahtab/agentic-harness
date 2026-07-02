"""Tests for baseline evaluation harness."""
from __future__ import annotations

import pytest
from tazos.evaluator import validate_output
from tazos.harnesses.evaluator.evaluator_harness import BaselineEvaluator, EvalResult


class StubLLM:
    def __init__(self) -> None:
        self._usage: dict[str, int] = {"prompt_tokens": 120, "completion_tokens": 40}

    def usage(self) -> dict[str, int]:
        return self._usage


class TestBaselineEvaluator:
    def setup_method(self) -> None:
        self.ev = BaselineEvaluator(StubLLM())

    def test_correct_output_passes(self) -> None:
        out = {"savings_pct": 23.0, "rate_used": 12.98, "ppa_rate": 10.0, "dscr": 2.25}
        r = self.ev.evaluate("AGT-EXEC-CFO", out)
        assert r.status == "pass"
        assert r.financial_accuracy is True
        assert r.financial_violations == []

    def test_blended_rate_blocks(self) -> None:
        out = {"savings_pct": 14.0, "rate_used": 14.81}
        r = self.ev.evaluate("AGT-EXEC-CFO", out)
        assert r.status == "error"
        assert r.financial_accuracy is False
        assert len(r.financial_violations) >= 1

    def test_report_aggregates(self) -> None:
        cases = [
            {"agent_id": "AGT-EXEC-CFO", "output": {"savings_pct": 23.0, "rate_used": 12.98}},
            {"agent_id": "AGT-EXEC-CFO", "output": {"savings_pct": 14.0, "rate_used": 14.81}},
        ]
        results = [self.ev.evaluate(**c) for c in cases]
        report = self.ev.report(results)
        assert report["total_runs"] == 2
        assert abs(report["financial_accuracy_rate"] - 0.5) < 1e-6
        assert report["total_tokens"] > 0
        assert len(report["violations"]) >= 1
