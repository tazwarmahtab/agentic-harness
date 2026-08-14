"""Policy-enforced ToolGateway for Paperclip-managed AOS execution."""

from __future__ import annotations

from typing import Any

from aos.integrations.policy import AutonomyLevel, evaluate_action
from aos.tools import ToolGateway, ToolResult


class GovernedToolGateway(ToolGateway):
    """Tool gateway that enforces high-impact action policy before execution.

    The ordinary AOS gateway remains backward compatible. Paperclip-managed
    processes use this subclass so high-impact actions cannot bypass the
    founder approval boundary.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._verified_approvals: dict[str, tuple[str, str]] = {}

    def grant_verified_approval(
        self,
        *,
        approval_id: str,
        action_class: str,
        approver_id: str,
    ) -> None:
        """Register an approval only through a trusted runtime integration.

        The approval ID is opaque to the LLM/task prompt. A caller must supply
        the founder identity and the exact action class being authorized.
        """
        if approver_id != "HUM-000001":
            raise PermissionError("Only the founder identity may grant high-impact approval")
        self._verified_approvals[approval_id] = (action_class, approver_id)

    def _approval_is_verified(
        self,
        *,
        approval_id: str | None,
        action_class: str | None,
    ) -> bool:
        if not approval_id or not action_class:
            return False
        approved_action = self._verified_approvals.get(approval_id)
        return approved_action == (action_class, "HUM-000001")

    def call(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_id: str,
    ) -> ToolResult:
        action_class = inputs.get("_action_class")
        approval_id = inputs.get("_approval_id")
        approval_granted = self._approval_is_verified(
            approval_id=approval_id,
            action_class=action_class,
        )
        decision = evaluate_action(
            action_class=action_class,
            approval_granted=approval_granted,
        )
        if not decision.allowed:
            tool = self.tools.get(capability)
            return ToolResult(
                tool_id=tool.id if tool else "",
                capability=capability,
                agent_id=agent_id,
                status="denied",
                error=decision.reason,
                approval_required=True,
            )

        sanitized = dict(inputs)
        sanitized.pop("_action_class", None)
        sanitized.pop("_approval_id", None)
        return super().call(capability, sanitized, agent_id)

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Enforce action policy before legacy concrete-action execution."""
        action_class = action.get("action_class")
        approval_id = action.get("approval_id")
        approval_granted = self._approval_is_verified(
            approval_id=approval_id,
            action_class=action_class,
        )
        decision = evaluate_action(
            action_class=action_class,
            approval_granted=approval_granted,
        )
        if not decision.allowed:
            return {
                "ok": False,
                "status": "denied",
                "error": decision.reason,
                "required_level": int(decision.required_level),
            }

        sanitized = dict(action)
        sanitized.pop("action_class", None)
        sanitized.pop("approval_id", None)
        return super().execute(sanitized)
