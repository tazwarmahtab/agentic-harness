"""LLM client abstraction with model routing and provider fallback.

Routes tasks to the right model based on agent criticality.
Supports three backends (tried in order):
  1. 9router (localhost:20128) — model routing via cu/claude-4.5-* IDs
  2. Direct Anthropic API — claude-sonnet-4-20250514 / claude-haiku-4-5
  3. DryRunLLMClient — mock for testing (no API calls)

Model routing table mirrors CLAUDE.md / 9router config.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Model routing table — mirrors CLAUDE.md / 9router config
#
# Default models can be overridden via env vars (Claude Code convention):
#   ANTHROPIC_DEFAULT_SONNET_MODEL, _HAIKU_MODEL, _OPUS_MODEL
# ---------------------------------------------------------------------------
MODEL_TABLE: dict[str, str] = {
    "default": "cu/claude-4.5-sonnet",      # paid Claude Sonnet — general tasks
    "reasoning": "cu/claude-4.5-opus-high-thinking",  # paid Claude Opus — complex reasoning
    "fast": "cu/claude-4.5-haiku",          # paid Claude Haiku — code/structured
    "subagent": "cu/claude-4.5-haiku",      # paid Claude Haiku — lightweight agents
}

# Direct Anthropic model IDs (fallback when 9router is down)
ANTHROPIC_MODEL_TABLE: dict[str, str] = {
    "default": "claude-sonnet-4-20250514",
    "reasoning": "claude-opus-4-20250514",
    "fast": "claude-haiku-4-5-20251001",
    "subagent": "claude-haiku-4-5-20251001",
}

# Agent criticality → model tier mapping
CRITICALITY_TO_MODEL: dict[str, str] = {
    "critical": "default",    # sonnet — dispatcher, planner
    "high": "default",        # sonnet — COO, CFO, Chief of Staff
    "medium": "fast",         # haiku — routine specialists
    "low": "fast",            # haiku — lightweight tasks
}


# ---------------------------------------------------------------------------
# Response type
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """Parsed LLM response."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    provider: str = "unknown"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

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
    ) -> LLMResponse:
        """Send a completion request and return the response."""
        ...


# ---------------------------------------------------------------------------
# Auto-detection helpers
# ---------------------------------------------------------------------------

def _detect_9router_key() -> str:
    """Auto-detect 9router API key from auth config."""
    key_path = Path.home() / ".9router" / "auth" / "cli-secret"
    if key_path.exists():
        try:
            return key_path.read_text().strip()
        except Exception:
            pass
    return ""


def _is_9router_usable(base_url: str, timeout: int = 3) -> bool:
    """Check if 9router is running AND has usable provider backends.

    A running 9router with no configured providers (proxy pools, provider
    nodes) will return model metadata but can't actually route requests.
    We check: (1) server responds, (2) has >0 proxy pools in db.json.
    """
    try:
        # Check server is up
        req = urllib.request.Request(f"{base_url}/v1/models")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
            models = body.get("data", [])
            if not models:
                return False
    except Exception:
        return False

    # Check db.json for configured proxy pools (the actual backends)
    try:
        db_path = Path.home() / ".9router" / "db.json"
        if db_path.exists():
            db = json.loads(db_path.read_text())
            pools = db.get("proxyPools", [])
            if not pools:
                return False
            # Verify pools have valid auth
            for pool in pools:
                if pool.get("status") == "disabled":
                    continue
                if pool.get("api_key") or pool.get("auth_token"):
                    return True
            return False
        return False
    except Exception:
        return False


def _parse_first_json(raw: str) -> dict:
    """Parse the first complete JSON object from a string.

    Handles streaming responses where multiple JSON objects may be
    concatenated, or responses that are truncated (no closing brace).
    Returns the first complete object as a dict.
    """
    # Try raw parse first
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting from ```json ... ``` blocks
    import re
    code_blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    for block in code_blocks:
        try:
            result = json.loads(block.strip())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            continue

    # Try finding first { ... } that looks like a complete object
    depth = 0
    start_idx = -1
    for i, c in enumerate(raw):
        if c == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start_idx >= 0:
                try:
                    result = json.loads(raw[start_idx : i + 1])
                    if isinstance(result, dict):
                        return result
                except (json.JSONDecodeError, ValueError):
                    start_idx = -1

    # Fallback: if response looks like OpenAI format but was truncated,
    # try to extract the content field directly
    content_match = re.search(r'"content"\s*:\s*"(.*?)(?:"\s*[,}])', raw, re.DOTALL)
    if content_match:
        content = content_match.group(1)
        # Unescape JSON string escapes
        content = content.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
        return {"choices": [{"message": {"content": content}}]}

    raise ValueError(f"No complete JSON object found in response: {raw[:200]}")


def _detect_anthropic_key() -> str:
    """Auto-detect Anthropic API key from environment.

    Checks ANTHROPIC_API_KEY first, then ANTHROPIC_AUTH_TOKEN
    (used by Claude Code / 9router integration).
    """
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        return key
    return os.getenv("ANTHROPIC_AUTH_TOKEN", "")


# ---------------------------------------------------------------------------
# 9router client (OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------

