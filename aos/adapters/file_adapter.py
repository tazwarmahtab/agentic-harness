"""File-based data adapter for AOS harnesses.

Reads JSON data files from the venture data directory and returns
context dicts for injection into agent prompts.
"""

from __future__ import annotations

import json
import logging
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


def load_venture_data(venture_dir: Path) -> dict[str, Any]:
    """Convenience function to load all data for a venture.

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
    return adapter.load_all()
