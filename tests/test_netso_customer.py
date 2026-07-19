"""Tests for Netso customer dashboard service."""

from __future__ import annotations

import pytest

from aos.services.netso_customer import (
    GenerationData,
    SavingsData,
    BillingData,
    PortfolioData,
    FinancialsData,
    get_generation,
    get_savings,
    get_billing,
    get_portfolio,
    get_financials,
)


@pytest.mark.unit
class TestGenerationData:
    def test_to_dict_has_required_keys(self):
        data = GenerationData(
            customer_id="CGS-001",
            customer_name="Test",
            system_capacity_kw=850,
            current_month={"generation_kwh": 12750},
            ytd={"generation_kwh": 76500},
            trend=[],
            alerts=[],
            last_updated="2026-07-20T08:00:00",
        )
        result = data.to_dict()
        assert "customer_id" in result
        assert "system_capacity_kw" in result
        assert "current_month" in result
        assert "ytd" in result
        assert "trend" in result
        assert "alerts" in result

    def test_to_dict_is_frozen(self):
        data = GenerationData(
            customer_id="CGS-001",
            customer_name="Test",
            system_capacity_kw=850,
            current_month={},
            ytd={},
            trend=[],
            alerts=[],
            last_updated="",
        )
        with pytest.raises(AttributeError):
            data.customer_id = "CHANGED"


@pytest.mark.unit
class TestGetGeneration:
    def test_returns_generation_for_valid_site(self):
        result = get_generation("CGS-001")
        assert result is not None
        assert result.customer_id == "CGS-001"
        assert result.system_capacity_kw == 850
        assert "generation_kwh" in result.current_month

    def test_returns_none_for_unknown_site(self):
        result = get_generation("NONEXISTENT")
        assert result is None

    def test_to_dict_matches_spec_shape(self):
        result = get_generation("CGS-001")
        assert result is not None
        d = result.to_dict()
        assert set(d.keys()) == {
            "customer_id", "customer_name", "system_capacity_kw",
            "current_month", "ytd", "trend", "alerts", "last_updated",
        }


@pytest.mark.unit
class TestGetSavings:
    def test_returns_savings_for_valid_site(self):
        result = get_savings("CGS-001")
        assert result is not None
        assert result.grid_rate_bdt_per_kwh == 12.98
        assert result.ppa_rate_bdt_per_kwh == 10.00
        assert result.savings_pct == 23.0

    def test_savings_math_is_correct(self):
        result = get_savings("CGS-001")
        assert result is not None
        gen_kwh = result.current_month["generation_kwh"]
        expected_grid = gen_kwh * 12.98
        expected_ppa = gen_kwh * 10.00
        expected_savings = expected_grid - expected_ppa
        assert result.current_month["grid_cost_bdt"] == round(expected_grid, 2)
        assert result.current_month["ppa_cost_bdt"] == round(expected_ppa, 2)
        assert result.current_month["savings_bdt"] == round(expected_savings, 2)

    def test_returns_none_for_unknown_site(self):
        assert get_savings("NONEXISTENT") is None


@pytest.mark.unit
class TestGetBilling:
    def test_returns_billing_for_valid_site(self):
        result = get_billing("CGS-001")
        assert result is not None
        assert result.customer_id == "CGS-001"
        assert len(result.history) == 3

    def test_current_invoice_is_pending(self):
        result = get_billing("CGS-001")
        assert result is not None
        assert result.current_invoice["status"] == "pending"

    def test_outstanding_matches_pending(self):
        result = get_billing("CGS-001")
        assert result is not None
        pending = [i for i in result.history if i["status"] == "pending"]
        expected = sum(i["amount_bdt"] for i in pending)
        assert result.outstanding["total_bdt"] == expected

    def test_returns_none_for_unknown_site(self):
        assert get_billing("NONEXISTENT") is None


@pytest.mark.unit
class TestGetPortfolio:
    def test_returns_portfolio_with_customers(self):
        result = get_portfolio()
        assert result.total_customers >= 1
        assert len(result.customers) >= 1

    def test_financial_constants_match_ground_truth(self):
        result = get_portfolio()
        fc = result.financial_constants
        assert fc["true_variable_rate"] == 12.98
        assert fc["ppa_rate"] == 10.00
        assert fc["customer_savings_pct"] == 23.0


@pytest.mark.unit
class TestGetFinancials:
    def test_returns_financials_with_scenarios(self):
        result = get_financials()
        assert result.scenarios["scenario_a"]["dscr"] == 2.25
        assert result.scenarios["scenario_b"]["dscr"] == 3.09

    def test_opex_is_monthly_not_annual(self):
        result = get_financials()
        annual = result.portfolio_financials["annual_opex_bdt"]
        monthly = result.portfolio_financials["monthly_opex_bdt"]
        assert monthly == round(annual / 12, 2)
