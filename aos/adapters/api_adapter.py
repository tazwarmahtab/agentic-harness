"""Base API adapter for AOS harnesses.

Provides common patterns for API-based adapters:
- Rate limiting
- Caching to JSON files (fallback)
- Error handling
- Token refresh
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BaseAPIAdapter(ABC):
    """Base class for API-based data adapters."""

    def __init__(
        self,
        cache_dir: Path,
        cache_ttl_seconds: int = 300,  # 5 minutes default
    ):
        """
        Parameters
        ----------
        cache_dir:
            Directory to store cached API responses.
        cache_ttl_seconds:
            Cache time-to-live in seconds. Default 300 (5 minutes).
        """
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def fetch(self) -> dict[str, Any]:
        """Fetch data from the API. Must be implemented by subclasses."""
        ...

    @abstractmethod
    def get_cache_key(self) -> str:
        """Return the cache key for this adapter (e.g., 'calendar', 'email')."""
        ...

    def load(self) -> dict[str, Any] | None:
        """Load data from cache or API.

        Returns cached data if fresh, otherwise fetches from API and updates cache.
        Returns None if both cache and API fail.
        """
        cache_file = self.cache_dir / f"{self.get_cache_key()}.json"

        # Try cache first
        if cache_file.exists():
            try:
                cache_data = self._read_cache(cache_file)
                if cache_data and not self._is_cache_expired(cache_file):
                    logger.debug("Using cached data for %s", self.get_cache_key())
                    return cache_data.get("data")
            except Exception as e:
                logger.warning("Cache read failed for %s: %s", self.get_cache_key(), e)

        # Fetch from API
        try:
            data = self.fetch()
            if data:
                self._write_cache(cache_file, data)
                return data
        except Exception as e:
            logger.warning("API fetch failed for %s: %s", self.get_cache_key(), e)

        # Fall back to stale cache
        if cache_file.exists():
            try:
                cache_data = self._read_cache(cache_file)
                if cache_data:
                    logger.warning("Using stale cache for %s", self.get_cache_key())
                    return cache_data.get("data")
            except Exception as e:
                logger.warning("Stale cache read failed for %s: %s", self.get_cache_key(), e)

        return None

    def _read_cache(self, cache_file: Path) -> dict[str, Any] | None:
        """Read data from cache file."""
        with open(cache_file) as f:
            return json.load(f)

    def _write_cache(self, cache_file: Path, data: dict[str, Any]) -> None:
        """Write data to cache file."""
        cache_data = {
            "cached_at": time.time(),
            "data": data,
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)

    def _is_cache_expired(self, cache_file: Path) -> bool:
        """Check if cache file is expired."""
        try:
            cache_data = self._read_cache(cache_file)
            cached_at = cache_data.get("cached_at", 0)
            return (time.time() - cached_at) > self.cache_ttl
        except Exception:
            return True
