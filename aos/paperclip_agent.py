"""Paperclip heartbeat entrypoint for the Netso AOS runtime.

Paperclip owns agent identity, assignment, heartbeat scheduling and task state.
This process adapter delegates the actual reasoning/execution to the existing
AOS agent contract, then publishes the result back to Paperclip.

Task input from Paperclip is untrusted data. It cannot change the selected
agent, capability set, or autonomy policy.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from aos.integrations.paperclip_runtime import sync_cycle_outcome
from aos.llm import create_llm_client
from aos.memory import build_memory_from_manifest
from aos.registry import load_registry
from aos.tools import ToolGateway
from aos.usage import UsageTracker
from aos.graph import _run_agent_node


# Canonical AOS identities. These are explicit rather than silently mapping a
# Paperclip executive to a semantically unrelated analyst/dispatcher.
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

    gateway = ToolGateway(venture_root=venture_dir, memory_store=memory_store)
    if bundle.tools:
        gateway.register_tools_from_dict(
            [
                t.model_dump() if hasattr(t, "model_dump") else t
                for t in (bundle.tools.tools if hasattr(bundle.tools, "tools") else [])
            ]
        )

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

    state = {
        "cycle_id": cycle_id,
        "venture_id": venture_id,
        "harness_id": bundle.harness.id,
        "step_results": [result],
        "errors": [result.get("error")] if result.get("error") else [],
        "approval_queue": [],
        "evaluation": result.get("output", {}).get("_validation", {}),
    }

    sync = sync_cycle_outcome(state)
    print({"result": result, "paperclip_sync": sync})
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
