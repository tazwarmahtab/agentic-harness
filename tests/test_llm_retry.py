"""Tests for RouterLLMClient.complete() retry and fallback logic, plus _parse_first_json."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from aos.llm import MODEL_TABLE, RouterLLMClient, _parse_first_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(body: dict) -> MagicMock:
    """Build a mock HTTP response that decodes to *body*."""
    raw = json.dumps(body).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _make_client(**kwargs) -> RouterLLMClient:
    """Construct a RouterLLMClient with env vars neutralised."""
    defaults = {"base_url": "http://localhost:20128", "api_key": ""}
    defaults.update(kwargs)
    return RouterLLMClient(**defaults)


# Shared valid response body
_OK_BODY: dict = {
    "model": "cu/claude-4.5-sonnet",
    "choices": [{"message": {"content": "hello world"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> RouterLLMClient:
    return _make_client(timeout=5)


@pytest.fixture
def call_kwargs() -> dict:
    return {
        "model": "cu/claude-4.5-sonnet",
        "system": "You are helpful.",
        "messages": [{"role": "user", "content": "hi"}],
    }


# ---------------------------------------------------------------------------
# 1. test_retry_on_urlerror
# ---------------------------------------------------------------------------


class TestRetryOnError:
    def test_retry_on_urlerror(
        self, client: RouterLLMClient, call_kwargs: dict
    ) -> None:
        """First call raises URLError, second succeeds -> 2 total calls, correct response."""
        url_error = urllib.error.URLError("connection refused")
        side_effects = [url_error, _make_response(_OK_BODY)]

        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = side_effects
            result = client.complete(**call_kwargs)

        assert mock_open.call_count == 2
        assert result.content == "hello world"
        assert result.provider == "9router"

    # -----------------------------------------------------------------------
    # 2. test_retry_on_connection_error
    # -----------------------------------------------------------------------

    def test_retry_on_connection_error(
        self, client: RouterLLMClient, call_kwargs: dict
    ) -> None:
        """First call raises ConnectionError, second succeeds -> retry happens."""
        side_effects = [ConnectionError("timeout"), _make_response(_OK_BODY)]

        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = side_effects
            result = client.complete(**call_kwargs)

        assert mock_open.call_count == 2
        assert result.content == "hello world"

    # -----------------------------------------------------------------------
    # 3. test_404_triggers_model_fallback
    # -----------------------------------------------------------------------

    def test_404_triggers_model_fallback(
        self, client: RouterLLMClient, call_kwargs: dict
    ) -> None:
        """First model returns 404 -> code falls back to next model in MODEL_TABLE."""
        not_found = urllib.error.URLError("not found")
        not_found.code = 404  # type: ignore[attr-defined]

        fallback_model = MODEL_TABLE["default"]  # first fallback tier

        # First model (requested) fails 3x with 404, then fallback model succeeds
        side_effects = [
            not_found,
            not_found,
            not_found,  # 3 attempts on requested model
            _make_response({**_OK_BODY, "model": fallback_model}),
        ]

        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = side_effects
            result = client.complete(**call_kwargs)

        assert result.model == fallback_model
        # 3 attempts on original + 1 on fallback = 4
        assert mock_open.call_count == 4

    # -----------------------------------------------------------------------
    # 4. test_all_models_fail
    # -----------------------------------------------------------------------

    def test_all_models_fail(self, client: RouterLLMClient, call_kwargs: dict) -> None:
        """ConnectionError on all attempts for all models -> raises after exhausting retries.

        Non-404 errors retry up to 3 times per model, then fall back to next model.
        With 3 models, that's up to 9 total attempts.
        """
        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = ConnectionError("network down")
            with pytest.raises(ConnectionError, match="network down"):
                client.complete(**call_kwargs)

        # 3 models × 3 retries each = 9 attempts
        assert mock_open.call_count == 9

    # -----------------------------------------------------------------------
    # 5. test_success_no_retry
    # -----------------------------------------------------------------------

    def test_success_no_retry(self, client: RouterLLMClient, call_kwargs: dict) -> None:
        """First call succeeds -> only 1 HTTP call made, no retries."""
        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _make_response(_OK_BODY)
            result = client.complete(**call_kwargs)

        assert mock_open.call_count == 1
        assert result.content == "hello world"
        assert result.model == "cu/claude-4.5-sonnet"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5}

    # -----------------------------------------------------------------------
    # 6. test_exponential_backoff
    # -----------------------------------------------------------------------

    def test_exponential_backoff(
        self, client: RouterLLMClient, call_kwargs: dict
    ) -> None:
        """Verify sleep(1) on attempt 1, sleep(2) on attempt 2 (2**attempt pattern)."""
        side_effects = [
            urllib.error.URLError("err1"),
            urllib.error.URLError("err2"),
            _make_response(_OK_BODY),
        ]

        with (
            patch("aos.llm.urllib.request.urlopen") as mock_open,
            patch("time.sleep") as mock_sleep,
        ):
            mock_open.side_effect = side_effects
            client.complete(**call_kwargs)

        # attempt=0 -> sleep(2**0)=sleep(1), attempt=1 -> sleep(2**1)=sleep(2)
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_calls == [1, 2]


# ---------------------------------------------------------------------------
# 7. test_parse_first_json_from_json_block
# ---------------------------------------------------------------------------


class TestParseFirstJson:
    def test_parse_first_json_from_json_block(self) -> None:
        """Extracts JSON from ```json ... ``` fenced code blocks."""
        raw = (
            "Here is the result:\n"
            "```json\n"
            '{"choices": [{"message": {"content": "parsed"}}]}\n'
            "```\n"
            "Trailing text."
        )
        result = _parse_first_json(raw)
        assert result["choices"][0]["message"]["content"] == "parsed"

    # -----------------------------------------------------------------------
    # 8. test_parse_first_json_from_truncated
    # -----------------------------------------------------------------------

    def test_parse_first_json_from_truncated(self) -> None:
        """Extracts content from a truncated JSON string via regex fallback."""
        raw = (
            '{"model": "test", "choices": [{"message": {"content": "truncated output",'
            ' "role": "assistant"}, "finish_reason": "length"}],'
            ' "usage": {"prompt_tokens": 5'
        )
        result = _parse_first_json(raw)
        assert result["choices"][0]["message"]["content"] == "truncated output"

    # -----------------------------------------------------------------------
    # Additional parsing edge cases
    # -----------------------------------------------------------------------

    def test_parse_raw_json_object(self) -> None:
        """Plain JSON object parsed directly without extraction."""
        raw = json.dumps({"key": "value"})
        result = _parse_first_json(raw)
        assert result == {"key": "value"}

    def test_parse_multiple_json_objects(self) -> None:
        """When multiple JSON objects are concatenated, first complete one is returned."""
        obj1 = {"id": 1, "data": "first"}
        obj2 = {"id": 2, "data": "second"}
        raw = json.dumps(obj1) + json.dumps(obj2)
        result = _parse_first_json(raw)
        assert result == obj1

    def test_parse_braces_fallback(self) -> None:
        """Falls back to finding first complete { ... } when no code block."""
        raw = 'prefix {"a": 1} suffix'
        result = _parse_first_json(raw)
        assert result == {"a": 1}

    def test_parse_raises_on_no_json(self) -> None:
        """Raises ValueError when no JSON can be extracted at all."""
        with pytest.raises(ValueError, match="No complete JSON object found"):
            _parse_first_json("not json at all, just plain text")


# ---------------------------------------------------------------------------
# Edge cases for complete()
# ---------------------------------------------------------------------------


class TestCompleteEdgeCases:
    def test_error_in_body_raises_connection_error(
        self, client: RouterLLMClient, call_kwargs: dict
    ) -> None:
        """Response body contains 'error' key -> raises ConnectionError."""
        error_body = {"error": "rate limit exceeded"}
        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _make_response(error_body)
            with pytest.raises(ConnectionError, match="rate limit exceeded"):
                client.complete(**call_kwargs)

    def test_reasoning_fallback_to_content(
        self, client: RouterLLMClient, call_kwargs: dict
    ) -> None:
        """When content is empty but reasoning exists, reasoning is used as content."""
        body = {
            "model": "test",
            "choices": [{"message": {"content": "", "reasoning": "chain of thought"}}],
            "usage": {},
        }
        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _make_response(body)
            result = client.complete(**call_kwargs)

        assert result.content == "chain of thought"

    def test_api_key_sent_in_header(self, call_kwargs: dict) -> None:
        """When api_key is set, Authorization header is included."""
        client = _make_client(api_key="test-key-123")
        with patch("aos.llm.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _make_response(_OK_BODY)
            client.complete(**call_kwargs)

        # Inspect the Request object passed to urlopen
        req = mock_open.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer test-key-123"
