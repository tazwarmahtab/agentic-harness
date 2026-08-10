"""Notification helper — sends alerts via Telegram and console.

Centralizes notification logic for approval requests, daily briefs,
and escalation alerts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("aos.notify")


def _load_env():
    """Load .env file if not already loaded."""
    if os.getenv("AOS_TELEGRAM_BOT_TOKEN"):
        return  # Already loaded

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            # Manual .env loading if python-dotenv not installed
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ.setdefault(key.strip(), value.strip())


def _get_telegram_provider():
    """Get Telegram alert provider if configured."""
    _load_env()
    bot_token = os.getenv("AOS_TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("AOS_TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return None
    try:
        from aos.alerting_telegram import TelegramAlertProvider
        return TelegramAlertProvider(bot_token=bot_token, chat_id=chat_id)
    except Exception as e:
        logger.warning("Failed to create Telegram provider: %s", e)
        return None


def send_approval_notification(approvals: list[dict[str, Any]]) -> bool:
    """Send approval summary via Telegram.

    Parameters
    ----------
    approvals:
        List of approval dicts with keys: id, action, agent_id, risk_assessment, rationale

    Returns
    -------
    True if sent successfully, False otherwise.
    """
    if not approvals:
        return False

    provider = _get_telegram_provider()
    if not provider:
        logger.info("Telegram not configured, skipping approval notification")
        return False

    # Build message
    lines = ["📋 *AOS Approval Queue*\n"]
    lines.append(f"*{len(approvals)} pending approval(s)*\n")

    for i, item in enumerate(approvals, 1):
        item_id = item.get("id", "?")
        action = item.get("action", item.get("title", "Unknown"))
        agent = item.get("agent_id", "Unknown")
        risk = item.get("risk_assessment", "N/A")

        lines.append(f"*{i}. [{item_id}]* {action}")
        lines.append(f"   Agent: {agent}")
        lines.append(f"   Risk: {risk}")
        lines.append("")

    lines.append("Approve: `python -m aos approvals approve-all`")
    lines.append("Reject: `python -m aos approvals reject-all`")
    lines.append("List: `python -m aos approvals list`")

    text = "\n".join(lines)

    try:
        import httpx
        url = f"https://api.telegram.org/bot{provider.bot_token}/sendMessage"
        resp = httpx.post(
            url,
            json={
                "chat_id": provider.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            logger.info("Approval notification sent via Telegram")
            return True
        else:
            logger.warning("Telegram send failed: %s", resp.status_code)
            return False
    except Exception as e:
        logger.warning("Failed to send Telegram notification: %s", e)
        return False


def send_run_summary(
    steps_completed: int,
    total_steps: int,
    errors: list[str],
    approvals_pending: int,
    venture: str = "netso",
) -> bool:
    """Send run summary via Telegram.

    Parameters
    ----------
    steps_completed:
        Number of steps that completed successfully.
    total_steps:
        Total number of steps in the cycle.
    errors:
        List of error messages.
    approvals_pending:
        Number of pending approvals.
    venture:
        Venture name.

    Returns
    -------
    True if sent successfully, False otherwise.
    """
    provider = _get_telegram_provider()
    if not provider:
        return False

    status = "✅" if not errors else "⚠️"
    lines = [f"{status} *AOS Run Complete*\n"]
    lines.append(f"*Venture:* {venture}")
    lines.append(f"*Steps:* {steps_completed}/{total_steps}")

    if errors:
        lines.append(f"*Errors:* {len(errors)}")
        for err in errors[:3]:
            lines.append(f"  - {err[:80]}")

    if approvals_pending:
        lines.append(f"\n*Approvals pending:* {approvals_pending}")
        lines.append("Run `python -m aos approvals list` to review")

    text = "\n".join(lines)

    try:
        import httpx
        url = f"https://api.telegram.org/bot{provider.bot_token}/sendMessage"
        resp = httpx.post(
            url,
            json={
                "chat_id": provider.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10.0,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Failed to send run summary: %s", e)
        return False