class RouterLLMClient:
    """LLM client that talks to 9router / OpenAI-compatible endpoint.

    Reads config from environment variables set by Claude Code / ECC:
      ANTHROPIC_BASE_URL → base URL (default http://localhost:20128/v1)
      ANTHROPIC_AUTH_TOKEN → Bearer token
      ANTHROPIC_DEFAULT_SONNET_MODEL / _HAIKU / _OPUS → model overrides
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 300,
    ):
        # Prefer ANTHROPIC_BASE_URL (Claude Code convention)
        self.base_url = (
            base_url
            or os.getenv("ANTHROPIC_BASE_URL", "")
            or os.getenv("TAZOS_LLM_BASE_URL", "http://localhost:20128")
        )
        # Strip trailing /v1 if present — we append /v1/chat/completions
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]

        self.api_key = (
            api_key
            or os.getenv("ANTHROPIC_AUTH_TOKEN", "")
            or os.getenv("TAZOS_LLM_API_KEY", "")
            or _detect_9router_key()
        )
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
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        import time as _time
        last_error = None
        models_to_try = [model]
        # If the requested model fails, fall back through the routing table
        # Skip reasoning models for structured output reliability
        for fallback_tier in ["default", "fast"]:
            fallback = MODEL_TABLE.get(fallback_tier, "")
            if fallback and fallback not in models_to_try:
                models_to_try.append(fallback)

        for current_model in models_to_try:
            # Rebuild payload with current model
            current_payload = {**payload, "model": current_model}
            current_data = json.dumps(current_payload).encode("utf-8")

            for attempt in range(3):
                try:
                    retry_req = urllib.request.Request(url, data=current_data, headers=headers, method="POST")
                    with urllib.request.urlopen(retry_req, timeout=self.timeout) as resp:
                        raw = resp.read().decode("utf-8")
                        body = _parse_first_json(raw)

                        if "error" in body:
                            raise ConnectionError(f"9router error: {body['error']}")

                        choice = body["choices"][0]
                        msg = choice.get("message", {})
                        content = msg.get("content") or ""
                        if not content and msg.get("reasoning"):
                            content = msg["reasoning"]
                        return LLMResponse(
                            content=content,
                            model=body.get("model", current_model),
                            usage=body.get("usage", {}),
                            provider="9router",
                        )
                except (urllib.error.URLError, ConnectionError) as e:
                    last_error = e
                    if attempt < 2:
                        _time.sleep(2 ** attempt)
                        continue
                    # 404 means model not found — try next model
                    if hasattr(e, 'code') and e.code == 404:
                        break
                    raise

        raise last_error or ConnectionError("All model attempts failed")


# ---------------------------------------------------------------------------
# Direct Anthropic client (Messages API)
# ---------------------------------------------------------------------------

class AnthropicLLMClient:
    """Direct Anthropic API client (Messages API)."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str | None = None, timeout: int = 300):
        self.api_key = api_key or _detect_anthropic_key()
        if not self.api_key:
            raise ValueError("No Anthropic API key found. Set ANTHROPIC_API_KEY.")
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
        # Map 9router model IDs to Anthropic model IDs
        anthropic_model = model
        if model.startswith("cu/"):
            tier = "default"
            for t, m in MODEL_TABLE.items():
                if m == model:
                    tier = t
                    break
            anthropic_model = ANTHROPIC_MODEL_TABLE.get(tier, "claude-sonnet-4-20250514")

        payload = {
            "model": anthropic_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.API_URL, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content_parts = body.get("content", [])
            text = "".join(p.get("text", "") for p in content_parts if p.get("type") == "text")
            return LLMResponse(
                content=text,
                model=body.get("model", anthropic_model),
                usage=body.get("usage", {}),
                provider="anthropic",
            )


# ---------------------------------------------------------------------------
# Dry run client (no API calls)
# ---------------------------------------------------------------------------

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
            provider="dry_run",
        )


# ---------------------------------------------------------------------------
# Client factory — auto-detects best available backend
# ---------------------------------------------------------------------------

def create_llm_client(
    *,
    prefer: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> LLMClient:
    """Create the best available LLM client.

    Priority:
      1. prefer="router" → RouterLLMClient
      2. prefer="anthropic" → AnthropicLLMClient
      3. Auto-detect: try 9router, fall back to Anthropic, then dry run
      4. dry_run=True → DryRunLLMClient
    """
    if dry_run:
        return DryRunLLMClient()

    if prefer == "router":
        return RouterLLMClient()
    if prefer == "anthropic":
        return AnthropicLLMClient()

    # Auto-detect: prefer 9router/OpenAI-compat, then direct Anthropic, then dry run
    anthropic_base = os.getenv("ANTHROPIC_BASE_URL", "")
    has_auth_token = bool(os.getenv("ANTHROPIC_AUTH_TOKEN", ""))

    # If ANTHROPIC_BASE_URL points to a local proxy (9router), use router client
    if anthropic_base and ("127.0.0.1" in anthropic_base or "localhost" in anthropic_base or "20128" in anthropic_base):
        if has_auth_token:
            if verbose:
                print(f"[llm] Using 9router backend ({anthropic_base})")
            return RouterLLMClient()

    # Check 9router directly
    router_base = os.getenv("TAZOS_LLM_BASE_URL", "http://localhost:20128")
    if _is_9router_usable(router_base):
        if verbose:
            print("[llm] Using 9router backend")
        return RouterLLMClient()

    # Fall back to direct Anthropic API (needs real api.anthropic.com key)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        if verbose:
            print("[llm] Using Anthropic API directly")
        return AnthropicLLMClient()

    if verbose:
        print("[llm] No LLM backend available — falling back to dry run")
    return DryRunLLMClient()


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

def resolve_model(
    agent_criticality: str,
    override: str | None = None,
    use_anthropic_ids: bool = False,
) -> str:
    """Resolve model ID from agent criticality or explicit override."""
    if override:
        return override
    tier = CRITICALITY_TO_MODEL.get(agent_criticality, "default")
    table = ANTHROPIC_MODEL_TABLE if use_anthropic_ids else MODEL_TABLE
    return table[tier]
