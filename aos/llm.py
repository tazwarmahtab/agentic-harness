"""LLM client abstraction with model routing and provider fallback.

Routes tasks to the right model based on agent criticality.
Supports three backends (tried in order):
1. 9router (localhost:20128) — model routing via cu/claude-4.5-* IDs
2. Direct Anthropic API — claude-sonnet-4-20250514 / claude-haiku-4-5
3. DryRunLLMClient — mock for testing (no API calls)

Model routing table mirrors CLAUDE.md / 9router config.

Free-tier subagent dispatch:
- CRITICALITY_TO_MODEL maps low/medium criticality agents to the "fast"
tier by default.
- When AOS_FREE_TIER is set in the environment, those agents are
redirected to the "free" tier which rotates across a pool of verified
OpenRouter free models (via 9router) — this avoids rate-limiting on
paid Claude endpoints during parallel fan-out.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time as _time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model routing table — mirrors CLAUDE.md / 9router config
# ---------------------------------------------------------------------------

# NVIDIA NIM model table (used when NvidiaLLMClient is active)
NVIDIA_MODEL_TABLE: dict[str, str] = {
    "default": "nvidia/nemotron-3-ultra-550b-a55b",        # best general-purpose
    "reasoning": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",  # reasoning model
    "fast": "nvidia/nemotron-3-ultra-550b-a55b",           # fast = best
    "subagent": "nvidia/nemotron-3-ultra-550b-a55b",       # subagents = best
    "free": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",  # free pool entry
}

# Primary model table — NVIDIA NIM models (best free tier)
MODEL_TABLE: dict[str, str] = {
    "default": "nvidia/nemotron-3-ultra-550b-a55b",
    "reasoning": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "fast": "nvidia/nemotron-3-ultra-550b-a55b",
    "subagent": "nvidia/nemotron-3-ultra-550b-a55b",
    "free": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
}

# Pool of verified free-tier models — round-robin indexed.
# Ordered by capability: best -> lightest
FREE_MODEL_POOL: list[str] = [
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/mistralai/mistral-medium-3.5-128b",
    "nvidia/google/gemma-4-31b-it",
]

# Direct Anthropic model IDs (fallback when 9router is down)
ANTHROPIC_MODEL_TABLE: dict[str, str] = {
    "default": "claude-sonnet-4-20250514",
    "reasoning": "claude-opus-4-20250514",
    "fast": "claude-haiku-4-5-20251001",
    "subagent": "claude-haiku-4-5-20251001",
    "free": "claude-sonnet-4-20250514",  # best available on direct Anthropic fallback
}

# Agent criticality → model tier mapping.
# Core orchestrators (dispatcher, planner) stay on "default" paid Sonnet.
CRITICALITY_TO_MODEL: dict[str, str] = {
    "critical": "default",  # dispatcher, planner — paid Sonnet
    "high": "default",  # COO, CFO, Chief of Staff — paid Sonnet
    "medium": "free",  # routine specialists — free tier round-robin
    "low": "free",  # lightweight tasks — free tier round-robin
}

# Round-robin counter (thread-safe via lock)
_free_model_lock = threading.Lock()
_free_model_idx = 0

# Free-tier env var: AOS_FREE_TIER is the canonical name.
# TAZOS_FREE_TIER (deprecated) is accepted as a fallback for backward compat.
AOS_FREE_TIER = os.getenv("AOS_FREE_TIER") or os.getenv("TAZOS_FREE_TIER")


# ---------------------------------------------------------------------------
# Free-tier model health tracking
# ---------------------------------------------------------------------------


@dataclass
class FreeModelHealth:
    """Health metrics for a free-tier model."""

    model: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: int = 0
    last_used: float = 0.0
    consecutive_failures: int = 0

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def record_success(self, latency_ms: int) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_ms += latency_ms
        self.consecutive_failures = 0
        self.last_used = _time.time()

    def record_failure(self) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_used = _time.time()

    def is_healthy(
        self, max_error_rate: float = 0.5, max_consecutive_failures: int = 5
    ) -> bool:
        """Check if model is healthy enough to use."""
        if self.total_requests < 3:
            return True  # Not enough data to judge
        if self.error_rate > max_error_rate:
            return False
        if self.consecutive_failures >= max_consecutive_failures:
            return False
        return True


# Global health registry
_free_model_health: dict[str, FreeModelHealth] = {
    model: FreeModelHealth(model=model) for model in FREE_MODEL_POOL
}


def record_free_model_result(model: str, success: bool, latency_ms: int = 0) -> None:
    """Record the result of a free-tier model call."""
    if model in _free_model_health:
        if success:
            _free_model_health[model].record_success(latency_ms)
        else:
            _free_model_health[model].record_failure()


def get_healthy_free_models(
    max_error_rate: float = 0.5,
    max_consecutive_failures: int = 5,
) -> list[str]:
    """Get list of healthy free-tier models, preserving round-robin order."""
    return [
        model
        for model in FREE_MODEL_POOL
        if _free_model_health[model].is_healthy(
            max_error_rate, max_consecutive_failures
        )
    ]


def _next_free_model() -> str:
    """Return the next healthy model from FREE_MODEL_POOL, cycling round-robin."""
    global _free_model_idx
    healthy = get_healthy_free_models()
    if not healthy:
        # Fallback to all models if none are healthy (last resort)
        healthy = FREE_MODEL_POOL
    with _free_model_lock:
        model = healthy[_free_model_idx % len(healthy)]
        _free_model_idx += 1
        return model


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

    Verifies:
    (1) server responds with model metadata
    (2) has >0 proxy pools in db.json with valid auth
    """
    # Check server is up
    try:
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

    Reads config from environment variables:
    ANTHROPIC_BASE_URL → base URL (required for router mode)
    ANTHROPIC_AUTH_TOKEN → Bearer token
    AOS_LLM_API_KEY → alternative auth token
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 300,
    ):
        self.base_url = (
            base_url
            or os.getenv("ANTHROPIC_BASE_URL", "")
            or os.getenv("AOS_LLM_BASE_URL", "")
        )
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]

        self.api_key = (
            api_key
            or os.getenv("ANTHROPIC_AUTH_TOKEN", "")
            or os.getenv("AOS_LLM_API_KEY", "")
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

        import time as _time

        last_error = None
        models_to_try = [model]

        # If the requested model fails, fall back through the routing table
        for fallback_tier in ["default", "fast", "free"]:
            fallback = MODEL_TABLE.get(fallback_tier, "")
            if fallback and fallback not in models_to_try:
                models_to_try.append(fallback)

        for current_model in models_to_try:
            current_payload = {**payload, "model": current_model}
            current_data = json.dumps(current_payload).encode("utf-8")

            for attempt in range(3):
                start_time = _time.perf_counter()
                try:
                    retry_req = urllib.request.Request(
                        url, data=current_data, headers=headers, method="POST"
                    )
                    with urllib.request.urlopen(
                        retry_req, timeout=self.timeout
                    ) as resp:
                        raw = resp.read().decode("utf-8")
                        body = _parse_first_json(raw)

                        if "error" in body:
                            raise ConnectionError(f"9router error: {body['error']}")

                        choice = body["choices"][0]
                        msg = choice.get("message", {})
                        content = msg.get("content") or ""
                        if not content and msg.get("reasoning"):
                            content = msg["reasoning"]

                        latency_ms = int((_time.perf_counter() - start_time) * 1000)
                        # Record health for free-tier models
                        if current_model in FREE_MODEL_POOL:
                            record_free_model_result(current_model, True, latency_ms)

                        return LLMResponse(
                            content=content,
                            model=body.get("model", current_model),
                            usage=body.get("usage", {}),
                            provider="9router",
                        )
                except (urllib.error.URLError, ConnectionError) as e:
                    latency_ms = int((_time.perf_counter() - start_time) * 1000)
                    last_error = e
                    if attempt < 2:
                        _time.sleep(2**attempt)
                        continue
                    # 404 means model not found — try next model
                    if hasattr(e, "code") and e.code == 404:
                        # Record failure for free-tier models
                        if current_model in FREE_MODEL_POOL:
                            record_free_model_result(current_model, False, latency_ms)
                        break
                    raise

        # Record final failure if all attempts failed and it's a free-tier model
        if model in FREE_MODEL_POOL:
            record_free_model_result(model, False, 0)
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
            anthropic_model = ANTHROPIC_MODEL_TABLE.get(
                tier, "claude-sonnet-4-20250514"
            )

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
        req = urllib.request.Request(
            self.API_URL, data=data, headers=headers, method="POST"
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content_parts = body.get("content", [])
            text = "".join(
                p.get("text", "") for p in content_parts if p.get("type") == "text"
            )
            return LLMResponse(
                content=text,
                model=body.get("model", anthropic_model),
                usage=body.get("usage", {}),
                provider="anthropic",
            )


# ---------------------------------------------------------------------------
# NVIDIA NIM client (direct to integrate.api.nvidia.com)
# ---------------------------------------------------------------------------


class NvidiaLLMClient:
    """Direct NVIDIA NIM API client (OpenAI-compatible endpoint).

    Used for NVIDIA-hosted models (stepfun/step-* and other nvidia/* IDs)
    when 9router is not configured as a pass-through proxy.
    Reads NIM key from NVIDIA_NIM_API_KEY env var.
    """

    API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

    def __init__(self, api_key: str | None = None, timeout: int = 300):
        self.api_key = api_key or os.getenv("NVIDIA_NIM_API_KEY", "")
        if not self.api_key:
            raise ValueError("No NVIDIA NIM key found. Set NVIDIA_NIM_API_KEY.")
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
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL, data=data, headers=headers, method="POST"
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw)

            if "error" in body:
                raise ConnectionError(f"NVIDIA NIM error: {body['error']}")

            choice = body["choices"][0]
            msg = choice.get("message", {})
            content = msg.get("content", "")
            return LLMResponse(
                content=content,
                model=body.get("model", model),
                usage=body.get("usage", {}),
                provider="nvidia-nim",
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
    3. Auto-detect: try 9router (with fallback), then Anthropic, then dry run
    4. dry_run=True → DryRunLLMClient
    """
    if dry_run:
        return DryRunLLMClient()

    if prefer == "router":
        return RouterLLMClient()
    if prefer == "anthropic":
        return AnthropicLLMClient()

    # Auto-detect: check NVIDIA NIM first (if key available), then 9router, then Anthropic, then dry run
    router_base = os.getenv("AOS_LLM_BASE_URL", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    has_auth_token = bool(os.getenv("ANTHROPIC_AUTH_TOKEN", ""))
    has_nvidia_key = bool(os.getenv("NVIDIA_NIM_API_KEY", ""))

    # NVIDIA NIM direct API — best rate limits for NVIDIA models
    if has_nvidia_key:
        try:
            if verbose:
                logger.info("Using NVIDIA NIM direct API")
            return NvidiaLLMClient()
        except ValueError:
            pass  # fall through

    # 9router is usable only if it has configured backend providers
    if has_auth_token and _is_9router_usable(router_base):
        if verbose:
            logger.info(f"Using local router backend: {router_base}")
        return RouterLLMClient()

    # Fall back to direct Anthropic API
    if anthropic_key:
        if verbose:
            logger.info("Using Anthropic API directly")
        return AnthropicLLMClient()

    # Last resort: Anthropic with auth token (for 9router-integrated setups)
    if has_auth_token:
        if verbose:
            logger.info("Using Anthropic via auth token")
        return AnthropicLLMClient()

    if verbose:
        logger.warning("No LLM backend available — falling back to dry run")
    return DryRunLLMClient()


def validate_free_tier_pool() -> dict[str, bool]:
    """Validate free-tier model pool at startup by checking 9router /v1/models.

    Returns a dict mapping model -> healthy status.
    """
    import urllib.request
    import json

    base = os.getenv("AOS_LLM_BASE_URL", "")
    if not base:
        return {}

    if base.endswith("/v1"):
        base = base[:-3]

    try:
        url = f"{base}/v1/models"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        available = {m["id"] for m in body.get("data", [])}
        result = {}
        for model in FREE_MODEL_POOL:
            result[model] = model in available
        return result
    except Exception:
        # On any error, return empty (caller handles gracefully)
        return {}


def ensure_healthy_free_tier_pool(min_healthy: int = 2) -> bool:
    """Ensure free-tier pool has at least min_healthy models available.

    Returns True if pool is healthy, False otherwise.
    """
    health = validate_free_tier_pool()
    if not health:
        return True  # Can't validate, assume OK (e.g., no router URL configured)

    healthy_count = sum(1 for ok in health.values() if ok)
    return healthy_count >= min_healthy


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


def resolve_model(
    agent_criticality: str,
    override: str | None = None,
    use_anthropic_ids: bool = False,
) -> str:
    """Resolve model ID from agent criticality or explicit override.

    In free-tier mode (AOS_FREE_TIER=1), medium and low criticality
    agents are routed across the FREE_MODEL_POOL round-robin to spread
    load and avoid per-endpoint rate limits during parallel fan-out.
    """
    if override:
        return override

    tier = CRITICALITY_TO_MODEL.get(agent_criticality, "default")
    table = ANTHROPIC_MODEL_TABLE if use_anthropic_ids else MODEL_TABLE
    model_id = table[tier]

    # Free-tier is the default for subagents.
    # Opt out with AOS_PAID_TIER=1.
    if tier == "free" or (tier == "fast" and os.getenv("AOS_PAID_TIER") != "1"):
        return _next_free_model()

    return model_id
