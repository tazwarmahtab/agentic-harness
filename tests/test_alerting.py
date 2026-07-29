from unittest.mock import patch, MagicMock
from aos.alerting import AlertingService, Alert

def test_alert_dscr_breach():
    svc = AlertingService(webhook_url=None)
    alert = Alert(level="critical", source="evaluator", message="DSCR 1.8 below alert floor 2.0", venture="netso")
    svc.send(alert)
    assert len(svc.sent) == 1

def test_alert_empty_url_just_logs():
    svc = AlertingService(webhook_url="")
    alert = Alert(level="warning", source="evaluator", message="test", venture="netso")
    svc.send(alert)
    assert len(svc.sent) == 1

@patch("httpx.post")
def test_alert_webhook_sends_http(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp
    svc = AlertingService(webhook_url="https://hooks.slack.com/test")
    alert = Alert(level="critical", source="evaluator", message="PPA deviation", venture="netso")
    svc.send(alert)
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "hooks.slack.com" in str(call_args)
