"""Morning brief — daily summary from real cycle data.

Reads from tracing (JSONTracer), approval_queue, and usage tracker
to produce a concise morning summary for the founder.
"""
from __future__ import annotations
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("aos.morning_brief")


def _read_tracing_summary(venture: str) -> dict[str, Any]:
    """Read last cycle's tracing data from JSON tracer output."""
    trace_dir = Path("traces")
    if not trace_dir.exists():
        return {"cycles": 0, "nodes": 0, "violations": 0}

    # Find most recent trace file for this venture
    trace_files = sorted(trace_dir.glob(f"*{venture}*.json"), reverse=True)
    if not trace_files:
        return {"cycles": 0, "nodes": 0, "violations": 0}

    try:
        with open(trace_files[0]) as f:
            data = json.load(f)
        return {
            "cycles": 1,
            "nodes": len(data.get("nodes", [])),
            "violations": sum(
                1 for n in data.get("nodes", [])
                if n.get("status") == "error"
            ),
        }
    except Exception:
        return {"cycles": 0, "nodes": 0, "violations": 0}


def _read_approval_summary() -> dict[str, Any]:
    """Read approval queue status."""
    queue_file = Path("data/approval_queue.json")
    if not queue_file.exists():
        return {"pending": 0, "resolved_today": 0}

    try:
        with open(queue_file) as f:
            items = json.load(f)
        today = date.today().isoformat()
        pending = sum(1 for i in items if i.get("status") == "pending")
        resolved_today = sum(
            1 for i in items
            if i.get("status") in ("approved", "rejected")
            and i.get("decided_at", "").startswith(today)
        )
        return {"pending": pending, "resolved_today": resolved_today}
    except Exception:
        return {"pending": 0, "resolved_today": 0}


def _read_usage_summary() -> dict[str, Any]:
    """Read usage tracker data."""
    usage_file = Path("data/usage_reports.json")
    if not usage_file.exists():
        return {"total_tokens": 0, "est_cost": 0.0}

    try:
        with open(usage_file) as f:
            reports = json.load(f)
        today = date.today().isoformat()
        today_reports = [r for r in reports if r.get("date", "").startswith(today)]
        total_tokens = sum(
            r.get("total_prompt_tokens", 0) + r.get("total_completion_tokens", 0)
            for r in today_reports
        )
        # Rough cost estimate: $3/M input + $15/M output
        est_cost = sum(
            r.get("total_prompt_tokens", 0) * 3.0 / 1_000_000
            + r.get("total_completion_tokens", 0) * 15.0 / 1_000_000
            for r in today_reports
        )
        return {"total_tokens": total_tokens, "est_cost": round(est_cost, 2)}
    except Exception:
        return {"total_tokens": 0, "est_cost": 0.0}


def generate_brief(venture: str = "netso") -> str:
    """Generate morning brief from real system data."""
    today = date.today().isoformat()
    tracing = _read_tracing_summary(venture)
    approvals = _read_approval_summary()
    usage = _read_usage_summary()

    lines = [
        f"☀️ AOS Morning Brief — {today}",
        "",
        f"📊 Venture: {venture.upper()}",
        f"🔄 Cycles run: {tracing['cycles']}",
        f"🤖 Nodes executed: {tracing['nodes']}",
        f"⚠️ Violations: {tracing['violations']}",
        f"📋 Approvals pending: {approvals['pending']}",
        f"✅ Approvals resolved today: {approvals['resolved_today']}",
        f"💰 Tokens used: {usage['total_tokens']:,}" if usage['total_tokens'] else "💰 Tokens used: 0",
        f"💵 Est. cost: ${usage['est_cost']:.2f}" if usage['est_cost'] else "💵 Est. cost: $0.00",
        "",
        "Good morning, Taz. Ready to work.",
    ]

    return "\n".join(lines)


def send_brief_telegram(brief: str) -> bool:
    """Send morning brief via Telegram."""
    try:
        from aos.alerting_telegram import TelegramAlertProvider
        import os
        token = os.environ.get("AOS_TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("AOS_TELEGRAM_CHAT_ID")
        if token and chat_id:
            provider = TelegramAlertProvider(bot_token=token, chat_id=chat_id)
            return provider.send(level="info", source="morning-brief", message=brief, venture="system")
        logger.warning("Telegram not configured, brief not sent")
        return False
    except Exception as e:
        logger.error(f"Failed to send morning brief: {e}")
        return False
