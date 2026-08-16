"""Tests for Valueflow Pipeline Alignment — Disposition, MAR gates, sprint review."""

from __future__ import annotations

import pytest

from aos.evaluator import (
    ClassifiedFinding,
    Disposition,
    classify_findings,
)

# ---------------------------------------------------------------------------
# Disposition enum tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDisposition:

    def test_values(self):
        assert Disposition.DISAGREE.value == "disagree"
        assert Disposition.AUTONOMOUS.value == "autonomous"
        assert Disposition.COLLABORATIVE.value == "collaborative"

    def test_all_members(self):
        assert len(Disposition) == 3

    def test_str_enum(self):
        assert isinstance(Disposition.DISAGREE, str)
        assert Disposition.DISAGREE == "disagree"


# ---------------------------------------------------------------------------
# ClassifiedFinding tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestClassifiedFinding:

    def test_frozen(self):
        f = ClassifiedFinding(
            finding="test", severity="high",
            disposition=Disposition.AUTONOMOUS, rationale="r",
        )
        with pytest.raises(AttributeError):
            f.finding = "changed"  # type: ignore[misc]

    def test_defaults(self):
        f = ClassifiedFinding(
            finding="test", severity="medium",
            disposition=Disposition.AUTONOMOUS,
        )
        assert f.rationale == ""


# ---------------------------------------------------------------------------
# classify_findings tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestClassifyFindings:

    def test_empty_input(self):
        result = classify_findings([])
        assert result == []

    def test_high_severity_autonomous(self):
        findings = [{"text": "Missing null check in parser", "severity": "high"}]
        result = classify_findings(findings)
        assert len(result) == 1
        assert result[0].disposition == Disposition.AUTONOMOUS
        assert result[0].severity == "high"

    def test_medium_severity_autonomous(self):
        findings = [{"text": "Consider using named tuple", "severity": "medium"}]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.AUTONOMOUS

    def test_low_severity_autonomous(self):
        findings = [{"text": "Minor whitespace issue", "severity": "low"}]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.AUTONOMOUS

    def test_critical_with_location_autonomous(self):
        findings = [{
            "text": "Buffer overflow in parser",
            "severity": "critical",
            "file": "src/parser.c",
            "line": 42,
        }]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.AUTONOMOUS

    def test_critical_without_location_collaborative(self):
        findings = [{"text": "Buffer overflow in parser", "severity": "critical"}]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.COLLABORATIVE

    def test_critical_architectural_decision_collaborative(self):
        findings = [{
            "text": "Architectural decision: switch database",
            "severity": "critical",
            "file": "config.py",
            "line": 1,
        }]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.COLLABORATIVE

    def test_critical_security_vulnerability_collaborative(self):
        findings = [{
            "text": "Security vulnerability in auth module",
            "severity": "critical",
            "file": "auth.py",
            "line": 10,
        }]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.COLLABORATIVE

    def test_critical_data_loss_collaborative(self):
        findings = [{
            "text": "Risk of data loss on cascade delete",
            "severity": "critical",
            "file": "models.py",
            "line": 55,
        }]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.COLLABORATIVE

    def test_disagree_pattern_false_positive(self):
        findings = [{"text": "False positive — not a real bug", "severity": "high"}]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.DISAGREE
        assert "reject pattern" in result[0].rationale

    def test_disagree_pattern_not_an_issue(self):
        findings = [{"text": "This is not a real issue", "severity": "medium"}]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.DISAGREE

    def test_disagree_pattern_stylistic_preference(self):
        findings = [{"text": "Stylistic preference: use tabs", "severity": "low"}]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.DISAGREE

    def test_disagree_pattern_contradicts_convention(self):
        findings = [{
            "text": "This contradicts project convention for naming",
            "severity": "medium",
        }]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.DISAGREE

    def test_mixed_findings(self):
        findings = [
            {"text": "Missing null check", "severity": "high"},
            {"text": "False positive", "severity": "medium"},
            {"text": "Buffer overflow", "severity": "critical"},
            {"text": "Minor style issue", "severity": "low"},
        ]
        result = classify_findings(findings)
        dispositions = [f.disposition for f in result]
        assert Disposition.AUTONOMOUS in dispositions
        assert Disposition.DISAGREE in dispositions
        assert Disposition.COLLABORATIVE in dispositions

    def test_finding_key_text_vs_finding(self):
        """Support both 'text' and 'finding' keys."""
        findings_text = [{"text": "Missing null check", "severity": "high"}]
        findings_finding = [{"finding": "Missing null check", "severity": "high"}]
        r1 = classify_findings(findings_text)
        r2 = classify_findings(findings_finding)
        assert r1[0].finding == r2[0].finding

    def test_severity_defaults_to_medium(self):
        findings = [{"text": "Some issue"}]
        result = classify_findings(findings)
        assert result[0].severity == "medium"

    def test_multiple_findings_count(self):
        findings = [
            {"text": f"Finding {i}", "severity": "high"}
            for i in range(5)
        ]
        result = classify_findings(findings)
        assert len(result) == 5
        assert all(f.disposition == Disposition.AUTONOMOUS for f in result)

    def test_disagree_before_collaborative_priority(self):
        """DISAGREE should be checked before COLLABORATIVE."""
        findings = [{
            "text": "False positive — not a real security vulnerability",
            "severity": "critical",
        }]
        result = classify_findings(findings)
        assert result[0].disposition == Disposition.DISAGREE


# ---------------------------------------------------------------------------
# Pipeline MAR gate tests (dry-run)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPipelineMAR:

    def test_mar_dry_run(self):
        """MAR gate in dry-run mode always passes."""
        from unittest.mock import MagicMock

        from aos.orchestrate.pipeline import (
            OrchestratePipeline,
            Phase,
            PipelineContext,
        )

        ctx = PipelineContext(dry_run=True, one_liner="test")
        gate_manager = MagicMock()
        pipeline = OrchestratePipeline(ctx, gate_manager)

        result = pipeline._run_mar(Phase.SPEC, Phase.AUTOPLAN)
        assert result is True

    def test_sprint_review_dry_run(self):
        """Sprint review in dry-run mode always passes."""
        from unittest.mock import MagicMock

        from aos.orchestrate.pipeline import (
            OrchestratePipeline,
            PipelineContext,
        )

        ctx = PipelineContext(dry_run=True, one_liner="test")
        gate_manager = MagicMock()
        pipeline = OrchestratePipeline(ctx, gate_manager)

        result = pipeline._run_sprint_review()
        assert result is True

    def test_mar_no_findings_passes(self):
        """MAR with no findings passes without classification."""
        from unittest.mock import MagicMock

        from aos.orchestrate.pipeline import (
            OrchestratePipeline,
            Phase,
            PhaseResult,
            PipelineContext,
            Status,
        )

        ctx = PipelineContext(one_liner="test")
        # Record an empty phase result
        ctx.record(PhaseResult(phase=Phase.SPEC, status=Status.PASSED))
        gate_manager = MagicMock()
        pipeline = OrchestratePipeline(ctx, gate_manager)

        result = pipeline._run_mar(Phase.SPEC, Phase.AUTOPLAN)
        assert result is True
