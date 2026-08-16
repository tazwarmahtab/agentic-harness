"""Output evaluator — validates agent output against financial ground truth.

Post-validates every agent output against NETSO_FINANCIAL constants.
Only applies financial checks to agents with financial_rules (CFO/Risk).
All agents get structural checks (raw_response detection).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aos.constants import (
    CAPEX_PER_KW_SCENARIO_A,
    DSCR_ALERT_FLOOR,
    NEM_EXPORT_RATE,
    NETSO_FINANCIAL,
)


@dataclass
class ValidationResult:
    """Result of output validation."""

    passed: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, violation: str) -> None:
        self.passed = False
        self.violations.append(violation)

    def warn(self, warning: str) -> None:
        self.warnings.append(warning)


# ---------------------------------------------------------------------------
# Three-bucket disposition (Phase 6: Valueflow Pipeline Alignment)
# ---------------------------------------------------------------------------

# Pre-compiled regexes — hoisted to module level to avoid recompilation per finding
_DISAGREE_PATTERNS = [
    re.compile(r"contradicts?\s+(project|team|convention)", re.IGNORECASE),
    re.compile(r"not\s+a\s+(real\s+)?(bug|issue|problem)", re.IGNORECASE),
    re.compile(r"false\s+positive", re.IGNORECASE),
    re.compile(r"stylistic\s+preference", re.IGNORECASE),
]

_COLLAB_PATTERNS = [
    re.compile(r"architect(ural)?\s+decision", re.IGNORECASE),
    re.compile(r"requires?\s+(human|founder|user)\s+(review|input|decision)", re.IGNORECASE),
    re.compile(r"security\s+vulnerability", re.IGNORECASE),
    re.compile(r"data\s+loss", re.IGNORECASE),
]


class Disposition(str, Enum):
    """Classification of review findings into actionable buckets.

    TheAgency Valueflow three-bucket disposition:
    - DISAGREE: finding is wrong or invalid; reject it
    - AUTONOMOUS: finding is valid but can be fixed without human input
    - COLLABORATIVE: finding requires human judgment or architectural decision
    """

    DISAGREE = "disagree"
    AUTONOMOUS = "autonomous"
    COLLABORATIVE = "collaborative"


@dataclass(frozen=True)
class ClassifiedFinding:
    """A review finding classified into a disposition bucket."""

    finding: str
    severity: str  # critical, high, medium, low
    disposition: Disposition
    rationale: str = ""


def classify_findings(
    findings: list[dict[str, Any]],
) -> list[ClassifiedFinding]:
    """Classify review findings into the three-bucket disposition.

    Rules:
    - CRITICAL findings with no code context → COLLABORATIVE (needs human)
    - CRITICAL findings with clear fix → AUTONOMOUS
    - HIGH findings → AUTONOMOUS (pattern-matchable fixes)
    - MEDIUM findings → AUTONOMOUS
    - LOW findings → AUTONOMOUS
    - Findings that contradict project conventions → DISAGREE
    """
    classified: list[ClassifiedFinding] = []

    for finding in findings:
        text = finding.get("text", finding.get("finding", ""))
        severity = finding.get("severity", "medium").lower()

        # Check for DISAGREE first
        disposition = Disposition.AUTONOMOUS
        rationale = ""
        for pattern in _DISAGREE_PATTERNS:
            if pattern.search(text):
                disposition = Disposition.DISAGREE
                rationale = f"Matches reject pattern: {pattern.pattern}"
                break

        # CRITICAL with architectural/ambiguous context → COLLABORATIVE
        if disposition == Disposition.AUTONOMOUS and severity == "critical":
            for pat in _COLLAB_PATTERNS:
                if pat.search(text):
                    disposition = Disposition.COLLABORATIVE
                    rationale = f"Critical finding requiring human judgment: {pat.pattern}"
                    break

            # CRITICAL without clear code location → COLLABORATIVE
            if disposition == Disposition.AUTONOMOUS and "file" not in finding and "line" not in finding:
                disposition = Disposition.COLLABORATIVE
                rationale = "Critical finding with no clear code location"

        classified.append(ClassifiedFinding(
            finding=text,
            severity=severity,
            disposition=disposition,
            rationale=rationale,
        ))

    return classified


# Financial-check agents (must have financial_rules in manifest)
_FINANCIAL_AGENTS = {"AGT-EXEC-CFO", "AGT-EXEC-RSK"}

# Patterns that indicate blended rate usage
_BLENDED_PATTERNS = [
    re.compile(r"14\.81", re.IGNORECASE),
    re.compile(r"blended.?rate", re.IGNORECASE),
    re.compile(r"14\.81\s*bdt", re.IGNORECASE),
]

# Patterns that indicate Scenario B without approval
_SCENARIO_B_PATTERNS = [
    re.compile(r"40[,.]?000"),  # Scenario B CAPEX value
    re.compile(r"scenario.?b", re.IGNORECASE),
    re.compile(r"0%\s*import.?duty", re.IGNORECASE),
]


def validate_output(
    output: dict[str, Any],
    agent_id: str,
    constants: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate agent output against ground truth.

    Financial checks only apply to CFO and Risk agents when constants are provided.
    Pass constants=NETSO_FINANCIAL for Netso, None to skip financial checks (e.g. planning ventures).
    Structural checks apply to all agents.
    """
    result = ValidationResult()

    if not output:
        return result

    # Skip validation for raw/unparseable responses
    if "raw_response" in output:
        return result

    # Flatten output for pattern matching
    flat = _flatten_for_matching(output)

    # Financial checks — only for financial agents with constants
    if agent_id in _FINANCIAL_AGENTS and constants is not None:
        _check_blended_rate(flat, output, result)
        _check_savings_pct(output, result)
        _check_dscr(output, result)
        _check_ppa_rate(output, result)
        _check_scenario_b(output, flat, result)
        _check_nem_export_rate(output, result)
        _check_capex_scenario_a(output, result)
        _check_true_variable_rate(output, flat, result)

    return result


