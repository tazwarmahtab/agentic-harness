"""
TazOS Engine — FastAPI application.

Exposes:
  - GET  /health              — liveness probe
  - WS   /ws/harness/{name}  — harness execution via WebSocket streaming
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from tazos.discover import find_venture
from tazos.graph import CycleState, build_graph
from tazos.llm import LLMClient, create_llm_client
from tazos.memory import build_memory_from_manifest, MemoryStore
from tazos.registry import HarnessBundle, load_registry
from tazos.tools import ToolGateway
from tazos.usage import UsageTracker

logger = logging.getLogger("tazos.api")

app = FastAPI(
    title="TazOS Engine",
    version="0.1.0",
    description="Governance-first agentic operating system engine.",
)

# Token auth — if TAZOS_API_TOKEN env var is set, WebSocket requires it as ?token=
TAZOS_API_TOKEN = os.getenv("TAZOS_API_TOKEN", "")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok", "service": "tazos-engine"}


# ---------------------------------------------------------------------------
# REST — harness catalogue
# ---------------------------------------------------------------------------

@app.get("/api/harnesses")
async def list_harnesses() -> list[dict[str, str]]:
    """Return all available harnesses discovered from tazos/harnesses/*."""
    harnesses_dir = _find_project_root() / "tazos" / "harnesses"
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
                result.append({
                    "id": bundle.harness.id,
                    "name": child.name,
                    "venture": registry.venture.id if registry.venture else "",
                })
        except Exception:
            # Fallback: return directory name even if YAML parsing fails
            result.append({"id": f"HAR-{child.name.upper()}", "name": child.name, "venture": ""})
    return result


# ---------------------------------------------------------------------------
# Helpers — filesystem / registry resolution
# ---------------------------------------------------------------------------

def _find_project_root() -> Path:
    """Find the tazos-engine project root (where tazos/ package lives).

    Same logic as ``__main__.find_project_root``.
    """
    return Path(__file__).parent.parent


def _resolve_bundle(
    harness_name: str,
    venture_name: str | None = None,
) -> tuple[HarnessBundle, str, str] | tuple[None, str, str]:
    """Load registry and return (bundle, venture_id, harness_id) or (None, …).

    Resolves harness directory and optional venture path following the same
    conventions as the CLI ``run`` command.
    """
    root = _find_project_root()
    harness_dir = root / "tazos" / "harnesses" / harness_name

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
            bundle.memory.model_dump(), venture_root=venture_root,
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

    # Token auth (if TAZOS_API_TOKEN is set)
    if TAZOS_API_TOKEN:
        token = websocket.query_params.get("token", "")
        if token != TAZOS_API_TOKEN:
            await websocket.send_json({"event": "error", "message": "Unauthorized"})
            await websocket.close(code=4001)
            return

    try:
        # --- Resolve bundle ---
        bundle, venture_id, harness_id = _resolve_bundle(
            harness_name, venture_name=venture,
        )

        if bundle is None:
            await websocket.send_json({
                "event": "error",
                "message": f"Harness '{harness_name}' not found.",
            })
            await websocket.close()
            return

        # --- Connected ack ---
        await websocket.send_json({
            "event": "connected",
            "harness": harness_name,
            "venture": venture_id,
        })

        # --- Build infrastructure (live LLM — gated by harness manifest) ---
        # Derive venture root from first harness artifact if available
        venture_root: Path | None = None
        if bundle.tools and bundle.tools.tools:
            for tool in bundle.tools.tools:
                if hasattr(tool, "root") and tool.root:
                    venture_root = Path(tool.root)
                    break

        llm, gateway, memory_store, usage_tracker = _build_infra(
            bundle, venture_root=venture_root,
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
        await websocket.send_json({
            "event": "completed",
            "state_summary": {
                "venture_id": venture_id,
                "harness_id": harness_id,
                "cycle_id": initial_state.get("cycle_id", ""),
            },
        })

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
            await websocket.send_json({
                "event": "error",
                "message": str(exc),
            })
        except Exception:
            pass  # Socket already closed
    finally:
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed


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
