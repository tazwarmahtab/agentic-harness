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
import time
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
MODEL_TABLE: dict[str, str] = {
    "default": "cu/claude-4.5-sonnet",  # paid Claude Sonnet
    "reasoning": "cu/claude-4.5-opus-high-thinking",  # paid Claude Opus
    "fast": "cu/claude-4.5-haiku",  # paid Claude Haiku
    "subagent": "cu/claude-4.5-haiku",  # paid Claude Haiku
    "free": "openrouter/google/gemma-4-31b-it:free",  # free pool entry
}

# Pool of verified free-tier models — round-robin indexed.
FREE_MODEL_POOL: list[str] = [
    "openrouter/google/gemma-4-31b-it:free",
    "openrouter/nvidia/stepfun-ai/step-3.7-flash",  # verified working via 9router
    "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
    "openrouter/meta/llama-4-scout-17b-16e-instruct",
    "openrouter/google/gemini-2.5-flash",
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


def _next_free_model() -> str:
    """Return the next model from FREE_MODEL_POOL, cycling round-robin."""
    global _free_model_idx
    with _free_model_lock:
        model = FREE_MODEL_POOL[_free_model_idx % len(FREE_MODEL_POOL)]
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

                        # Record success and return
                        circuit_breaker.record_success()
                        return LLMResponse(
                            content=content,
                            model=body.get("model", current_model),
                            usage=body.get("usage", {}),
                            provider="9router",
                        )
                except (urllib.error.URLError, ConnectionError) as e:
                    last_error = e
                    circuit_breaker.record_failure()
                    if attempt < 2:
                        time.sleep(2**attempt)
                        continue
                    # 404 means model not found — try next model
                    if hasattr(e, "code") and e.code == 404:
                        break
                    # For other errors, continue to next model
                    break

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
            tier = "default"
            for t, m in MODEL_TABLE.items():
                if m == model:
                    tier = t
                    break
            anthropic_model = ANTHROPIC_MODEL_TABLE.get(
                tier, "claude-sonnet-4-20250514"
            )

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

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.API_URL, data=data, headers=headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                content_parts = body.get("content", [])
                text = "".join(
                    p.get("text", "") for p in content_parts if p.get("type") == "text"
                )
                circuit_breaker.record_success()
                return LLMResponse(
                    content=text,
                    model=body.get("model", anthropic_model),
                    usage=body.get("usage", {}),
                    provider="anthropic",
                )
        except (urllib.error.URLError, ConnectionError) as e:
            circuit_breaker.record_failure()
            raise


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
                    circuit_breaker.record_failure()
                    raise ConnectionError(f"NVIDIA NIM error: {body['error']}")

                choice = body["choices"][0]
                msg = choice.get("message", {})
                content = msg.get("content", "")
                circuit_breaker.record_success()
                return LLMResponse(
                    content=content,
                    model=body.get("model", model),
                    usage=body.get("usage", {}),
                    provider="nvidia-nim",
                )
        except (urllib.error.URLError, ConnectionError) as e:
            circuit_breaker.record_failure()
            raise


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

    # Auto-detect: check 9router first (with usability guard), then Anthropic, then dry run
    router_base = os.getenv("AOS_LLM_BASE_URL", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    has_auth_token = bool(os.getenv("ANTHROPIC_AUTH_TOKEN", ""))

    # 9router is usable only if it has configured backend providers
    if has_auth_token and _is_9router_usable(router_base):
        if verbose:
            logger.info(f"Using local router backend: {router_base}")
        return RouterLLMClient()

    # No working 9router. NVIDIA-NIM models (nvidia/*, z-ai/*) can be
    # reached directly if NVIDIA_NIM_API_KEY is set.
    if os.getenv("NVIDIA_NIM_API_KEY"):
        try:
            return NvidiaLLMClient()
        except ValueError:
            pass  # fall through to Anthropic

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
