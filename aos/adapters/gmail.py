"""Gmail adapter for AOS harnesses.

Fetches recent emails from Gmail API and returns structured data
for injection into agent prompts.

Requires:
    - google-api-python-client
    - google-auth-oauthlib
    - credentials.json from Google Cloud Console
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aos.adapters.api_adapter import BaseAPIAdapter

logger = logging.getLogger(__name__)


class GmailAdapter(BaseAPIAdapter):
    """Fetches emails from Gmail API."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(
        self,
        credentials_path: Path | None = None,
        token_path: Path | None = None,
        cache_dir: Path | None = None,
        max_emails: int = 20,
        days_back: int = 7,
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
        max_emails:
            Maximum number of emails to fetch.
        days_back:
            Number of days back to fetch emails.
        """
        self.credentials_path = credentials_path or Path("credentials.json")
        self.token_path = token_path or Path("token_gmail.json")
        self.max_emails = max_emails
        self.days_back = days_back

        cache_dir = cache_dir or Path("cache")
        super().__init__(cache_dir=cache_dir, cache_ttl_seconds=300)

    def get_cache_key(self) -> str:
        return "email"

    def fetch(self) -> dict[str, Any]:
        """Fetch emails from Gmail API."""
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
        service = build("gmail", "v1", credentials=creds)

        # Calculate time range
        after_date = (datetime.now() - timedelta(days=self.days_back)).strftime(
            "%Y/%m/%d"
        )

        # Fetch email list
        query = f"after:{after_date}"
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=self.max_emails)
            .execute()
        )

        messages = results.get("messages", [])

        # Fetch each email
        emails = []
        for msg in messages[: self.max_emails]:
            try:
                message = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="full")
                    .execute()
                )
                emails.append(self._parse_email(message))
            except Exception as e:
                logger.warning("Failed to fetch email %s: %s", msg["id"], e)

        return {
            "unread_count": sum(1 for e in emails if not e.get("is_read")),
            "important_threads": [
                e for e in emails if e.get("requires_action")
            ],
            "recent_sent": [],  # Would need separate query for sent
            "all_recent": emails,
            "source": "gmail",
            "fetched_at": datetime.now().isoformat(),
        }

    def _parse_email(self, message: dict) -> dict[str, Any]:
        """Parse a Gmail message into structured format."""
        headers = {h["name"].lower(): h["value"] for h in message["payload"]["headers"]}

        # Get snippet (preview)
        snippet = message.get("snippet", "")

        # Determine if requires action
        requires_action = False
        action_keywords = ["action required", "please", "deadline", "urgent", "follow up"]
        if any(kw in snippet.lower() for kw in action_keywords):
            requires_action = True

        # Get date
        date_str = headers.get("date", "")
        try:
            date_obj = datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S")
            date_formatted = date_obj.strftime("%Y-%m-%d")
        except Exception:
            date_formatted = date_str[:10] if date_str else ""

        return {
            "id": message.get("id", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", "No subject"),
            "date": date_formatted,
            "summary": snippet[:200] if snippet else "",
            "requires_action": requires_action,
            "is_read": "UNREAD" not in message.get("labelIds", []),
            "labels": message.get("labelIds", []),
        }
