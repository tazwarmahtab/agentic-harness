"""Tests for regression detection module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aos.regression import (
    BaselineSnapshot,
    Regression,
    RegressionDetector,
    Severity,
    _parse_pytest_output,
    collect_baseline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    test_count: int = 100,
    tests_passed: int = 98,
    tests_failed: int = 2,
    financial_accuracy_rate: float = 0.95,
    total_tokens: int = 5000,
    composite_score: float = 98.0,
    git_commit: str | None = "abc1234",
) -> BaselineSnapshot:
    return BaselineSnapshot(
        timestamp="2026-07-03T00:00:00+00:00",
        test_count=test_count,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        financial_accuracy_rate=financial_accuracy_rate,
        total_tokens=total_tokens,
        composite_score=composite_score,
        git_commit=git_commit,
    )


# ===================================================================
# TestBaselineSnapshot
# ===================================================================


class TestBaselineSnapshot:
    def test_creation(self) -> None:
        snap = _make_snapshot()
        assert snap.test_count == 100
        assert snap.tests_passed == 98
        assert snap.tests_failed == 2
        assert snap.financial_accuracy_rate == 0.95
        assert snap.total_tokens == 5000
        assert snap.composite_score == 98.0
        assert snap.git_commit == "abc1234"

    def test_frozen(self) -> None:
        snap = _make_snapshot()
        with pytest.raises(AttributeError):
            snap.test_count = 99  # type: ignore[misc]

    def test_to_dict(self) -> None:
        snap = _make_snapshot(git_commit=None)
        d = snap.to_dict()
        assert isinstance(d, dict)
        assert d["test_count"] == 100
        assert d["git_commit"] is None

    def test_from_dict_roundtrip(self) -> None:
        original = _make_snapshot()
        d = original.to_dict()
        restored = BaselineSnapshot.from_dict(d)
        assert restored == original

    def test_from_dict_optional_git_commit_missing(self) -> None:
        data = _make_snapshot().to_dict()
        del data["git_commit"]
        restored = BaselineSnapshot.from_dict(data)
        assert restored.git_commit is None


# ===================================================================
# TestRegressionDetector
# ===================================================================


class TestRegressionDetector:
    def setup_method(self) -> None:
        self.baseline = _make_snapshot()

    def test_no_regressions(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        current = _make_snapshot()
        regressions = detector.detect_regressions(current, self.baseline)
        assert regressions == []

    def test_critical_test_count_decreased(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        current = _make_snapshot(test_count=95, tests_passed=93, tests_failed=2)
        regressions = detector.detect_regressions(current, self.baseline)
        crits = [r for r in regressions if r.severity == Severity.CRITICAL]
        assert len(crits) == 1
        assert crits[0].metric_name == "test_count"
        assert "decreased" in crits[0].message

    def test_critical_new_failures(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        baseline_no_failures = _make_snapshot(tests_failed=0)
        current = _make_snapshot(test_count=101, tests_passed=99, tests_failed=2)
        regressions = detector.detect_regressions(current, baseline_no_failures)
        crits = [r for r in regressions if r.severity == Severity.CRITICAL]
        assert len(crits) == 1
        assert crits[0].metric_name == "tests_failed"

    def test_high_financial_accuracy_large_drop(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        current = _make_snapshot(financial_accuracy_rate=0.88)
        regressions = detector.detect_regressions(current, self.baseline)
        highs = [r for r in regressions if r.severity == Severity.HIGH]
        assert any(r.metric_name == "financial_accuracy_rate" for r in highs)

    def test_medium_financial_accuracy_small_drop(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        current = _make_snapshot(financial_accuracy_rate=0.93)
        regressions = detector.detect_regressions(current, self.baseline)
        mediums = [r for r in regressions if r.severity == Severity.MEDIUM]
        assert any(r.metric_name == "financial_accuracy_rate" for r in mediums)
        # Should NOT also have a HIGH for the same metric
        highs = [
            r
            for r in regressions
            if r.severity == Severity.HIGH
            and r.metric_name == "financial_accuracy_rate"
        ]
        assert highs == []

    def test_medium_token_usage_spike(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        current = _make_snapshot(total_tokens=8000)  # 60% increase
        regressions = detector.detect_regressions(current, self.baseline)
        mediums = [r for r in regressions if r.severity == Severity.MEDIUM]
        assert any(r.metric_name == "total_tokens" for r in mediums)

    def test_high_composite_score_drop(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        current = _make_snapshot(composite_score=97.0)  # 1.0 drop > 0.5
        regressions = detector.detect_regressions(current, self.baseline)
        highs = [r for r in regressions if r.severity == Severity.HIGH]
        assert any(r.metric_name == "composite_score" for r in highs)

    def test_save_and_load_snapshot(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        snap = _make_snapshot()
        detector.save_snapshot(snap, "v1")
        loaded = detector.load_snapshot("v1")
        assert loaded is not None
        assert loaded == snap

    def test_load_missing_snapshot_returns_none(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        assert detector.load_snapshot("nonexistent") is None

    def test_check_and_report_no_baseline(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        snap = _make_snapshot()
        regressions, passed = detector.check_and_report(snap, "v1")
        assert regressions == []
        assert passed is True
        # Should have saved the snapshot
        loaded = detector.load_snapshot("v1")
        assert loaded == snap

    def test_check_and_report_with_regressions(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        # Save baseline with 0 failures
        baseline = _make_snapshot(test_count=100, tests_failed=0, tests_passed=100)
        detector.save_snapshot(baseline, "v1")
        # Current has new failures
        current = _make_snapshot(test_count=99, tests_failed=1, tests_passed=98)
        regressions, passed = detector.check_and_report(current, "v1")
        assert len(regressions) > 0
        assert passed is False  # CRITICAL present

    def test_check_and_report_no_critical(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        detector.save_snapshot(self.baseline, "v1")
        # Small accuracy drop — MEDIUM only
        current = _make_snapshot(financial_accuracy_rate=0.93)
        regressions, passed = detector.check_and_report(current, "v1")
        assert len(regressions) > 0
        assert passed is True  # No CRITICAL

    def test_multiple_regressions_detected(self, tmp_path: Path) -> None:
        detector = RegressionDetector(str(tmp_path))
        baseline = _make_snapshot(test_count=100, tests_failed=0, tests_passed=100)
        current = _make_snapshot(
            test_count=90,
            tests_passed=88,
            tests_failed=2,
            financial_accuracy_rate=0.80,
            total_tokens=10000,
            composite_score=88.0,
        )
        regressions = detector.detect_regressions(current, baseline)
        assert len(regressions) >= 4

    def test_regression_dataclass_frozen(self, tmp_path: Path) -> None:
        r = Regression(
            metric_name="test_count",
            baseline_value=100.0,
            current_value=90.0,
            severity=Severity.CRITICAL,
            message="dropped",
        )
        with pytest.raises(AttributeError):
            r.severity = Severity.LOW  # type: ignore[misc]


# ===================================================================
# TestCollectBaseline
# ===================================================================


class TestCollectBaseline:
    def test_collect_baseline_with_mocked_output(self) -> None:
        mock_output = "42 passed, 3 failed in 1.23s"
        with patch("aos.regression.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            snap = collect_baseline(git_commit="deadbeef")
        assert snap.test_count == 45
        assert snap.tests_passed == 42
        assert snap.tests_failed == 3
        assert snap.git_commit == "deadbeef"
        assert snap.composite_score == round(42 / 45 * 100, 2)

    def test_collect_baseline_all_passing(self) -> None:
        mock_output = "10 passed in 0.50s"
        with patch("aos.regression.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            snap = collect_baseline(git_commit="ff00ff")
        assert snap.test_count == 10
        assert snap.tests_passed == 10
        assert snap.tests_failed == 0
        assert snap.composite_score == 100.0

    def test_collect_baseline_subprocess_failure(self) -> None:
        with patch("aos.regression.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("not found")
            snap = collect_baseline(git_commit="nope")
        assert snap.test_count == 0
        assert snap.tests_passed == 0
        assert snap.tests_failed == 0
        assert snap.git_commit == "nope"

    def test_collect_baseline_git_commit_auto(self) -> None:
        mock_output = "5 passed in 0.10s"
        with patch("aos.regression.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""
            snap = collect_baseline()
        assert snap.git_commit is not None


# ===================================================================
# TestParsePytestOutput
# ===================================================================


class TestParsePytestOutput:
    def test_passing_and_failing(self) -> None:
        tc, tp, tf = _parse_pytest_output("42 passed, 3 failed in 1.23s")
        assert tc == 45
        assert tp == 42
        assert tf == 3

    def test_only_passing(self) -> None:
        tc, tp, tf = _parse_pytest_output("10 passed in 0.50s")
        assert tc == 10
        assert tp == 10
        assert tf == 0

    def test_only_failing(self) -> None:
        tc, tp, tf = _parse_pytest_output("5 failed in 0.30s")
        assert tc == 5
        assert tp == 0
        assert tf == 5

    def test_empty_output(self) -> None:
        tc, tp, tf = _parse_pytest_output("")
        assert tc == 0
        assert tp == 0
        assert tf == 0

    def test_realistic_output(self) -> None:
        output = (
            "========================= test session starts ==========================\n"
            "platform linux -- Python 3.12.0, pytest-8.0.0\n"
            "collected 50 items\n"
            "..................................................   [100%]\n"
            "========================= 50 passed in 2.34s ===========================\n"
        )
        tc, tp, tf = _parse_pytest_output(output)
        assert tc == 50
        assert tp == 50
        assert tf == 0
