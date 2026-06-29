"""LLM client abstraction with model routing.

Routes tasks to the right model based on agent criticality and
the model routing config in CLAUDE.md (9router at localhost:20128).

Default: cu/claude-4.5-sonnet
Complex reasoning: cu/claude-4.5-opus-high-thinking
Fast/simple: cu/claude-4.5-haiku
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Model routing table — mirrors CLAUDE.md / 9router config
# ---------------------------------------------------------------------------
MODEL_TABLE: dict[str, str] = {
    "default": "cu/claude-4.5-sonnet",
    "reasoning": "cu/claude-4.5-opus-high-thinking",
    "fast": "cu/claude-4.5-haiku",
    "subagent": "cu/claude-4.5-haiku",
}

# Agent criticality → model tier mapping
CRITICALITY_TO_MODEL: dict[str, str] = {
    "critical": "default",
    "high": "default",
    "medium": "default",
    "low": "fast",
}


class LLMClient(Protocol):
    """Protocol for LLM backends."""

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Send a completion request and return the assistant message."""
        ...


@dataclass
class LLMResponse:
    """Parsed LLM response."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class HTTPLLMClient:
    """LLM client that talks to 9router or any OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 120,
    ):
        self.base_url = base_url or os.getenv("TAZOS_LLM_BASE_URL", "http://localhost:20128")
        self.api_key = api_key or os.getenv("TAZOS_LLM_API_KEY", "")
        self.timeout = timeout

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Send completion request to 9router / OpenAI-compatible endpoint."""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choice = body["choices"][0]
                return LLMResponse(
                    content=choice["message"]["content"],
                    model=body.get("model", model),
                    usage=body.get("usage", {}),
                )
        except urllib.error.URLError as e:
            raise ConnectionError(f"LLM request failed: {e}") from e


class DryRunLLMClient:
    """Mock client for testing — returns a placeholder response."""

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> LLMResponse:
        user_msg = messages[-1]["content"] if messages else "(no input)"
        return LLMResponse(
            content=f"[DRY RUN] Agent received: {user_msg[:200]}",
            model=model,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
        )


def resolve_model(
    agent_criticality: str,
    override: str | None = None,
) -> str:
    """Resolve model ID from agent criticality or explicit override."""
    if override:
        return override
    tier = CRITICALITY_TO_MODEL.get(agent_criticality, "default")
    return MODEL_TABLE[tier]
