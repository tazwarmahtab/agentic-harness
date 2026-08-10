"""Data adapter for AOS harnesses.

Supports both file-based and API-based data sources.
API adapters are used when configured (env vars set), otherwise falls back to file-based.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Data files to load (relative to venture data directory)
DATA_FILES = {
    "calendar": "calendar.json",
    "email": "email.json",
    "crm": "deals.json",
    "finance": None,  # Special: load from seed/ directory
    "projects": "projects.json",
    "comms": "comms.json",
    "knowledge": "knowledge.json",
    "founder_context": "founder_context.json",
}


class FileDataAdapter:
    """Reads JSON data files from a venture data directory."""

    def __init__(self, data_dir: Path, venture_dir: Path | None = None):
        """
        Parameters
        ----------
        data_dir:
            Path to the data directory (e.g., aos/ventures/netso/data/).
        venture_dir:
            Path to the venture directory (e.g., aos/ventures/netso/).
            Used for loading seed data (billing, generation, deals).
        """
        self.data_dir = data_dir
        self.venture_dir = venture_dir or data_dir.parent

    def load_all(self) -> dict[str, Any]:
        """Load all data sources and return a context dict."""
        context: dict[str, Any] = {}

        for source, filename in DATA_FILES.items():
            try:
                data = self._load_source(source, filename)
                if data:
                    context[source] = data
            except Exception as e:
                logger.warning("Failed to load %s: %s", source, e)
                context[source] = {"error": str(e)}

        return context

    def load_source(self, source: str) -> dict[str, Any] | None:
        """Load a specific data source."""
        filename = DATA_FILES.get(source)
        return self._load_source(source, filename)

    def _load_source(
        self, source: str, filename: str | None
    ) -> dict[str, Any] | None:
        """Load a single data source from file."""
        if source == "finance":
            return self._load_finance()

        if not filename:
            return None

        filepath = self.data_dir / filename
        if not filepath.exists():
            logger.debug("Data file not found: %s", filepath)
            return None

        with open(filepath) as f:
            raw = json.load(f)

        # Extract data payload if wrapped in {last_updated, data} format
        if isinstance(raw, dict) and "data" in raw:
            return raw["data"]
        return raw

    def _load_finance(self) -> dict[str, Any] | None:
        """Load finance data from seed files."""
        context: dict[str, Any] = {}

        # Load billing
        billing_path = self.venture_dir / "seed" / "billing.json"
        if billing_path.exists():
            with open(billing_path) as f:
                context["billing"] = json.load(f)

        # Load generation
        generation_path = self.venture_dir / "seed" / "generation.json"
        if generation_path.exists():
            with open(generation_path) as f:
                context["generation"] = json.load(f)

        # Load constants
        constants_path = self.venture_dir / "seed" / "constants.json"
        if constants_path.exists():
            with open(constants_path) as f:
                raw = json.load(f)
                context["constants"] = raw.get("financial_constants", raw)

        return context if context else None


def _get_api_adapter(source: str, venture_dir: Path) -> Any | None:
    """Get API adapter for a data source if configured."""
    try:
        if source == "calendar" and os.getenv("GOOGLE_CREDENTIALS_PATH"):
            from aos.adapters.google_calendar import GoogleCalendarAdapter

            credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH"))
            token_path = Path(os.getenv("GOOGLE_CALENDAR_TOKEN_PATH", "token_calendar.json"))
            cache_dir = venture_dir / "cache"
            return GoogleCalendarAdapter(
                credentials_path=credentials_path,
                token_path=token_path,
                cache_dir=cache_dir,
            )

        if source == "email" and os.getenv("GOOGLE_CREDENTIALS_PATH"):
            from aos.adapters.gmail import GmailAdapter

            credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH"))
            token_path = Path(os.getenv("GMAIL_TOKEN_PATH", "token_gmail.json"))
            cache_dir = venture_dir / "cache"
            return GmailAdapter(
                credentials_path=credentials_path,
                token_path=token_path,
                cache_dir=cache_dir,
            )

        if source == "crm":
            from aos.adapters.crm_adapter import CRMAdapter, FileCRMAdapter

            crm_type = os.getenv("CRM_TYPE", "file")
            if crm_type != "file":
                return CRMAdapter.create(
                    crm_type=crm_type,
                    api_key=os.getenv("CRM_API_KEY", ""),
                )
            # File-based CRM
            deals_path = venture_dir / "deals.json"
            if deals_path.exists():
                return FileCRMAdapter(deals_path=deals_path)

    except Exception as e:
        logger.debug("No API adapter for %s: %s", source, e)

    return None


def load_venture_data(venture_dir: Path) -> dict[str, Any]:
    """Convenience function to load all data for a venture.

    Uses API adapters when configured, falls back to file-based.

    Parameters
    ----------
    venture_dir:
        Path to the venture directory (e.g., aos/ventures/netso/).

    Returns
    -------
    Dict with keys: calendar, email, crm, finance, projects, comms, knowledge, founder_context.
    """
    data_dir = venture_dir / "data"
    adapter = FileDataAdapter(data_dir=data_dir, venture_dir=venture_dir)
    context = adapter.load_all()

    # Override with API adapters when configured
    for source in ["calendar", "email", "crm"]:
        api_adapter = _get_api_adapter(source, venture_dir)
        if api_adapter:
            try:
                api_data = api_adapter.load() if hasattr(api_adapter, "load") else api_adapter.fetch_deals() if source == "crm" else None
                if api_data:
                    context[source] = api_data
                    logger.info("Using API adapter for %s", source)
            except Exception as e:
                logger.warning("API adapter failed for %s: %s", source, e)

    return context
