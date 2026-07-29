def test_constants_match_ground_truth():
    """Verify aos/constants.py matches GROUND_TRUTH_CONSTANTS.md."""
    from aos.constants import (
        CAPEX_PER_KW_SCENARIO_A,
        PPA_RATE,
        TRUE_VARIABLE_RATE,
        DSCR_ALERT_FLOOR,
        NEM_EXPORT_RATE,
        CUSTOMER_SAVINGS_PCT,
    )
    assert CAPEX_PER_KW_SCENARIO_A == 55_000
    assert PPA_RATE == 10.0
    assert TRUE_VARIABLE_RATE == 12.98
    assert DSCR_ALERT_FLOOR == 2.0
    assert NEM_EXPORT_RATE == 6.4523
    assert CUSTOMER_SAVINGS_PCT == 23.0
