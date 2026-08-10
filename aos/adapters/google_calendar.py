"""Google Calendar adapter for AOS harnesses.

Fetches events from Google Calendar API and returns structured data
for injection into agent prompts.

Requires:
    - google-api-python-client
    - google-auth-oauthlib
    - credentials.json from Google Cloud Console
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aos.adapters.api_adapter import BaseAPIAdapter

logger = logging.getLogger(__name__)


class GoogleCalendarAdapter(BaseAPIAdapter):
    """Fetches events from Google Calendar API."""

    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(
        self,
        credentials_path: Path | None = None,
        token_path: Path | None = None,
        cache_dir: Path | None = None,
        calendar_id: str = "primary",
        days_ahead: int = 7,
    ):
        """
        Parameters
        ----------
        credentials_path:
            Path to credentials.json from Google Cloud Console.
        token_path:
            Path to store OAuth token (auto-generated if not provided).
        cache_dir:
            Directory for cached API responses.
        calendar_id:
            Google Calendar ID (default: "primary").
        days_ahead:
            Number of days ahead to fetch events.
        """
        self.credentials_path = credentials_path or Path("credentials.json")
        self.token_path = token_path or Path("token.json")
        self.calendar_id = calendar_id
        self.days_ahead = days_ahead

        cache_dir = cache_dir or Path("cache")
        super().__init__(cache_dir=cache_dir, cache_ttl_seconds=300)

    def get_cache_key(self) -> str:
        return "calendar"

    def fetch(self) -> dict[str, Any]:
        """Fetch events from Google Calendar API."""
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        # Check for credentials
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Credentials not found: {self.credentials_path}\n"
                "Run: python ops/setup-google-auth.py"
            )

        # Load or create token
        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self.token_path), self.SCOPES
            )

        # Refresh or create new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        # Build service
        service = build("calendar", "v3", credentials=creds)

        # Calculate time range
        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=self.days_ahead)).isoformat() + "Z"

        # Fetch events
        events_result = (
            service.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        # Format events
        meetings = []
        deadlines = []

        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))

            formatted = {
                "id": event.get("id", ""),
                "title": event.get("summary", "No title"),
                "date": start[:10] if start else "",
                "time": start[11:16] if start and "T" in start else "",
                "end_time": end[11:16] if end and "T" in end else "",
                "location": event.get("location", ""),
                "description": event.get("description", ""),
                "attendees": [
                    a.get("email", "")
                    for a in event.get("attendees", [])
                ],
                "link": event.get("htmlLink", ""),
            }

            # Classify as meeting or deadline based on keywords
            title_lower = formatted["title"].lower()
            if any(kw in title_lower for kw in ["deadline", "due", "submit", "review"]):
                deadlines.append(formatted)
            else:
                meetings.append(formatted)

        return {
            "meetings": meetings,
            "deadlines": deadlines,
            "source": "google_calendar",
            "fetched_at": now.isoformat(),
        }
