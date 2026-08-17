"""Policy-enforced ToolGateway for Paperclip-managed AOS execution."""

from __future__ import annotations

from typing import Any

from aos.integrations.policy import AutonomyLevel, evaluate_action
from aos.tools import ToolGateway, ToolResult


class GovernedToolGateway(ToolGateway):
    """Tool gateway that enforces high-impact action policy before execution."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._approval_tokens: dict[str, str] = {}

    def register_approval_token(self, *, approval_id: str, token: str) -> None:
        """Register an opaque token received from the trusted approval service."""
        if not approval_id or not token:
            raise ValueError("approval_id and token are required")
        self._approval_tokens[approval_id] = token

    def _token_for(self, approval_id: str | None) -> str | None:
        return self._approval_tokens.get(approval_id or "")

    def call(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_id: str,
    ) -> ToolResult:
        action_class = inputs.get("_action_class")
        approval_id = inputs.get("_approval_id")
        decision = evaluate_action(
            action_class=action_class,
            approval_token=self._token_for(approval_id),
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
        decision = evaluate_action(
            action_class=action_class,
            approval_token=self._token_for(approval_id),
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
