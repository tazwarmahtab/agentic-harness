"""Tests for TAZ OS output evaluator — validates agent output against ground truth."""

from __future__ import annotations

import pytest
from tazos.constants import NETSO_FINANCIAL
from tazos.evaluator import validate_output, ValidationResult


class TestValidateOutput:
    def test_clean_output_passes(self) -> None:
        output = {"savings_pct": 23.0, "rate_used": 12.98}
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert result.passed

    def test_blended_rate_detected(self) -> None:
        output = {"savings_pct": 14.0, "rate_used": 14.81, "note": "based on blended rate"}
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert not result.passed
        assert any("blended" in v.lower() for v in result.violations)

    def test_wrong_savings_pct_detected(self) -> None:
        output = {"savings_pct": 14.0, "rate_used": 12.98}
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert not result.passed
        assert any("savings" in v.lower() for v in result.violations)

    def test_non_cfo_agent_skips_financial_checks(self) -> None:
        output = {"whatever": 14.81}
        result = validate_output(output, "AGT-EXEC-COO", NETSO_FINANCIAL)
        assert result.passed

    def test_empty_output_passes(self) -> None:
        result = validate_output({}, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert result.passed

    def test_raw_response_passes(self) -> None:
        output = {"raw_response": "I couldn't parse the response"}
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert result.passed

    def test_dscr_below_floor_detected(self) -> None:
        output = {"dscr": 1.8, "savings_pct": 23.0}
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert not result.passed
        assert any("dscr" in v.lower() for v in result.violations)

    def test_ppa_rate_wrong_detected(self) -> None:
        output = {"ppa_rate": 12.0, "savings_pct": 23.0}
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert not result.passed
        assert any("ppa" in v.lower() for v in result.violations)

    def test_scenario_b_without_approval_detected(self) -> None:
        output = {"capex_per_kw": 40000, "savings_pct": 23.0}
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert not result.passed
        assert any("scenario" in v.lower() for v in result.violations)

    def test_correct_values_all_pass(self) -> None:
        output = {
            "savings_pct": 23.0,
            "rate_used": 12.98,
            "ppa_rate": 10.00,
            "dscr": 2.25,
            "capex_per_kw": 55000,
        }
        result = validate_output(output, "AGT-EXEC-CFO", NETSO_FINANCIAL)
        assert result.passed

    def test_risk_agent_also_validated(self) -> None:
        output = {"dscr": 1.5}
        result = validate_output(output, "AGT-EXEC-RSK", NETSO_FINANCIAL)
        assert not result.passed


class TestValidateOutputPlanningVenture:
    """Financial checks are skipped when constants=None (planning ventures)."""

    def test_cfo_with_none_constants_skips_financial(self) -> None:
        output = {"savings_pct": 14.0, "rate_used": 14.81, "note": "bad"}
        result = validate_output(output, "AGT-EXEC-CFO", constants=None)
        assert result.passed

    def test_rsk_with_none_constants_skips_financial(self) -> None:
        output = {"dscr": 1.5}
        result = validate_output(output, "AGT-EXEC-RSK", constants=None)
        assert result.passed

    def test_non_financial_agent_still_works_with_none(self) -> None:
        output = {"whatever": 14.81}
        result = validate_output(output, "AGT-EXEC-COO", constants=None)
        assert result.passed
