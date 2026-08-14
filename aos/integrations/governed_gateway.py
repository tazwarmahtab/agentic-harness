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

    def call(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_id: str,
    ) -> ToolResult:
        action_class = inputs.get("_action_class")
        approval_granted = bool(inputs.get("_approval_granted", False))
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
        sanitized.pop("_approval_granted", None)
        return super().call(capability, sanitized, agent_id)

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Enforce action policy before legacy concrete-action execution."""
        decision = evaluate_action(
            action_class=action.get("action_class"),
            approval_granted=bool(action.get("approval_granted", False)),
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
        sanitized.pop("approval_granted", None)
        return super().execute(sanitized)