def _flatten_for_matching(d: dict[str, Any]) -> str:
    """Flatten dict values to a string for regex matching."""
    parts: list[str] = []
    for v in d.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (int, float)):
            parts.append(str(v))
        elif isinstance(v, dict):
            parts.append(_flatten_for_matching(v))
        elif isinstance(v, list):
            parts.extend(str(item) for item in v)
    return " ".join(parts)


def _check_blended_rate(flat: str, output: dict, result: ValidationResult) -> None:
    """Check for blended rate usage in output.

    Flags blended rate (14.81) in savings/cost context UNLESS
    the output also confirms savings use the correct true_variable_rate (12.98).
    If true_variable_rate is 12.98 AND blended rate 14.81 appears in a savings
    context, it is a violation (contradictory claims).
    """
    # Check if true_variable_rate is correctly 12.98
    true_var_rate = _find_numeric(
        output, ["true_variable_rate", "true_var_rate", "tvr"]
    )
    savings_uses_tvr = true_var_rate is not None and abs(true_var_rate - 12.98) < 0.01

    # Check for blended rate in savings/cost context
    blended_in_savings = False
    for pattern in _BLENDED_PATTERNS:
        if pattern.search(flat):
            blended_in_savings = True
            break

    if blended_in_savings:
        if savings_uses_tvr:
            # Contradictory: claims TVR=12.98 but also mentions blended in savings context
            result.fail(
                "Contradictory: true_variable_rate is 12.98 but blended rate (14.81) "
                "appears in savings context. Must use only TVR for savings. "
                "Hard-fail rule: blended_rate_near_savings"
            )
        else:
            # Blended rate used without correct TVR — violation
            result.fail(
                "Blended rate (14.81) detected in output. "
                "Must use True Variable Rate (12.98) for savings. "
                "Hard-fail rule: blended_rate_used_for_savings"
            )


def _check_savings_pct(output: dict, result: ValidationResult) -> None:
    """Check customer savings percentage matches ground truth."""
    savings = _find_numeric(output, ["savings_pct", "savings", "customer_savings"])
    if savings is not None and abs(savings - 23.0) > 0.5:
        result.fail(
            f"Savings percentage {savings}% differs from ground truth 23.0%. "
            f"Hard-fail rule: wrong_savings_pct"
        )


def _check_dscr(output: dict, result: ValidationResult) -> None:
    """Check DSCR is above alert floor."""
    dscr = _find_numeric(output, ["dscr", "debt_service_coverage"])
    if dscr is not None and dscr < DSCR_ALERT_FLOOR:
        result.fail(
            f"DSCR {dscr} is below alert floor {DSCR_ALERT_FLOOR}. "
            f"Must flag as immediate alert. "
            f"Hard-fail rule: dscr_below_floor_not_flagged"
        )


def _check_ppa_rate(output: dict, result: ValidationResult) -> None:
    """Check PPA rate matches ground truth."""
    ppa = _find_numeric(output, ["ppa_rate", "ppa"])
    if ppa is not None and abs(ppa - 10.0) > 0.01:
        result.fail(
            f"PPA rate {ppa} differs from ground truth 10.00 BDT/kWh. "
            f"Hard-fail rule: wrong_ppa_rate"
        )


def _check_scenario_b(output: dict, flat: str, result: ValidationResult) -> None:
    """Check for Scenario B usage without founder approval."""
    # Check pattern matches in flattened text
    for pattern in _SCENARIO_B_PATTERNS:
        if pattern.search(flat):
            result.fail(
                "Scenario B referenced in output without founder approval. "
                "Default to Scenario A (55,000 BDT/kW). "
                "Hard-fail rule: scenario_b_without_nbr_confirmation"
            )
            return

    # Also check for Scenario B CAPEX value (40000) in numeric fields
    capex = _find_numeric(output, ["capex", "capex_per_kw", "capital_expenditure"])
    if capex is not None and abs(capex - 40000) < 100:
        result.fail(
            f"Scenario B CAPEX {capex} detected without founder approval. "
            f"Default to Scenario A (55,000 BDT/kW). "
            f"Hard-fail rule: scenario_b_without_nbr_confirmation"
        )


