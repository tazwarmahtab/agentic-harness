"""Regression tests: evaluator failure must emit a useful report and fail closed.

These CLI tests use a synthetic fixture. They do not alter any Netso financial
assumption, golden threshold, or accepted expected result.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_evaluator(golden_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "aos.evaluator",
            "--golden-dir",
            str(golden_dir),
            "--fail-on-regression",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )


def test_mismatch_reports_failure_before_nonzero_exit(tmp_path: Path) -> None:
    fixture = {
        "agent_id": "AGT-EXEC-COO",
        "output": {"status": "synthetic"},
        "expected": {"passed": False, "violations": ["synthetic mismatch"]},
    }
    (tmp_path / "mismatch.json").write_text(json.dumps(fixture), encoding="utf-8")

    result = _run_evaluator(tmp_path)

    assert result.returncode != 0
    assert "Golden tests: 1 total, 0 passed, 1 failed" in result.stdout
    assert "mismatch.json" in result.stdout
    assert "Expected violations" in result.stdout
    assert "Actual violations" in result.stdout


def test_missing_golden_dataset_cannot_report_success(tmp_path: Path) -> None:
    absent_dir = tmp_path / "missing"

    result = _run_evaluator(absent_dir)

    assert result.returncode != 0
    assert "No golden fixtures" in (result.stdout + result.stderr)
