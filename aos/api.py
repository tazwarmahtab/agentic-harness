"""
TazOS Engine — FastAPI application.

Exposes:
  - GET  /health              — liveness probe
  - GET  /api/harnesses       — harness catalogue
  - GET  /api/summary         — dashboard KPIs
  - GET  /api/ws/stats        — WebSocket connection stats
  - WS   /ws/harness/{name}  — harness execution via WebSocket streaming
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import os
import uuid
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from aos.discover import find_venture
from aos.hardening import ConnectionLimiter, sanitize_path, validate_harness_name
from aos.graph import CycleState, build_graph
from aos.llm import LLMClient, create_llm_client
from aos.memory import build_memory_from_manifest, MemoryStore
from aos.registry import HarnessBundle, load_registry
from aos.tools import ToolGateway
from aos.usage import UsageTracker
from aos.health import check_system_health
from aos.entity_index import default_index
from aos.event_bus import default_bus
from aos.services.pipeline import get_pipeline_status, get_pipeline_history
from aos.services.approvals import (
    get_pending_approvals,
    approve_request,
    reject_request,
)
from aos.services.memory import get_memory_summary
from aos.services.sales import get_sales_status
from aos.services.system import get_system_status
from aos.services.agents import get_agents_status
from aos.services.netso_customer import (
    get_generation,
    get_savings,
    get_billing,
    get_portfolio,
    get_financials,
)

logger = logging.getLogger("aos.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle — replaces deprecated on_event."""
    logger.info("Running startup health check...")

    llm_check = _check_llm_providers()
    if not llm_check["any_available"]:
        logger.warning("⚠️  No LLM providers configured! System will fail at runtime.")
        for warning in llm_check["warnings"]:
            logger.warning(f"   - {warning}")
    else:
        available = [k for k, v in llm_check["providers"].items() if v]
        logger.info(f"✓ LLM providers available: {', '.join(available)}")

    env_check = _check_required_env_vars()
    if not env_check["all_present"]:
        logger.warning(
            f"⚠️  Missing required env vars: {', '.join(env_check['missing'])}"
        )
    else:
        logger.info("✓ All required env vars present")

    yield


app = FastAPI(
    title="AOS Engine",
    version="0.1.0",
    description="Governance-first agentic operating system engine.",
    lifespan=lifespan,
)

# CORS — allow dashboard preview from any local origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token auth — if AOS_API_TOKEN env var is set, WebSocket requires it as ?token=
AOS_API_TOKEN = os.getenv("AOS_API_TOKEN", "") or os.getenv("TAZOS_API_TOKEN", "")
TAZOS_API_TOKEN = AOS_API_TOKEN  # backward-compat alias

# WebSocket connection limiter — caps concurrent connections per server instance
_ws_limiter = ConnectionLimiter(max_connections=10)


# ---------------------------------------------------------------------------
# REST auth dependency — mirrors WebSocket token gating for REST endpoints
# ---------------------------------------------------------------------------


def _require_auth(
    authorization: str | None = Header(None),
) -> None:
    """FastAPI dependency: reject requests without valid Bearer token.

    If AOS_API_TOKEN is not configured, auth is skipped (local-dev mode).
    Raises HTTPException 401 if token is missing or invalid.
    """
    from fastapi import HTTPException

    if not AOS_API_TOKEN:
        return  # no token configured — local dev, allow all

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization format")

    if parts[1] != AOS_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


def _check_llm_providers() -> dict[str, str | list[str] | bool]:
    """Check which LLM providers are configured and available."""
    providers = {
        "anthropic": False,
        "local_router": False,
        "nvidia_nim": False,
    }
    warnings = []

    # Check Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_token = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    if anthropic_key or anthropic_token:
        providers["anthropic"] = True
    else:
        warnings.append("ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN not configured")

    # Check local router
    router_base = os.getenv("AOS_LLM_BASE_URL", "")
    if router_base:
        providers["local_router"] = True

    # Check NVIDIA NIM
    nvidia_key = os.getenv("NVIDIA_NIM_API_KEY", "")
    if nvidia_key:
        providers["nvidia_nim"] = True

    return {
        "providers": providers,
        "warnings": warnings,
        "any_available": any(providers.values()),
    }


