"""Generic CRM adapter for AOS harnesses.

Provides a base class for CRM integrations with pluggable backends.
Concrete implementations for Salesforce, HubSpot, etc. can be added later.

Current implementation reads from deals.json (file-based).
API-based backends can be added by subclassing BaseCRMAdapter.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BaseCRMAdapter(ABC):
    """Abstract base class for CRM adapters."""

    @abstractmethod
    def fetch_deals(self) -> list[dict[str, Any]]:
        """Fetch deals from the CRM. Returns list of deal dicts."""
        ...

    @abstractmethod
    def fetch_contacts(self) -> list[dict[str, Any]]:
        """Fetch contacts from the CRM. Returns list of contact dicts."""
        ...


class FileCRMAdapter(BaseCRMAdapter):
    """File-based CRM adapter (reads from deals.json)."""

    def __init__(self, deals_path: Path):
        """
        Parameters
        ----------
        deals_path:
            Path to deals.json file.
        """
        self.deals_path = deals_path

    def fetch_deals(self) -> list[dict[str, Any]]:
        """Read deals from JSON file."""
        if not self.deals_path.exists():
            return []

        try:
            with open(self.deals_path) as f:
                data = json.load(f)
            return data.get("deals", [])
        except Exception as e:
            logger.warning("Failed to read deals: %s", e)
            return []

    def fetch_contacts(self) -> list[dict[str, Any]]:
        """Contacts not tracked in file-based mode."""
        return []


class SalesforceCRMAdapter(BaseCRMAdapter):
    """Salesforce CRM adapter (placeholder for future implementation)."""

    def __init__(self, instance_url: str, access_token: str):
        self.instance_url = instance_url
        self.access_token = access_token

    def fetch_deals(self) -> list[dict[str, Any]]:
        """Fetch opportunities from Salesforce."""
        # TODO: Implement Salesforce API call
        raise NotImplementedError("Salesforce adapter not yet implemented")

    def fetch_contacts(self) -> list[dict[str, Any]]:
        """Fetch contacts from Salesforce."""
        # TODO: Implement Salesforce API call
        raise NotImplementedError("Salesforce adapter not yet implemented")


class HubSpotCRMAdapter(BaseCRMAdapter):
    """HubSpot CRM adapter (placeholder for future implementation)."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_deals(self) -> list[dict[str, Any]]:
        """Fetch deals from HubSpot."""
        # TODO: Implement HubSpot API call
        raise NotImplementedError("HubSpot adapter not yet implemented")

    def fetch_contacts(self) -> list[dict[str, Any]]:
        """Fetch contacts from HubSpot."""
        # TODO: Implement HubSpot API call
        raise NotImplementedError("HubSpot adapter not yet implemented")


class PipedriveCRMAdapter(BaseCRMAdapter):
    """Pipedrive CRM adapter (placeholder for future implementation)."""

    def __init__(self, api_token: str):
        self.api_token = api_token

    def fetch_deals(self) -> list[dict[str, Any]]:
        """Fetch deals from Pipedrive."""
        # TODO: Implement Pipedrive API call
        raise NotImplementedError("Pipedrive adapter not yet implemented")

    def fetch_contacts(self) -> list[dict[str, Any]]:
        """Fetch contacts from Pipedrive."""
        # TODO: Implement Pipedrive API call
        raise NotImplementedError("Pipedrive adapter not yet implemented")


class CRMAdapter:
    """Factory for creating CRM adapters based on configuration."""

    @staticmethod
    def create(crm_type: str = "file", **kwargs) -> BaseCRMAdapter:
        """Create a CRM adapter based on type.

        Parameters
        ----------
        crm_type:
            Type of CRM: "file", "salesforce", "hubspot", "pipedrive"
        **kwargs:
            Additional arguments for the specific CRM adapter.
        """
        if crm_type == "file":
            return FileCRMAdapter(**kwargs)
        elif crm_type == "salesforce":
            return SalesforceCRMAdapter(**kwargs)
        elif crm_type == "hubspot":
            return HubSpotCRMAdapter(**kwargs)
        elif crm_type == "pipedrive":
            return PipedriveCRMAdapter(**kwargs)
        else:
            raise ValueError(f"Unknown CRM type: {crm_type}")
