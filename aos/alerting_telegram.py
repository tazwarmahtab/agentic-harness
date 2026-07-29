"""Telegram-specific alert provider with cooldown for duplicate suppression."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("aos.alerting.telegram")

LEVEL_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🟢",
}


@dataclass
class TelegramAlertProvider:
    bot_token: str
    chat_id: str
    cooldown_seconds: int = 300
    _last_sent: dict[str, float] = field(default_factory=dict)

    def send(self, level: str, source: str, message: str, venture: str = "unknown") -> bool:
        """Send alert via Telegram. Returns True if sent, False if cooldown suppressed."""
        key = f"{source}:{message[:50]}"
        now = time.time()

        if key in self._last_sent:
            elapsed = now - self._last_sent[key]
            if elapsed < self.cooldown_seconds:
                logger.debug(f"Cooldown active for {key}, {self.cooldown_seconds - elapsed:.0f}s remaining")
                return False

        emoji = LEVEL_EMOJI.get(level, "⚪")
        text = (
            f"{emoji} *AOS Alert*\n\n"
            f"*Level:* {level.upper()}\n"
            f"*Source:* {source}\n"
            f"*Venture:* {venture}\n\n"
            f"{message}"
        )

        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = httpx.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10.0)
            self._last_sent[key] = now
            logger.info(f"Telegram alert sent: {level} {source}")
            return True
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")
            return False
