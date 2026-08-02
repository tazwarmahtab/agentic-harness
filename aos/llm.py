"""LLM client abstraction with model routing and provider fallback.

Routes tasks to the right model based on agent criticality.
Supports multiple backends (tried in order):
1. NVIDIA NIM direct API — nvidia/* models (if NVIDIA_NIM_API_KEY set)
2. Bytez direct API — meta-llama/* models (if BYTEZ_API_KEY set)
3. 9router (localhost:20128) — model routing via cu/claude-4.5-* IDs
4. Direct Anthropic API — claude-sonnet-4-20250514 / claude-haiku-4-5
5. DryRunLLMClient — mock for testing (no API calls)

Model routing table mirrors CLAUDE.md / 9router config.

Free-tier subagent dispatch:
- CRITICALITY_TO_MODEL maps low/medium criticality agents to the "fast"
  tier by default.
- When AOS_FREE_TIER is set in the environment, those agents are
  redirected to the "free" tier which rotates across a pool of verified
  free models (via 9router) — this avoids rate-limiting on
  paid Claude endpoints during parallel fan-out.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time as _time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models for routing manifest
# ---------------------------------------------------------------------------

from pydantic import BaseModel, ValidationError
import networkx as nx

class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration for a model."""
    failure_threshold: int
    recovery_window_sec: int


class VentureRoutingManifest(BaseModel):
    """Routing manifest for a venture, defining allowed model transitions, criticality mappings, and fallback paths."""
    version: str
    venture: str
    dag: List[Tuple[str, str]]
    criticality_map: Dict[str, str]
    fallback_path: List[str]
    shadow: bool = False
    circuit_breaker: Dict[str, CircuitBreakerConfig] = {}


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