def _check_required_env_vars() -> dict[str, bool | list[str]]:
    """Check if required environment variables are set."""
    required = {
        "AOS_API_TOKEN": os.getenv("AOS_API_TOKEN", ""),
    }

    missing = [k for k, v in required.items() if not v]

    return {"all_present": len(missing) == 0, "missing": missing}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok", "service": "aos-engine"}


@app.get("/health/ready")
async def health_ready() -> dict:
    """Readiness check — detailed component health via aos.health module."""
    result = check_system_health()
    d = result.to_dict()
    d["service"] = "aos-engine"
    return d


# ---------------------------------------------------------------------------
# REST — harness catalogue
# ---------------------------------------------------------------------------


@app.get("/api/harnesses")
async def list_harnesses() -> list[dict[str, str]]:
    """Return all available harnesses discovered from aos/harnesses/*."""
    harnesses_dir = Path(__file__).parent / "harnesses"
    result: list[dict[str, str]] = []
    if not harnesses_dir.exists():
        return result
    for child in sorted(harnesses_dir.iterdir()):
        if not child.is_dir():
            continue
        harness_yml = child / "harness.yml"
        if not harness_yml.exists():
            continue
        # Load via registry to get structured data
        try:
            registry = load_registry(harness_dir=child)
            if registry.harnesses:
                bundle = next(iter(registry.harnesses.values()))
                result.append(
                    {
                        "id": bundle.harness.id,
                        "name": child.name,
                        "venture": registry.venture.id if registry.venture else "",
                    }
                )
        except Exception:
            # Fallback: return directory name even if YAML parsing fails
            result.append(
                {"id": f"HAR-{child.name.upper()}", "name": child.name, "venture": ""}
            )
    return result


