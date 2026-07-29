from unittest.mock import patch, MagicMock
from aos.alerting_telegram import TelegramAlertProvider


@patch("httpx.post")
def test_telegram_sends_message(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp

    provider = TelegramAlertProvider(bot_token="test-token-123", chat_id="123456789")
    provider.send(level="critical", source="evaluator", message="DSCR 1.8 below floor", venture="netso")
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "api.telegram.org" in call_args[0][0]
    assert "test-token-123" in call_args[0][0]


@patch("httpx.post")
def test_telegram_cooldown_suppresses_duplicate(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp

    provider = TelegramAlertProvider(bot_token="tok", chat_id="123", cooldown_seconds=300)
    provider.send(level="critical", source="evaluator", message="DSCR breach", venture="netso")
    provider.send(level="critical", source="evaluator", message="DSCR breach", venture="netso")
    assert mock_post.call_count == 1


@patch("httpx.post")
def test_telegram_send_returns_true(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    provider = TelegramAlertProvider(bot_token="tok", chat_id="123")
    result = provider.send(level="info", source="test", message="hello", venture="x")
    assert result is True