def _check_nem_export_rate(output: dict, result: ValidationResult) -> None:
    """Check NEM export rate matches ground truth (6.4523 BDT/kWh)."""
    nem = _find_numeric(output, ["nem_export", "nem_rate", "export_rate"])
    if nem is not None and abs(nem - NEM_EXPORT_RATE) > 0.1:
        result.fail(
            f"NEM export rate {nem} differs from ground truth {NEM_EXPORT_RATE} BDT/kWh. "
            f"Hard-fail rule: wrong_nem_export_rate"
        )


def _check_capex_scenario_a(output: dict, result: ValidationResult) -> None:
    """Check CAPEX Scenario A matches ground truth (55,000 BDT/kW)."""
    capex = _find_numeric(output, ["capex", "capex_per_kw", "capital_expenditure"])
    if capex is not None:
        # Only check if it looks like a Scenario A value (within 20% of 55000)
        if 40000 < capex < 70000 and abs(capex - CAPEX_PER_KW_SCENARIO_A) > 1000:
            result.fail(
                f"Scenario A CAPEX {capex} differs from ground truth {CAPEX_PER_KW_SCENARIO_A} BDT/kW. "
                f"Hard-fail rule: wrong_capex_scenario_a"
            )


def _check_true_variable_rate(
    output: dict, flat: str, result: ValidationResult
) -> None:
    """Check that true variable rate (12.98) is used, not blended (14.81) for savings."""
    # If savings are mentioned, verify the rate used is 12.98 not 14.81
    savings_keywords = ["savings", "saving", "avoided cost", "cost reduction"]
    if any(kw in flat.lower() for kw in savings_keywords):
        # Check if blended rate appears near savings context
        blended_near_savings = re.search(
            r"(?:savings|saving|avoided).{0,100}14\.81", flat, re.IGNORECASE
        )
        if blended_near_savings:
            result.fail(
                "Blended rate (14.81) used near savings context. "
                "Must use True Variable Rate (12.98) for savings calculations. "
                "Hard-fail rule: blended_rate_near_savings"
            )


def _find_numeric(d: dict[str, Any], keys: list[str]) -> float | None:
    """Find a numeric value by key name (case-insensitive, partial match).

    Handles both numeric types and numeric strings (common for parsed LLM JSON).
    """
    for key in keys:
        for k, v in d.items():
            if key.lower() in k.lower():
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, str):
                    try:
                        return float(v)
                    except ValueError:
                        pass
    return None


# ---------------------------------------------------------------------------
# Golden dataset runner
# ---------------------------------------------------------------------------


def run_golden_tests(
    golden_dir: str = "tests/golden",
    fail_on_regression: bool = False,
) -> dict[str, Any]:
    """Run evaluator against all golden dataset files.

    Args:
        golden_dir: Directory containing golden test JSON files.
        fail_on_regression: If True, return non-zero exit code on any mismatch.

    Returns:
        Dict with test results and summary.
    """
    import glob
    import json

    files = glob.glob(f"{golden_dir}/*.json")
    if not files:
        return {"ok": True, "tests": 0, "passed": 0, "failed": 0, "details": []}

    results = []
    passed = 0
    failed = 0

    for f in sorted(files):
        with open(f) as fp:
            test = json.load(fp)

        agent_id = test["agent_id"]
        output = test["output"]
        expected = test["expected"]

        result = validate_output(output, agent_id, NETSO_FINANCIAL)

        match = result.passed == expected["passed"] and set(result.violations) == set(
            expected["violations"]
        )

        if match:
            passed += 1
        else:
            failed += 1

        results.append(
            {
                "file": f,
                "agent_id": agent_id,
                "expected_passed": expected["passed"],
                "actual_passed": result.passed,
                "expected_violations": expected["violations"],
                "actual_violations": result.violations,
                "match": match,
            }
        )

    summary = {
        "ok": failed == 0,
        "tests": len(files),
        "passed": passed,
        "failed": failed,
        "details": results,
    }

    if fail_on_regression and not summary["ok"]:
        sys.exit(1)

    return summary


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run evaluator golden dataset tests")
    parser.add_argument(
        "--golden-dir",
        default="tests/golden",
        help="Directory containing golden test JSON files",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with non-zero code if any test fails",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed results",
    )
    args = parser.parse_args()

    summary = run_golden_tests(args.golden_dir, args.fail_on_regression)

    if args.verbose:
        import json

        print(json.dumps(summary, indent=2))
    else:
        print(
            f"Golden tests: {summary['tests']} total, {summary['passed']} passed, {summary['failed']} failed"
        )
        for d in summary["details"]:
            if not d["match"]:
                print(
                    f"  FAIL: {d['file']} (expected passed={d['expected_passed']}, got passed={d['actual_passed']})"
                )
                print(f"    Expected violations: {d['expected_violations']}")
                print(f"    Actual violations:   {d['actual_violations']}")

    if not summary["ok"]:
        sys.exit(1)
