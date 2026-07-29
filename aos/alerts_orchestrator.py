"""Alerts orchestrator — calls evaluator THEN sends alerts.

The evaluator (validate_output) is a pure function. This module wraps it
and adds the side effect of sending Telegram alerts when violations occur.
This keeps the evaluator testable and free of import/side-effect concerns.
"""
from __future__ import annotations
import logging
import os
from aos.evaluator import ValidationResult, validate_output

logger = logging.getLogger("aos.alerts_orchestrator")


def validate_and_alert(
    output: dict,
    agent_id: str,
    constants: dict | None = None,
) -> ValidationResult:
    """Run evaluator, then send Telegram alerts for any violations.

    This is the recommended entry point for harness cycles that want
    alerting. It preserves the evaluator as a pure function while adding
    the alerting side effect in a separate, testable layer.
    """
    result = validate_output(output, agent_id, constants)

    if not result.passed:
        _send_alerts(result, agent_id)

    return result


def _send_alerts(result: ValidationResult, agent_id: str) -> None:
    """Send Telegram alerts for each violation."""
    try:
        from aos.alerting_telegram import TelegramAlertProvider
        token = os.environ.get("AOS_TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("AOS_TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            logger.debug("Telegram not configured, skipping alerts")
            return

        provider = TelegramAlertProvider(bot_token=token, chat_id=chat_id)
        venture = agent_id.split("-")[1].lower() if "-" in agent_id else "unknown"

        for violation in result.violations:
            provider.send(
                level="critical",
                source="evaluator",
                message=violation,
                venture=venture,
            )
    except Exception as e:
        logger.error(f"Alert delivery failed: {e}")
