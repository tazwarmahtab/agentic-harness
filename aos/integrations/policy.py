"""Machine-enforced autonomy policy for the AOS/Paperclip boundary.

Prompts describe policy; this module enforces the minimum irreversible-action
boundary at runtime. Unknown action classes fail closed only when explicitly
marked as high-impact; ordinary internal work remains executable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class AutonomyLevel(IntEnum):
    OBSERVE = 0
    RECOMMEND = 1
    REVERSIBLE_EXECUTE = 2
    BOUNDED_EXECUTE = 3
    APPROVAL_REQUIRED = 4
    HUMAN_ONLY = 5


HIGH_IMPACT_ACTIONS = frozenset(
    {
        "money_movement",
        "financing_commitment",
        "contract_execution",
        "ownership_change",
        "governance_change",
        "safety_critical_engineering_approval",
        "regulatory_submission",
    }
)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    required_level: AutonomyLevel
    reason: str


def evaluate_action(
    *,
    action_class: str | None,
    approval_granted: bool = False,
) -> PolicyDecision:
    """Evaluate a declared action class before an irreversible tool call.

    ``action_class`` is intentionally explicit: the runtime must not infer
    legal/financial/safety consequences from free-form LLM prose.
    """
    if not action_class:
        return PolicyDecision(
            allowed=True,
            required_level=AutonomyLevel.REVERSIBLE_EXECUTE,
            reason="No high-impact action class declared.",
        )

    if action_class in HIGH_IMPACT_ACTIONS:
        if approval_granted:
            return PolicyDecision(
                allowed=True,
                required_level=AutonomyLevel.APPROVAL_REQUIRED,
                reason="Explicit founder approval is present.",
            )
        return PolicyDecision(
            allowed=False,
            required_level=AutonomyLevel.HUMAN_ONLY,
            reason=f"Founder approval required for {action_class}.",
        )

    return PolicyDecision(
        allowed=True,
        required_level=AutonomyLevel.BOUNDED_EXECUTE,
        reason="Action is outside the high-impact action registry.",
    )
