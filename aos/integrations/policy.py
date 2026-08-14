"""Machine-enforced autonomy policy for the AOS/Paperclip boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from enum import IntEnum
from typing import Any


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

FOUNDER_ID = "HUM-000001"


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    required_level: AutonomyLevel
    reason: str


def _secret() -> bytes:
    value = os.getenv("AOS_APPROVAL_SIGNING_SECRET", "")
    return value.encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_founder_approval_token(
    *,
    approval_id: str,
    action_class: str,
    founder_id: str = FOUNDER_ID,
) -> str:
    """Create an action-bound HMAC token for a trusted approval service."""
    secret = _secret()
    if not secret:
        raise RuntimeError("AOS_APPROVAL_SIGNING_SECRET is required to mint approval tokens")
    payload = {
        "approval_id": approval_id,
        "action_class": action_class,
        "founder_id": founder_id,
        "version": 1,
    }
    encoded = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = hmac.new(secret, encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64(signature)}"


def verify_founder_approval_token(
    token: str | None,
    *,
    action_class: str,
    founder_id: str = FOUNDER_ID,
) -> bool:
    """Verify that a token was signed by the trusted approval service and is bound to this action."""
    if not token or not action_class or not _secret():
        return False
    try:
        encoded, supplied_sig = token.split(".", 1)
        expected_sig = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(supplied_sig), expected_sig):
            return False
        payload: dict[str, Any] = json.loads(_unb64(encoded))
        return (
            payload.get("version") == 1
            and payload.get("founder_id") == founder_id
            and payload.get("action_class") == action_class
            and bool(payload.get("approval_id"))
        )
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def evaluate_action(
    *,
    action_class: str | None,
    approval_token: str | None = None,
    founder_id: str = FOUNDER_ID,
) -> PolicyDecision:
    """Evaluate a declared action class before an irreversible tool call.

    High-impact actions require an action-bound, cryptographically signed
    founder approval token. Free-form task input and booleans are never proof
    of authority.
    """
    if not action_class:
        return PolicyDecision(
            allowed=True,
            required_level=AutonomyLevel.REVERSIBLE_EXECUTE,
            reason="No high-impact action class declared.",
        )

    if action_class in HIGH_IMPACT_ACTIONS:
        if verify_founder_approval_token(
            approval_token,
            action_class=action_class,
            founder_id=founder_id,
        ):
            return PolicyDecision(
                allowed=True,
                required_level=AutonomyLevel.APPROVAL_REQUIRED,
                reason="Verified founder approval token is present.",
            )
        return PolicyDecision(
            allowed=False,
            required_level=AutonomyLevel.HUMAN_ONLY,
            reason=f"Verified founder approval required for {action_class}.",
        )

    return PolicyDecision(
        allowed=True,
        required_level=AutonomyLevel.BOUNDED_EXECUTE,
        reason="Action is outside the high-impact action registry.",
    )
