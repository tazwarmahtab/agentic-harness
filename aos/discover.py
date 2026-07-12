"""Venture discovery — find and enumerate all ventures in the workspace."""

from __future__ import annotations

import logging
from pathlib import Path

from aos.loader import load_venture
from aos.schemas.venture import Venture

logger = logging.getLogger(__name__)


def discover_ventures(ventures_dir: Path | None = None) -> list[tuple[Path, Venture]]:
    """Discover all venture.yml files under ventures/ directory.

    Returns list of (path, Venture) tuples sorted by venture name.
    """
    if ventures_dir is None:
        ventures_dir = Path(__file__).parent / "ventures"

    # Reject traversal in user-supplied directories
    if ".." in ventures_dir.parts:
        logger.warning("Rejected ventures directory with traversal: %s", ventures_dir)
        return []

    if not ventures_dir.exists():
        return []

    results: list[tuple[Path, Venture]] = []
    for venture_path in sorted(ventures_dir.glob("*/venture.yml")):
        try:
            venture = load_venture(venture_path)
            results.append((venture_path, venture))
        except Exception:
            continue

    return results


def find_venture(name_or_id: str, ventures_dir: Path | None = None) -> tuple[Path, Venture] | None:
    """Find a venture by name or ID (case-insensitive).

    Accepts:
      - "netso" or "VEN-NETSO-001"
      - "Netso Energy" (full name)
    """
    all_ventures = discover_ventures(ventures_dir)
    query = name_or_id.lower()

    for path, venture in all_ventures:
        if venture.id.lower() == query:
            return path, venture
        if venture.name.lower() == query:
            return path, venture
        if query in venture.name.lower():
            return path, venture
        if query in venture.id.lower():
            return path, venture

    return None
