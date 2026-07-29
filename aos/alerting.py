"""Structured alerting for financial breaches and system events."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aos.alerting")

@dataclass(frozen=True)
class Alert:
    level: str  # "critical", "warning", "info"
    source: str  # "evaluator", "graph", "approval", "system"
    message: str
    venture: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

class AlertingService:
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url
        self._sent: list[Alert] = []

    def send(self, alert: Alert) -> None:
        """Send alert via webhook (if configured) and always log."""
        self._sent.append(alert)
        log_fn = logger.critical if alert.level == "critical" else logger.warning
        log_fn(f"[{alert.level.upper()}] {alert.source}: {alert.message} (venture={alert.venture})")
        if self.webhook_url:
            self._send_webhook(alert)

    def _send_webhook(self, alert: Alert) -> None:
        try:
            import httpx
            payload = {
                "text": f"[{alert.level.upper()}] {alert.source}: {alert.message}",
                "venture": alert.venture,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            httpx.post(self.webhook_url, json=payload, timeout=10.0)
        except Exception as e:
            logger.error(f"Webhook delivery failed: {e}")

    @property
    def sent(self) -> list[Alert]:
        return list(self._sent)