# Bytez model table (used when BytezLLMClient is active)
BYTEZ_MODEL_TABLE: dict[str, str] = {
    "default": "meta-llama/Meta-Llama-3.1-405B-Instruct",
    "reasoning": "meta-llama/Meta-Llama-3.1-405B-Instruct",
    "fast": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "subagent": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "free": "meta-llama/Meta-Llama-3.1-8B-Instruct",
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

AOS_FREE_TIER = os.getenv("AOS_FREE_TIER")


def validate_manifest(manifest: VentureRoutingManifest) -> None:
    """Validate routing manifest DAG and fallback path."""
    graph = nx.DiGraph()
    graph.add_edges_from(manifest.dag)

    # Check for cycles
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError(f"Manifest DAG for {manifest.venture} contains cycles")

    # Check fallback path is a Hamiltonian path
    if not nx.is_simple_path(graph, manifest.fallback_path):
        raise ValueError(f"Fallback path for {manifest.venture} is not a valid path in DAG")

    # Check all criticality levels are mapped
    for criticality in ["critical", "high", "medium", "low"]:
        if criticality not in manifest.criticality_map:
            raise ValueError(f"Missing criticality mapping for {criticality} in {manifest.venture}")

    # Check all models in criticality_map exist in DAG
    all_models = set(graph.nodes())
    for model in manifest.criticality_map.values():
        if model not in all_models:
            raise ValueError(f"Model {model} in criticality_map not found in DAG for {manifest.venture}")


def load_manifest(venture: str) -> VentureRoutingManifest:
    """Load and validate routing manifest for a venture."""
    manifest_path = Path(f"aos/ventures/{venture}/routing.manifest.json")
    if not manifest_path.exists():
        raise FileNotFoundError(f"No routing manifest found for venture {venture}")

    try:
        manifest_data = json.loads(manifest_path.read_text())
        manifest = VentureRoutingManifest(**manifest_data)
        validate_manifest(manifest)
        return manifest
    except (ValidationError, ValueError) as e:
        raise ValueError(f"Invalid manifest for {venture}: {str(e)}")

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


class CircuitBreaker:
    """Circuit breaker for LLM clients."""

    def __init__(self, failure_threshold: int = 5, recovery_window_sec: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_window_sec = recovery_window_sec
        self.failure_count = 0
        self.last_failure_time = 0
        self.lock = threading.Lock()

    def is_open(self) -> bool:
        """Check if circuit breaker is open (tripped)."""
        with self.lock:
            if self.failure_count < self.failure_threshold:
                return False

            # Check if recovery window has passed
            if time.time() - self.last_failure_time > self.recovery_window_sec:
                self.failure_count = 0  # Reset on recovery
                return False

            return True

    def record_failure(self) -> None:
        """Record a failure and trip circuit if threshold exceeded."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

    def record_success(self) -> None:
        """Record a success and reset failure count."""
        with self.lock:
            self.failure_count = 0


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
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def _get_circuit_breaker(self, model: str, venture: str) -> CircuitBreaker:
        """Get circuit breaker for a model, configured from venture manifest."""
        key = f"{venture}:{model}"
        if key not in self.circuit_breakers:
            try:
                manifest = load_manifest(venture)
                config = manifest.circuit_breaker.get(model)
                if config:
                    self.circuit_breakers[key] = CircuitBreaker(
                        failure_threshold=config.failure_threshold,
                        recovery_window_sec=config.recovery_window_sec,
                    )
                else:
                    # Default circuit breaker settings
                    self.circuit_breakers[key] = CircuitBreaker()
            except FileNotFoundError:
                # No manifest — use default circuit breaker
                self.circuit_breakers[key] = CircuitBreaker()

        return self.circuit_breakers[key]

    def _get_venture_from_context(self, messages: list[dict[str, str]]) -> str:
        """Extract venture from messages context."""
        # Look for venture in system message or first user message
        for msg in messages:
            if msg.get("role") == "system" and "venture:" in msg.get("content", "").lower():
                return msg["content"].lower().split("venture:")[1].strip().split()[0]
            if msg.get("role") == "user" and "venture:" in msg.get("content", "").lower():
                return msg["content"].lower().split("venture:")[1].strip().split()[0]

        # Default to netso if not found
        return "netso"

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

        venture = self._get_venture_from_context(messages)
        last_error = None
        models_to_try = [model]

        # If the requested model fails, fall back through the routing table
        for fallback_tier in ["default", "fast", "free"]:
            fallback = MODEL_TABLE.get(fallback_tier, "")
            if fallback and fallback not in models_to_try:
                models_to_try.append(fallback)

        for current_model in models_to_try:
            # Check circuit breaker
            circuit_breaker = self._get_circuit_breaker(current_model, venture)
            if circuit_breaker.is_open():
                logger.warning(f"Circuit breaker open for {current_model} in {venture}, skipping")
                continue

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
                            circuit_breaker.record_failure()
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
                    circuit_breaker.record_failure()
                    if attempt < 2:
                        time.sleep(2**attempt)
                        continue
                    # 404 means model not found — try next model
                    if hasattr(e, "code") and e.code == 404:
                        # Record failure for free-tier models
                        if current_model in FREE_MODEL_POOL:
                            record_free_model_result(current_model, False, latency_ms)
                        break
                    # For other errors, continue to next model
                    break

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
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def _get_circuit_breaker(self, model: str, venture: str) -> CircuitBreaker:
        """Get circuit breaker for a model, configured from venture manifest."""
        key = f"{venture}:{model}"
        if key not in self.circuit_breakers:
            try:
                manifest = load_manifest(venture)
                config = manifest.circuit_breaker.get(model)
                if config:
                    self.circuit_breakers[key] = CircuitBreaker(
                        failure_threshold=config.failure_threshold,
                        recovery_window_sec=config.recovery_window_sec,
                    )
                else:
                    # Default circuit breaker settings
                    self.circuit_breakers[key] = CircuitBreaker()
            except FileNotFoundError:
                # No manifest — use default circuit breaker
                self.circuit_breakers[key] = CircuitBreaker()

        return self.circuit_breakers[key]

    def _get_venture_from_context(self, messages: list[dict[str, str]]) -> str:
        """Extract venture from messages context."""
        # Look for venture in system message or first user message
        for msg in messages:
            if msg.get("role") == "system" and "venture:" in msg.get("content", "").lower():
                return msg["content"].lower().split("venture:")[1].strip().split()[0]
            if msg.get("role") == "user" and "venture:" in msg.get("content", "").lower():
                return msg["content"].lower().split("venture:")[1].strip().split()[0]

        # Default to netso if not found
        return "netso"

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
            anthropic_model = model[3:]  # strip "cu/" prefix
        elif model.startswith("nvidia/"):
            # NVIDIA models not supported on direct Anthropic API
            raise ValueError(f"Model {model} not supported on direct Anthropic API")

        venture = self._get_venture_from_context(messages)
        circuit_breaker = self._get_circuit_breaker(model, venture)

        # Check circuit breaker
        if circuit_breaker.is_open():
            raise ConnectionError(f"Circuit breaker open for {model} in {venture}")

        payload = {
            "model": anthropic_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw)

        if "error" in body:
            raise ConnectionError(f"Anthropic error: {body['error']}")

        content = ""
        for block in body.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return LLMResponse(
            content=content,
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
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def _get_circuit_breaker(self, model: str, venture: str) -> CircuitBreaker:
        """Get circuit breaker for a model, configured from venture manifest."""
        key = f"{venture}:{model}"
        if key not in self.circuit_breakers:
            try:
                manifest = load_manifest(venture)
                config = manifest.circuit_breaker.get(model)
                if config:
                    self.circuit_breakers[key] = CircuitBreaker(
                        failure_threshold=config.failure_threshold,
                        recovery_window_sec=config.recovery_window_sec,
                    )
                else:
                    # Default circuit breaker settings
                    self.circuit_breakers[key] = CircuitBreaker()
            except FileNotFoundError:
                # No manifest — use default circuit breaker
                self.circuit_breakers[key] = CircuitBreaker()

        return self.circuit_breakers[key]

    def _get_venture_from_context(self, messages: list[dict[str, str]]) -> str:
        """Extract venture from messages context."""
        # Look for venture in system message or first user message
        for msg in messages:
            if msg.get("role") == "system" and "venture:" in msg.get("content", "").lower():
                return msg["content"].lower().split("venture:")[1].strip().split()[0]
            if msg.get("role") == "user" and "venture:" in msg.get("content", "").lower():
                return msg["content"].lower().split("venture:")[1].strip().split()[0]

        # Default to netso if not found
        return "netso"

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

        venture = self._get_venture_from_context(messages)
        circuit_breaker = self._get_circuit_breaker(model, venture)

        # Check circuit breaker
        if circuit_breaker.is_open():
            raise ConnectionError(f"Circuit breaker open for {model} in {venture}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL, data=data, headers=headers, method="POST"
        )

        try:
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
# Bytez client (direct to Bytez API)
# ---------------------------------------------------------------------------


class BytezLLMClient:
    """Direct Bytez API client (OpenAI-compatible endpoint).

    Used for Bytez-hosted models (meta-llama/* and other Bytez-supported IDs).
    Reads key from BYTEZ_API_KEY env var.
    """

    API_URL = "https://api.bytez.io/v1/chat/completions"

    def __init__(self, api_key: str | None = None, timeout: int = 300):
        self.api_key = api_key or os.getenv("BYTEZ_API_KEY", "")
        if not self.api_key:
            raise ValueError("No Bytez API key found. Set BYTEZ_API_KEY.")
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
            raise ConnectionError(f"Bytez error: {body['error']}")

        choice = body["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content", "")
        return LLMResponse(
            content=content,
            model=body.get("model", model),
            usage=body.get("usage", {}),
            provider="bytez",
        )
>>>>>>> 337e7e2 (feat: add Bytez and NVIDIA NIM backends to LLM client)


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
    1. dry_run=True → DryRunLLMClient
    2. prefer="router" → RouterLLMClient
    3. prefer="anthropic" → AnthropicLLMClient
    4. prefer="nvidia" → NvidiaLLMClient
    5. prefer="bytez" → BytezLLMClient
    6. Auto-detect: try NVIDIA NIM → Bytez → 9router → Anthropic → dry run
    """
    if dry_run:
        return DryRunLLMClient()

    if prefer == "router":
        return RouterLLMClient()
    if prefer == "anthropic":
        return AnthropicLLMClient()
    if prefer == "bytez":
        return BytezLLMClient()
    if prefer == "nvidia":
        return NvidiaLLMClient()

    # Auto-detect: check NVIDIA NIM first (if key available), then Bytez, then 9router, then Anthropic, then dry run
    router_base = os.getenv("AOS_LLM_BASE_URL", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    has_auth_token = bool(os.getenv("ANTHROPIC_AUTH_TOKEN", ""))
    has_nvidia_key = bool(os.getenv("NVIDIA_NIM_API_KEY", ""))
    has_bytez_key = bool(os.getenv("BYTEZ_API_KEY", ""))

    # NVIDIA NIM direct API — best rate limits for NVIDIA models
    if has_nvidia_key:
        try:
            if verbose:
                logger.info("Using NVIDIA NIM direct API")
            return NvidiaLLMClient()
        except ValueError:
            pass  # fall through

    # Bytez direct API
    if has_bytez_key:
        try:
            if verbose:
                logger.info("Using Bytez direct API")
            return BytezLLMClient()
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
    venture: str,
    override: str | None = None,
    use_anthropic_ids: bool = False,
) -> str:
    """Resolve model ID from agent criticality, venture manifest, and override.

    In free-tier mode (AOS_FREE_TIER=1), medium and low criticality
    agents are routed across the FREE_MODEL_POOL round-robin to spread
    load and avoid per-endpoint rate limits during parallel fan-out.

    Uses venture-specific routing manifest if available, falling back
    to the global CRITICALITY_TO_MODEL table.
    """
    if override:
        return override

    # Load venture-specific manifest if available
    try:
        manifest = load_manifest(venture)
        tier = manifest.criticality_map.get(agent_criticality, "default")
        graph = nx.DiGraph()
        graph.add_edges_from(manifest.dag)
        if tier not in graph.nodes():
            raise ValueError(f"Model tier {tier} not found in DAG for venture {venture}")
    except FileNotFoundError:
        # No manifest — fall back to global mapping
        tier = CRITICALITY_TO_MODEL.get(agent_criticality, "default")

    table = ANTHROPIC_MODEL_TABLE if use_anthropic_ids else MODEL_TABLE
    model_id = table[tier]

    # Free-tier is the default for subagents.
    # Opt out with AOS_PAID_TIER=1.
    if tier == "free" or (tier == "fast" and os.getenv("AOS_PAID_TIER") != "1"):
        return _next_free_model()

    return model_id