# ---------------------------------------------------------------------------
# Helpers — filesystem / registry resolution
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Find the aos-engine project root."""
    from aos.__main__ import find_project_root

    return find_project_root()


def _resolve_bundle(
    harness_name: str,
    venture_name: str | None = None,
) -> tuple[HarnessBundle, str, str] | tuple[None, str, str]:
    """Load registry and return (bundle, venture_id, harness_id) or (None, …).

    Resolves harness directory and optional venture path following the same
    conventions as the CLI ``run`` command.

    Validates harness_name against traversal attacks before constructing
    any filesystem paths.
    """
    # Security: validate harness name before path construction
    if not validate_harness_name(harness_name):
        logger.warning("Invalid harness name rejected: %r", harness_name)
        return None, venture_name or "unknown", harness_name
    if sanitize_path(harness_name) is None:
        logger.warning("Path traversal attempt blocked: %r", harness_name)
        return None, venture_name or "unknown", harness_name

    harness_dir = Path(__file__).parent / "harnesses" / harness_name

    if not harness_dir.exists():
        return None, venture_name or "unknown", harness_name

    # Resolve venture
    venture_path = None
    if venture_name:
        result = find_venture(venture_name)
        if result:
            vp, _venture = result
            venture_path = vp

    registry = load_registry(
        harness_dir=harness_dir,
        venture_path=venture_path if venture_path and venture_path.exists() else None,
    )

    if not registry.harnesses:
        return None, venture_name or "unknown", harness_name

    bundle = next(iter(registry.harnesses.values()))
    venture_id = registry.venture.id if registry.venture else "UNKNOWN"
    harness_id = bundle.harness.id

    return bundle, venture_id, harness_id


def _build_infra(
    bundle: HarnessBundle,
    venture_root: Path | None = None,
) -> tuple[LLMClient, ToolGateway, MemoryStore | None, UsageTracker]:
    """Construct infrastructure objects for graph execution (live LLM)."""
    llm = create_llm_client(dry_run=False, verbose=False)

    # Memory store
    memory_store: MemoryStore | None = None
    if bundle.memory:
        memory_store = build_memory_from_manifest(
            bundle.memory.model_dump(),
            venture_root=venture_root,
        )

    # Tool gateway
    gateway = ToolGateway(venture_root=venture_root, memory_store=memory_store)
    if bundle.tools:
        gateway.register_tools_from_dict(
            [
                t.model_dump() if hasattr(t, "model_dump") else t
                for t in (bundle.tools.tools if hasattr(bundle.tools, "tools") else [])
            ]
        )

    usage_tracker = UsageTracker()

    return llm, gateway, memory_store, usage_tracker


def _build_initial_state(
    venture_id: str,
    harness_id: str,
    venture_artifacts: dict[str, str] | None = None,
) -> CycleState:
    """Build the initial CycleState for a new execution cycle."""
    cycle_id = f"{date.today().isoformat()}-ws"

    return CycleState(
        venture_id=venture_id,
        harness_id=harness_id,
        cycle_id=cycle_id,
        venture_artifacts=venture_artifacts or {},
        inputs={},
        step_results=[],
        approval_queue=[],
        handoffs=[],
        errors=[],
    )


@app.get("/api/entity-index")
async def entity_index_summary() -> dict:
    """Return summary of registered AOS entities."""
    return {
        "total": len(default_index),
        "by_type": default_index.summary(),
    }


@app.get("/api/event-log")
async def event_log() -> dict:
    """Return AOS event bus summary."""
    return {
        "total_events": len(default_bus.log()),
        "by_type": default_bus.summary(),
    }


# ---------------------------------------------------------------------------
# WebSocket — harness execution
# ---------------------------------------------------------------------------


@app.websocket("/ws/harness/{harness_name}")
async def harness_ws(
    websocket: WebSocket,
    harness_name: str,
    venture: str | None = None,
) -> None:
    """Stream harness execution over a WebSocket connection.

    Query params:
        venture – venture name/id (defaults to first discovered venture)

    Protocol:
        Client connects → server sends ``connected`` → server streams
        ``node_update`` events for each graph node → server sends
        ``completed`` when the graph finishes.

    Events sent by server::

        {"event": "connected",   "harness": "...", "venture": "..."}
        {"event": "node_update", "node": "...", "state_diff": {...}}
        {"event": "completed",   "state_summary": {...}}
        {"event": "error",       "message": "..."}
    """
    await websocket.accept()

    # Token auth (if AOS_API_TOKEN is set)
    if AOS_API_TOKEN:
        token = websocket.query_params.get("token", "")
        if token != AOS_API_TOKEN:
            await websocket.send_json({"event": "error", "message": "Unauthorized"})
            await websocket.close(code=4001)
            return

    # Connection limiting — cap concurrent WebSocket sessions
    conn_id = f"{harness_name}:{uuid.uuid4().hex[:12]}"
    if not _ws_limiter.try_acquire(conn_id):
        await websocket.send_json(
            {
                "event": "error",
                "message": "Connection limit reached. Try again later.",
            }
        )
        await websocket.close(code=4029)
        return

    try:
        # --- Resolve bundle ---
        bundle, venture_id, harness_id = _resolve_bundle(
            harness_name,
            venture_name=venture,
        )

        if bundle is None:
            await websocket.send_json(
                {
                    "event": "error",
                    "message": f"Harness '{harness_name}' not found.",
                }
            )
            await websocket.close()
            return

        # --- Connected ack ---
        await websocket.send_json(
            {
                "event": "connected",
                "harness": harness_name,
                "venture": venture_id,
            }
        )

        # --- Build infrastructure (live LLM — gated by harness manifest) ---
        # Derive venture root from first harness artifact if available
        venture_root: Path | None = None
        if bundle.tools and bundle.tools.tools:
            for tool in bundle.tools.tools:
                if hasattr(tool, "root") and tool.root:
                    venture_root = Path(tool.root)
                    break

        llm, gateway, memory_store, usage_tracker = _build_infra(
            bundle,
            venture_root=venture_root,
        )

        # --- Build graph ---
        compiled_graph = build_graph(
            bundle=bundle,
            llm=llm,
            tool_gateway=gateway,
            memory_store=memory_store,
            usage_tracker=usage_tracker,
        )

        # --- Resolve venture artifacts (file paths) ---
        venture_artifacts: dict[str, str] = {}
        # (None for now — artifacts are resolved from CLI args or defaults)

        # --- Initial state ---
        initial_state = _build_initial_state(
            venture_id=venture_id,
            harness_id=harness_id,
            venture_artifacts=venture_artifacts,
        )

        # --- Graph config ---
        config: dict = {
            "configurable": {
                "bundle": bundle,
                "llm": llm,
                "tool_gateway": gateway,
                "memory_store": memory_store,
                "usage_tracker": usage_tracker,
            }
        }

        # --- Stream the graph ---
        # astream is async-native; LangGraph bridges sync nodes internally.
        async for update in _stream_graph(compiled_graph, initial_state, config):
            await websocket.send_json(update)

        # --- Completed ---
        await websocket.send_json(
            {
                "event": "completed",
                "state_summary": {
                    "venture_id": venture_id,
                    "harness_id": harness_id,
                    "cycle_id": initial_state.get("cycle_id", ""),
                },
            }
        )

    except WebSocketDisconnect:
        # Client disconnected mid-execution — no cleanup needed.
        # The threadpool and graph are GC'd automatically.
        logger.info(
            "Client disconnected from /ws/harness/%s mid-execution.",
            harness_name,
        )
    except Exception as exc:
        logger.exception("WebSocket error in /ws/harness/%s", harness_name)
        try:
            await websocket.send_json(
                {
                    "event": "error",
                    "message": str(exc),
                }
            )
        except Exception:
            pass  # Socket already closed
    finally:
        _ws_limiter.release(conn_id)
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed


# ---------------------------------------------------------------------------
# REST — WebSocket stats
# ---------------------------------------------------------------------------


@app.get("/api/ws/stats")
async def ws_stats() -> dict[str, int]:
    """Return current WebSocket connection stats."""
    return {
        "active_connections": _ws_limiter.active_count,
        "max_connections": _ws_limiter.max_connections,
    }


# ---------------------------------------------------------------------------
# REST — Dashboard summary
# ---------------------------------------------------------------------------


@app.get("/api/summary")
async def dashboard_summary() -> dict[str, object]:
    """Return high-level KPIs for the dashboard frontend."""
    root = _find_project_root()
    harnesses_dir = Path(__file__).parent / "harnesses"

    # Count harnesses
    harness_count = 0
    if harnesses_dir.exists():
        harness_count = sum(
            1
            for d in harnesses_dir.iterdir()
            if d.is_dir() and (d / "harness.yml").exists()
        )

    # Count test files
    test_count = 0
    tests_dir = root / "tests"
    if tests_dir.exists():
        test_count = sum(1 for _ in tests_dir.rglob("test_*.py"))

    # Memory domains
    memory_count = 0
    memory_dir = Path(__file__).parent / "memory"
    if memory_dir.exists():
        memory_count = sum(1 for _ in memory_dir.glob("*.yml"))

    return {
        "harnesses": harness_count,
        "tests": test_count,
        "memory_domains": memory_count,
        "financial_accuracy": None,  # populated after first evaluator run
    }


# ---------------------------------------------------------------------------
# REST — Pipeline status
# ---------------------------------------------------------------------------


@app.get("/api/pipeline/status")
async def pipeline_status() -> dict[str, object]:
    """Return pipeline execution status."""
    status = get_pipeline_status()
    return status.to_dict()


@app.get("/api/pipeline/history")
async def pipeline_history() -> list[dict[str, object]]:
    """Return pipeline execution history."""
    return get_pipeline_history()


# ---------------------------------------------------------------------------
# REST — Approvals
# ---------------------------------------------------------------------------


@app.get("/api/approvals")
async def list_approvals(
    _auth: None = Depends(_require_auth),
) -> list[dict[str, object]]:
    """Return pending approvals."""
    approvals = get_pending_approvals()
    return [a.to_dict() for a in approvals]


@app.post("/api/approvals/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    _auth: None = Depends(_require_auth),
) -> dict[str, object]:
    """Approve a pending request."""
    return approve_request(approval_id)


@app.post("/api/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    reason: str = "",
    _auth: None = Depends(_require_auth),
) -> dict[str, object]:
    """Reject a pending request."""
    return reject_request(approval_id, reason)


# ---------------------------------------------------------------------------
# REST — Memory
# ---------------------------------------------------------------------------


@app.get("/api/memory/summary")
async def memory_summary() -> dict[str, object]:
    """Return memory store summary."""
    summary = get_memory_summary()
    return summary.to_dict()


# ---------------------------------------------------------------------------
# REST — Sales
# ---------------------------------------------------------------------------


@app.get("/api/sales/status")
async def sales_status() -> dict[str, object]:
    """Return sales graph status."""
    status = get_sales_status()
    return status.to_dict()


# ---------------------------------------------------------------------------
# REST — System status
# ---------------------------------------------------------------------------


@app.get("/api/system/status")
async def system_status() -> dict[str, object]:
    """Return system status with health score."""
    status = get_system_status()
    return status.to_dict()


# ---------------------------------------------------------------------------
# REST — Agents
# ---------------------------------------------------------------------------


@app.get("/api/agents")
async def agents_status() -> dict[str, object]:
    """Return agents status summary."""
    status = get_agents_status()
    return status.to_dict()


# ---------------------------------------------------------------------------
# REST — Dashboard aggregate endpoint
# ---------------------------------------------------------------------------


@app.get("/api/dashboard")
async def dashboard() -> dict[str, object]:
    """Return all KPIs in a single response for the Mission Control Dashboard."""
    # Get basic counts
    root = _find_project_root()
    harnesses_dir = Path(__file__).parent / "harnesses"

    # Count harnesses
    harness_count = 0
    if harnesses_dir.exists():
        harness_count = sum(
            1
            for d in harnesses_dir.iterdir()
            if d.is_dir() and (d / "harness.yml").exists()
        )

    # Count test files
    test_count = 0
    tests_dir = root / "tests"
    if tests_dir.exists():
        test_count = sum(1 for _ in tests_dir.rglob("test_*.py"))

    # Memory domains
    memory_count = 0
    memory_dir = Path(__file__).parent / "memory"
    if memory_dir.exists():
        memory_count = sum(1 for _ in memory_dir.glob("*.yml"))

    # Entity count
    entity_count = len(default_index)

    # Event count
    event_count = len(default_bus.log())

    # Pipeline status
    pipeline = get_pipeline_status()

    # Approvals
    approvals = get_pending_approvals()

    # WebSocket connections
    ws_stats = {
        "active_connections": _ws_limiter.active_count,
        "max_connections": _ws_limiter.max_connections,
    }

    # System health
    system = get_system_status()

    return {
        "harnesses": harness_count,
        "tests": test_count,
        "memory_domains": memory_count,
        "entity_count": entity_count,
        "event_count": event_count,
        "pipeline": pipeline.to_dict(),
        "approval_count": len(approvals),
        "ws_connections": ws_stats,
        "health_score": system.health_score,
    }


async def _stream_graph(
    compiled_graph,
    initial_state: CycleState,
    config: dict,
):
    """Async generator that streams graph node updates over WebSocket.

    Each yielded item is a dict ready to send as JSON::

        {"event": "node_update", "node": "...", "state_diff": {...}}
    """
    # astream with stream_mode="updates" yields dicts: {node_name: output}
    aiterator = compiled_graph.astream(
        initial_state,
        config=config,
        stream_mode="updates",
    )

    try:
        async for chunk in aiterator:
            # chunk is a dict like {"review": {...}} or a tuple depending on mode
            if isinstance(chunk, dict):
                for node_name, state_diff in chunk.items():
                    yield {
                        "event": "node_update",
                        "node": node_name,
                        "state_diff": state_diff,
                    }
    except Exception as exc:
        yield {
            "event": "error",
            "message": f"Graph execution failed: {exc}",
        }


# ── Netso Customer Dashboard ────────────────────────────────────────────────


@app.get("/api/netso/customers/{site_id}/generation")
async def netso_generation(site_id: str) -> dict:
    data = get_generation(site_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return data.to_dict()


@app.get("/api/netso/customers/{site_id}/savings")
async def netso_savings(site_id: str) -> dict:
    data = get_savings(site_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return data.to_dict()


@app.get("/api/netso/customers/{site_id}/billing")
async def netso_billing(site_id: str) -> dict:
    data = get_billing(site_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return data.to_dict()


@app.get("/api/netso/portfolio")
async def netso_portfolio() -> dict:
    return get_portfolio().to_dict()


@app.get("/api/netso/financials")
async def netso_financials() -> dict:
    return get_financials().to_dict()
