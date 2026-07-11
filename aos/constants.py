"""Netso Energy financial constants — machine-readable ground truth.

Canonical source: ~/Documents/10-Projects/Netso_HQ/GROUND_TRUTH_CONSTANTS.md
Generator: ai_system/System/scripts/core_economics.py

NEVER deviate from these values. NEVER use blended_rate for savings.
"""

# === Scenario A (baseline) ===
CAPEX_PER_KW_SCENARIO_A = 55_000  # BDT/kW (EPC 40K + dev margin 15K)
DSCR_SCENARIO_A = 2.25
PROJECT_PAYBACK_A = 4.1  # years
LEVERED_IRR_A = 68.7  # %

# === Scenario B (policy upside — conditional on NBR confirmation) ===
CAPEX_PER_KW_SCENARIO_B = 40_000  # BDT/kW (0% import duty)
DSCR_SCENARIO_B = 3.09
PROJECT_PAYBACK_B = 3.0  # years
LEVERED_IRR_B = 114.1  # %

# === Rates ===
TRUE_VARIABLE_RATE = 12.98  # BDT/kWh (MT-2, excl. fixed demand charge)
BLENDED_RATE = 14.81  # BDT/kWh — NEVER use for savings calculations
PPA_RATE = 10.00  # BDT/kWh (3% triennial escalation)
NEM_EXPORT_RATE = 6.4523  # BDT/kWh
CUSTOMER_SAVINGS_PCT = 23.0  # % vs True Variable Rate

# === Risk thresholds ===
DSCR_ALERT_FLOOR = 2.0  # immediate alert below this

# === Infrastructure ===
CAPACITY_FACTOR = 16.5  # % (Chattogram pilot-verified)
OPEX_PER_KW = 1_000  # BDT/kW

# === IDCOL Debt ===
IDCOL_DEBT_PCT = 80  # %
IDCOL_INTEREST = 6.0  # % p.a.
IDCOL_TERM_YEARS = 10

# === Approval thresholds ===
PROPOSAL_VALUE_THRESHOLD_BDT = 5_000_000

# All constants as a dict for validation
NETSO_FINANCIAL: dict[str, float | int] = {
    "capex_per_kw_scenario_a": CAPEX_PER_KW_SCENARIO_A,
    "capex_per_kw_scenario_b": CAPEX_PER_KW_SCENARIO_B,
    "true_variable_rate": TRUE_VARIABLE_RATE,
    "blended_rate": BLENDED_RATE,
    "ppa_rate": PPA_RATE,
    "customer_savings_pct": CUSTOMER_SAVINGS_PCT,
    "nem_export_rate": NEM_EXPORT_RATE,
    "idcol_debt_pct": IDCOL_DEBT_PCT,
    "idcol_interest": IDCOL_INTEREST,
    "idcol_term_years": IDCOL_TERM_YEARS,
    "dscr_scenario_a": DSCR_SCENARIO_A,
    "dscr_scenario_b": DSCR_SCENARIO_B,
    "dscr_alert_floor": DSCR_ALERT_FLOOR,
    "capacity_factor": CAPACITY_FACTOR,
    "opex_per_kw": OPEX_PER_KW,
    "project_payback_a": PROJECT_PAYBACK_A,
    "project_payback_b": PROJECT_PAYBACK_B,
    "levered_irr_a": LEVERED_IRR_A,
    "levered_irr_b": LEVERED_IRR_B,
}
