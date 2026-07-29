from unittest.mock import patch, MagicMock
from aos.alerts_orchestrator import validate_and_alert
from aos.constants import NETSO_FINANCIAL


@patch("aos.alerts_orchestrator._send_alerts")
def test_validate_and_alert_passes_clean_output(mock_alerts):
    result = validate_and_alert(
        {"dscr": 2.5, "ppa_rate": 10.0, "savings_pct": 23.0},
        "AGT-EXEC-CFO",
        NETSO_FINANCIAL,
    )
    assert result.passed is True
    mock_alerts.assert_not_called()


@patch("aos.alerts_orchestrator._send_alerts")
def test_validate_and_alert_fires_on_violation(mock_alerts):
    result = validate_and_alert(
        {"dscr": 1.5},
        "AGT-EXEC-CFO",
        NETSO_FINANCIAL,
    )
    assert result.passed is False
    mock_alerts.assert_called_once()


@patch("aos.alerting_telegram.TelegramAlertProvider.send")
@patch.dict("os.environ", {"AOS_TELEGRAM_BOT_TOKEN": "tok", "AOS_TELEGRAM_CHAT_ID": "123"})
def test_send_alerts_calls_telegram(mock_send):
    from aos.alerts_orchestrator import _send_alerts
    from aos.evaluator import ValidationResult

    result = ValidationResult(passed=False, violations=["DSCR below floor"])
    _send_alerts(result, "AGT-EXEC-CFO")
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["level"] == "critical"
    assert "DSCR" in call_kwargs["message"]


@patch.dict("os.environ", {}, clear=True)
def test_send_alerts_noop_without_config():
    from aos.alerts_orchestrator import _send_alerts
    from aos.evaluator import ValidationResult

    result = ValidationResult(passed=False, violations=["test"])
    _send_alerts(result, "AGT-EXEC-CFO")  # should not raise
