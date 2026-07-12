"""Regression detection for baseline evaluation snapshots.

Compares current evaluation metrics against saved baselines to detect
regressions across releases. Persists snapshots as JSON files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class Regression:
    """A single detected regression between two snapshots."""

    metric_name: str
    baseline_value: float
    current_value: float
    severity: Severity
    message: str


@dataclass(frozen=True)
class BaselineSnapshot:
    """Immutable snapshot of evaluation metrics at a point in time."""

    timestamp: str
    test_count: int
    tests_passed: int
    tests_failed: int
    financial_accuracy_rate: float
    total_tokens: int
    composite_score: float
    git_commit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineSnapshot:
        """Deserialize from a dict."""
        return cls(
            timestamp=data["timestamp"],
            test_count=data["test_count"],
            tests_passed=data["tests_passed"],
            tests_failed=data["tests_failed"],
            financial_accuracy_rate=data["financial_accuracy_rate"],
            total_tokens=data["total_tokens"],
            composite_score=data["composite_score"],
            git_commit=data.get("git_commit"),
        )


class RegressionDetector:
    """Detects regressions by comparing a current snapshot against a saved baseline."""

    def __init__(self, baseline_dir: str) -> None:
        self._baseline_dir = Path(baseline_dir)
        self._baseline_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, snapshot: BaselineSnapshot, name: str) -> Path:
        """Save a snapshot to baseline_dir/{name}.json."""
        path = self._baseline_dir / f"{name}.json"
        path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
        return path

    def load_snapshot(self, name: str) -> BaselineSnapshot | None:
        """Load a snapshot from baseline_dir/{name}.json, or None if missing."""
        path = self._baseline_dir / f"{name}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return BaselineSnapshot.from_dict(data)

    def detect_regressions(
        self, current: BaselineSnapshot, baseline: BaselineSnapshot
    ) -> list[Regression]:
        """Compare current against baseline and return detected regressions."""
        regressions: list[Regression] = []

        # 1. test_count decreased → CRITICAL
        if current.test_count < baseline.test_count:
            regressions.append(
                Regression(
                    metric_name="test_count",
                    baseline_value=float(baseline.test_count),
                    current_value=float(current.test_count),
                    severity=Severity.CRITICAL,
                    message=(
                        f"Test count decreased from {baseline.test_count} "
                        f"to {current.test_count}"
                    ),
                )
            )

        # 2. tests_failed increased from 0 → CRITICAL
        if baseline.tests_failed == 0 and current.tests_failed > 0:
            regressions.append(
                Regression(
                    metric_name="tests_failed",
                    baseline_value=float(baseline.tests_failed),
                    current_value=float(current.tests_failed),
                    severity=Severity.CRITICAL,
                    message=(
                        f"New test failures introduced: "
                        f"{current.tests_failed} failure(s) vs 0 baseline"
                    ),
                )
            )

        # 3. financial_accuracy_rate decreased by >0.05 → HIGH
        acc_delta = baseline.financial_accuracy_rate - current.financial_accuracy_rate
        if acc_delta > 0.05:
            regressions.append(
                Regression(
                    metric_name="financial_accuracy_rate",
                    baseline_value=baseline.financial_accuracy_rate,
                    current_value=current.financial_accuracy_rate,
                    severity=Severity.HIGH,
                    message=(
                        f"Financial accuracy dropped by {acc_delta:.4f} "
                        f"(from {baseline.financial_accuracy_rate:.4f} "
                        f"to {current.financial_accuracy_rate:.4f})"
                    ),
                )
            )
        # 4. financial_accuracy_rate decreased by >0.01 → MEDIUM (only if not already HIGH)
        elif acc_delta > 0.01:
            regressions.append(
                Regression(
                    metric_name="financial_accuracy_rate",
                    baseline_value=baseline.financial_accuracy_rate,
                    current_value=current.financial_accuracy_rate,
                    severity=Severity.MEDIUM,
                    message=(
                        f"Financial accuracy dropped by {acc_delta:.4f} "
                        f"(from {baseline.financial_accuracy_rate:.4f} "
                        f"to {current.financial_accuracy_rate:.4f})"
                    ),
                )
            )

        # 5. total_tokens increased by >50% → MEDIUM
        if baseline.total_tokens > 0:
            token_ratio = (current.total_tokens - baseline.total_tokens) / baseline.total_tokens
            if token_ratio > 0.50:
                regressions.append(
                    Regression(
                        metric_name="total_tokens",
                        baseline_value=float(baseline.total_tokens),
                        current_value=float(current.total_tokens),
                        severity=Severity.MEDIUM,
                        message=(
                            f"Token usage increased by {token_ratio * 100:.1f}% "
                            f"(from {baseline.total_tokens} to {current.total_tokens})"
                        ),
                    )
                )

        # 6. composite_score decreased by >0.5 → HIGH
        score_delta = baseline.composite_score - current.composite_score
        if score_delta > 0.5:
            regressions.append(
                Regression(
                    metric_name="composite_score",
                    baseline_value=baseline.composite_score,
                    current_value=current.composite_score,
                    severity=Severity.HIGH,
                    message=(
                        f"Composite score dropped by {score_delta:.4f} "
                        f"(from {baseline.composite_score:.4f} "
                        f"to {current.composite_score:.4f})"
                    ),
                )
            )

        return regressions

    def check_and_report(
        self, current: BaselineSnapshot, name: str
    ) -> tuple[list[Regression], bool]:
        """Load existing baseline, compare, and report.

        Returns (regressions, passed) where passed=True if no CRITICAL regressions.
        If no baseline exists, saves current as new baseline and returns ([], True).
        """
        baseline = self.load_snapshot(name)
        if baseline is None:
            self.save_snapshot(current, name)
            return ([], True)

        regressions = self.detect_regressions(current, baseline)
        has_critical = any(r.severity == Severity.CRITICAL for r in regressions)
        return regressions, not has_critical


def _get_git_commit() -> str | None:
    """Return the current git commit hash, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def collect_baseline(git_commit: str | None = None) -> BaselineSnapshot:
    """Run pytest programmatically and build a BaselineSnapshot from the results.

    Executes ``python -m pytest`` in a subprocess, parses the terminal output
    to extract pass/fail counts, and returns a snapshot.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    commit = git_commit if git_commit is not None else _get_git_commit()

    test_count = 0
    tests_passed = 0
    tests_failed = 0

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        test_count, tests_passed, tests_failed = _parse_pytest_output(output)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    passed_rate = tests_passed / max(test_count, 1)
    composite_score = round(passed_rate * 100, 2)

    return BaselineSnapshot(
        timestamp=timestamp,
        test_count=test_count,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        financial_accuracy_rate=1.0,
        total_tokens=0,
        composite_score=composite_score,
        git_commit=commit,
    )


def _parse_pytest_output(output: str) -> tuple[int, int, int]:
    """Parse pytest terminal output to extract test counts.

    Handles lines like ``"5 passed, 1 failed in 0.12s"`` or ``"12 passed in 1.0s"``.
    """
    import re

    test_count = 0
    tests_passed = 0
    tests_failed = 0

    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        tests_passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        tests_failed = int(failed_match.group(1))

    test_count = tests_passed + tests_failed
    return test_count, tests_passed, tests_failed
