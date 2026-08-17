"""Runtime synchronization between AOS cycles and Paperclip.

Paperclip owns workforce/task state; AOS owns execution. This adapter keeps
that boundary explicit and is deliberately fail-soft: a Paperclip outage must
not corrupt or block the AOS execution result.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from aos.integrations.paperclip import PaperclipClient, PaperclipError, build_client_from_env

logger = logging.getLogger("aos.paperclip_runtime")


EXECUTIVE_ISSUE_ENV = "PAPERCLIP_EXECUTIVE_ISSUE_ID"


def sync_cycle_outcome(state: dict[str, Any]) -> dict[str, Any]:
    """Publish an AOS cycle outcome to the configured Paperclip control issue.

    If Paperclip is not configured, returns a skipped result. If configured but
    unavailable, returns an error result without raising into the AOS cycle.
    """
    if not os.getenv("PAPERCLIP_API_URL"):
        return {"status": "skipped", "reason": "Paperclip not configured"}

    try:
        client: PaperclipClient = build_client_from_env()
    except PaperclipError as exc:
        logger.warning("Paperclip configuration unavailable: %s", exc)
        return {"status": "skipped", "reason": "Paperclip configuration incomplete"}

    issue_id = os.getenv(EXECUTIVE_ISSUE_ENV, "")
    cycle_id = str(state.get("cycle_id", "unknown"))
    errors = list(state.get("errors", []))
    approvals = list(state.get("approval_queue", []))
    evaluation = state.get("evaluation", {})

    comment = (
        f"AOS cycle `{cycle_id}` completed.\n\n"
        f"Steps: {len(state.get('step_results', []))}\n"
        f"Errors: {len(errors)}\n"
        f"Pending approvals: {len(approvals)}\n"
        f"Evaluation: {evaluation.get('overall_status', 'not_reported') if isinstance(evaluation, dict) else 'not_reported'}"
    )
    if errors:
        comment += "\n\nErrors:\n" + "\n".join(f"- {e}" for e in errors[-5:])

    try:
        if issue_id:
            result = client.update_issue(
                issue_id,
                status="in_progress" if errors or approvals else "done",
                comment=comment,
                run_id=cycle_id,
            )
            return {"status": "synced", "mode": "existing_issue", "result": result}

        result = client.create_issue(
            title=f"Netso executive cycle {cycle_id}",
            description=comment,
            priority="high" if errors or approvals else "medium",
        )
        return {"status": "synced", "mode": "created_issue", "result": result}
    except PaperclipError as exc:
        logger.warning("Paperclip cycle sync failed: %s", exc)
        return {"status": "error", "reason": "Paperclip request failed"}
