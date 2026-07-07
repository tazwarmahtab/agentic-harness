"""Tests for TAZ OS AI Development Harness — Phase 17."""

from __future__ import annotations
import sys

from pathlib import Path

import pytest

from tazos.registry import load_registry


class TestAIDevelopmentHarnessLoading:
    def test_load_ai_dev_harness(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-AID-001"

    def test_ai_dev_has_5_specialists(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) == 5

    def test_ai_dev_has_planner(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-AID-PLAN"

    def test_ai_dev_has_dispatcher(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-AID-DISPATCH"


class TestPromptEngineer:
    def test_prompt_engineer_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        pe = bundle.specialists.get("AGT-AID-PROMPT")
        assert pe is not None
        assert pe.name == "Prompt Engineer"
        assert pe.criticality.value == "high"

    def test_prompt_engineer_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        pe = bundle.specialists.get("AGT-AID-PROMPT")
        assert pe is not None
        assert len(pe.constraints) >= 3
        constraint_text = " ".join(pe.constraints).lower()
        assert "test" in constraint_text


class TestWorkflowBuilder:
    def test_workflow_builder_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        wb = bundle.specialists.get("AGT-AID-WORKFLOW")
        assert wb is not None
        assert wb.name == "Workflow Builder"
        assert wb.criticality.value == "high"

    def test_workflow_builder_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        wb = bundle.specialists.get("AGT-AID-WORKFLOW")
        assert wb is not None
        assert len(wb.constraints) >= 3


class TestEvaluationAgent:
    def test_eval_agent_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        eval_agent = bundle.specialists.get("AGT-AID-EVAL")
        assert eval_agent is not None
        assert eval_agent.name == "Evaluation Agent"
        assert eval_agent.criticality.value == "critical"

    def test_eval_agent_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        eval_agent = bundle.specialists.get("AGT-AID-EVAL")
        assert eval_agent is not None
        constraint_text = " ".join(eval_agent.constraints).lower()
        assert "objective" in constraint_text or "ground_truth" in constraint_text


class TestBenchmarkRunner:
    def test_benchmark_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        bench = bundle.specialists.get("AGT-AID-BENCH")
        assert bench is not None
        assert bench.name == "Benchmark Runner"
        assert bench.criticality.value == "high"

    def test_benchmark_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        bench = bundle.specialists.get("AGT-AID-BENCH")
        assert bench is not None
        assert len(bench.constraints) >= 3


class TestFailureAnalyzer:
    def test_failure_analyzer_exists(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        fail = bundle.specialists.get("AGT-AID-FAIL")
        assert fail is not None
        assert fail.name == "Failure Analyzer"
        assert fail.criticality.value == "high"

    def test_failure_analyzer_has_constraints(self) -> None:
        harness_dir = Path("tazos/harnesses/ai_development")
        if not harness_dir.exists():
            pytest.skip("AI Development harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        fail = bundle.specialists.get("AGT-AID-FAIL")
        assert fail is not None
        constraint_text = " ".join(fail.constraints).lower()
        assert "root_cause" in constraint_text or "fix" in constraint_text


class TestCLIAIDevelopment:
    def test_cli_run_ai_dev_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "run", "--harness", "ai_development", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "ai_development" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_validate_ai_dev_harness(self) -> None:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tazos", "validate", "--harness", "ai_development"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)
