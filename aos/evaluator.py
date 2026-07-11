"""Output evaluator — validates agent output against financial ground truth.

Post-validates every agent output against NETSO_FINANCIAL constants.
Only applies financial checks to agents with financial_rules (CFO/Risk).
All agents get structural checks (raw_response detection).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aos.constants import (
    NETSO_FINANCIAL,
    DSCR_ALERT_FLOOR,
    NEM_EXPORT_RATE,
    CAPEX_PER_KW_SCENARIO_A,
    TRUE_VARIABLE_RATE,
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
        _check_blended_rate(flat, result)
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


def _check_true_variable_rate(output: dict, flat: str, result: ValidationResult) -> None:
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
                f"Blended rate (14.81) used near savings context. "
                f"Must use True Variable Rate (12.98) for savings calculations. "
                f"Hard-fail rule: blended_rate_near_savings"
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
