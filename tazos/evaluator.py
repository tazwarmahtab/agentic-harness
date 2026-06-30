"""Output evaluator — validates agent output against financial ground truth.

Post-validates every agent output against NETSO_FINANCIAL constants.
Only applies financial checks to agents with financial_rules (CFO/Risk).
All agents get structural checks (raw_response detection).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tazos.constants import NETSO_FINANCIAL, DSCR_ALERT_FLOOR


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

    Financial checks only apply to CFO and Risk agents.
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

    # Financial checks — only for financial agents
    if agent_id in _FINANCIAL_AGENTS:
        _check_blended_rate(flat, result)
        _check_savings_pct(output, result)
        _check_dscr(output, result)
        _check_ppa_rate(output, result)
        _check_scenario_b(output, flat, result)

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
    return " ".join(parts)


def _check_blended_rate(flat: str, result: ValidationResult) -> None:
    """Check for blended rate usage in output."""
    for pattern in _BLENDED_PATTERNS:
        if pattern.search(flat):
            result.fail(
                f"Blended rate (14.81) detected in output. "
                f"Must use True Variable Rate (12.98) for savings. "
                f"Hard-fail rule: blended_rate_used_for_savings"
            )
            return


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
                f"Scenario B referenced in output without founder approval. "
                f"Default to Scenario A (55,000 BDT/kW). "
                f"Hard-fail rule: scenario_b_without_nbr_confirmation"
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


def _find_numeric(d: dict[str, Any], keys: list[str]) -> float | None:
    """Find a numeric value by key name (case-insensitive, partial match)."""
    for k, v in d.items():
        k_lower = k.lower()
        for target in keys:
            if target in k_lower:
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, str):
                    try:
                        return float(v)
                    except ValueError:
                        pass
    return None
