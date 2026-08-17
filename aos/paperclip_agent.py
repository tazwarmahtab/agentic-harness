"""Paperclip heartbeat entrypoint for the Netso AOS runtime.

Paperclip owns agent identity, assignment, heartbeat scheduling and task state.
This process delegates reasoning to the existing AOS agent contract, then
executes only explicitly declared tool calls through the governed gateway.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from aos.graph import _run_agent_node
from aos.integrations.governed_gateway import GovernedToolGateway
from aos.integrations.paperclip_runtime import sync_cycle_outcome
from aos.llm import create_llm_client
from aos.memory import build_memory_from_manifest
from aos.registry import load_registry
from aos.usage import UsageTracker


AGENT_MAP = {
    "ceo": "AGT-EXEC-CEO",
    "cfo": "AGT-EXEC-CFO",
    "coo": "AGT-EXEC-COO",
    "cro": "AGT-EXEC-CRO",
    "cto": "AGT-EXEC-CTO",
    "legal": "AGT-EXEC-LEG",
}


def _project_root() -> Path:
    configured = os.getenv("AOS_PROJECT_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parent.parent


def _task_input() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return os.getenv("PAPERCLIP_TASK_PROMPT", "")


def _register_approval_tokens(gateway: GovernedToolGateway) -> None:
    """Load opaque approvals from a trusted runtime environment boundary.

    The LLM/task input never supplies these tokens. The deployment runtime must
    obtain them from the founder approval service and inject them as a secret.
    """
    raw = os.getenv("AOS_APPROVAL_TOKENS_JSON", "")
    if not raw:
        return
    try:
        approvals = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AOS_APPROVAL_TOKENS_JSON is not valid JSON") from exc
    if not isinstance(approvals, dict):
        raise RuntimeError("AOS_APPROVAL_TOKENS_JSON must be an object mapping approval IDs to tokens")
    for approval_id, token in approvals.items():
        if isinstance(approval_id, str) and isinstance(token, str):
            gateway.register_approval_token(approval_id=approval_id, token=token)


def execute_declared_tool_calls(
    gateway: GovernedToolGateway,
    output: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    """Execute structured tool calls emitted by an agent through the gateway.

    Only the declarative ``tool_calls`` field is executed. Arbitrary prose,
    shell commands, or unrecognized output fields are never treated as actions.
    """
    raw_calls = output.get("tool_calls", [])
    if raw_calls is None:
        return []
    if not isinstance(raw_calls, list):
        return [{"status": "error", "error": "tool_calls must be a list"}]

    results: list[dict[str, Any]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            results.append({"status": "error", "error": "tool call must be an object"})
            continue
        capability = call.get("capability")
        inputs = call.get("inputs", {})
        if not isinstance(capability, str) or not capability:
            results.append({"status": "error", "error": "tool call capability is required"})
            continue
        if not isinstance(inputs, dict):
            results.append({"status": "error", "error": "tool call inputs must be an object"})
            continue
        tool_result = gateway.call(capability, inputs, agent_id=agent_id)
        results.append(
            {
                "capability": capability,
                "status": tool_result.status,
                "output": tool_result.output,
                "error": tool_result.error,
                "approval_required": tool_result.approval_required,
                "approval_id": tool_result.approval_id,
            }
        )
    return results


def main() -> int:
    root = _project_root()
    harness_dir = root / "aos" / "harnesses" / "executive"
    venture_dir = root / "aos" / "ventures" / "netso"

    if not harness_dir.exists():
        print(f"AOS harness not found: {harness_dir}", file=sys.stderr)
        return 2

    agent_id = os.getenv("NETSO_AOS_AGENT_ID", "").strip()
    role = os.getenv("PAPERCLIP_AGENT_SLUG", "").strip().lower()
    if not agent_id:
        agent_id = AGENT_MAP.get(role, "")
    if not agent_id:
        print("NETSO_AOS_AGENT_ID or supported PAPERCLIP_AGENT_SLUG is required", file=sys.stderr)
        return 2

    registry = load_registry(harness_dir, venture_dir / "venture.yml")
    if not registry.harnesses:
        print("Executive harness could not be loaded", file=sys.stderr)
        return 2

    bundle = next(iter(registry.harnesses.values()))
    agent = bundle.specialists.get(agent_id)
    if agent is None:
        print(f"AOS agent not found in executive harness: {agent_id}", file=sys.stderr)
        return 2

    venture_id = registry.venture.id if registry.venture else "VEN-NETSO-001"
    venture_constants = (
        registry.venture.financial_constants.model_dump(exclude_none=True)
        if registry.venture and registry.venture.financial_constants
        else None
    )

    memory_store = None
    if bundle.memory:
        memory_store = build_memory_from_manifest(
            bundle.memory.model_dump(), venture_root=venture_dir
        )

    gateway = GovernedToolGateway(venture_root=venture_dir, memory_store=memory_store)
    if bundle.tools:
        gateway.register_tools_from_dict(
            [
                t.model_dump() if hasattr(t, "model_dump") else t
                for t in (bundle.tools.tools if hasattr(bundle.tools, "tools") else [])
            ]
        )
    _register_approval_tokens(gateway)

    llm = create_llm_client(dry_run=False, verbose=False)
    usage = UsageTracker()
    prompt = _task_input()
    cycle_id = (
        os.getenv("PAPERCLIP_RUN_ID")
        or os.getenv("PAPERCLIP_TASK_ID")
        or "paperclip-heartbeat"
    )

    result = _run_agent_node(
        agent=agent,
        bundle=bundle,
        step_name="paperclip_heartbeat",
        cycle_id=cycle_id,
        venture_id=venture_id,
        inputs={
            "paperclip_agent_id": os.getenv("PAPERCLIP_AGENT_ID", ""),
            "paperclip_task_id": os.getenv("PAPERCLIP_TASK_ID", ""),
            "task": prompt,
        },
        llm=llm,
        memory_store=memory_store,
        usage_tracker=usage,
        venture_constants=venture_constants,
    )

    tool_results = execute_declared_tool_calls(
        gateway,
        result.get("output", {}),
        agent_id=agent_id,
    )
    if tool_results:
        result["tool_results"] = tool_results
        blocked = [item for item in tool_results if item.get("status") in {"denied", "gated", "error"}]
        if blocked:
            result.setdefault("_errors", []).extend(
                f"{agent_id}: tool {item.get('capability', 'unknown')} {item.get('status')}"
                for item in blocked
            )
            if result.get("status") == "success":
                result["status"] = "partial"

    state = {
        "cycle_id": cycle_id,
        "venture_id": venture_id,
        "harness_id": bundle.harness.id,
        "step_results": [result],
        "errors": result.get("_errors", []) or ([result.get("error")] if result.get("error") else []),
        "approval_queue": [item for item in tool_results if item.get("approval_required")],
        "evaluation": result.get("output", {}).get("_validation", {}),
    }

    sync = sync_cycle_outcome(state)
    print({"result": result, "paperclip_sync": sync})
    return 0 if result.get("status") in {"success", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
