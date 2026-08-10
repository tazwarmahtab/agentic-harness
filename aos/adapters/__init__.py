"""Data adapters for AOS harnesses.

Supports both file-based and API-based data sources:
- FileDataAdapter: reads JSON files from venture data directory
- GoogleCalendarAdapter: fetches from Google Calendar API
- GmailAdapter: fetches from Gmail API
- CRMAdapter: generic CRM adapter with pluggable backends
"""

from aos.adapters.file_adapter import FileDataAdapter, load_venture_data
from aos.adapters.api_adapter import BaseAPIAdapter
from os import getenv

__all__ = [
    "FileDataAdapter",
    "BaseAPIAdapter",
    "load_venture_data",
]

# Lazy imports for API adapters (require google-api-python-client)
def get_google_calendar_adapter(**kwargs):
    """Get Google Calendar adapter if dependencies are available."""
    from aos.adapters.google_calendar import GoogleCalendarAdapter
    return GoogleCalendarAdapter(**kwargs)

def get_gmail_adapter(**kwargs):
    """Get Gmail adapter if dependencies are available."""
    from aos.adapters.gmail import GmailAdapter
    return GmailAdapter(**kwargs)

def get_crm_adapter(crm_type: str = "file", **kwargs):
    """Get CRM adapter by type."""
    from aos.adapters.crm_adapter import CRMAdapter
    return CRMAdapter.create(crm_type=crm_type, **kwargs)
