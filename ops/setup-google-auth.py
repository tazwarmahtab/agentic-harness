#!/usr/bin/env python3
"""Google OAuth setup script for AOS.

Authenticates with Google Calendar and Gmail APIs,
saves credentials for use by the adapters.

Usage:
    python ops/setup-google-auth.py

Prerequisites:
    1. Create a Google Cloud project at https://console.cloud.google.com
    2. Enable Calendar API and Gmail API
    3. Create OAuth 2.0 credentials (Desktop app)
    4. Download credentials.json to project root
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def setup_google_auth():
    """Run the Google OAuth setup flow."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Error: google-auth-oauthlib not installed.")
        print("Install with: pip install google-auth-oauthlib")
        return False

    credentials_path = project_root / "credentials.json"
    if not credentials_path.exists():
        print(f"Error: credentials.json not found at {credentials_path}")
        print()
        print("To get credentials.json:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Create or select a project")
        print("3. Enable Calendar API and Gmail API")
        print("4. Go to Credentials > Create Credentials > OAuth 2.0 Client ID")
        print("5. Select 'Desktop app'")
        print("6. Download the JSON file and save as credentials.json")
        return False

    # Scopes for Calendar and Gmail
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]

    print("Google OAuth Setup")
    print("==================")
    print()
    print("This will open a browser window for Google authentication.")
    print("After authorizing, tokens will be saved for AOS to use.")
    print()

    # Run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)

    # Save tokens
    token_calendar = project_root / "token_calendar.json"
    token_gmail = project_root / "token_gmail.json"

    with open(token_calendar, "w") as f:
        f.write(creds.to_json())

    with open(token_gmail, "w") as f:
        f.write(creds.to_json())

    print()
    print("✅ Authentication successful!")
    print(f"   Calendar token: {token_calendar}")
    print(f"   Gmail token: {token_gmail}")
    print()
    print("Add to your .env file:")
    print("   GOOGLE_CREDENTIALS_PATH=credentials.json")
    print("   GOOGLE_CALENDAR_TOKEN_PATH=token_calendar.json")
    print("   GMAIL_TOKEN_PATH=token_gmail.json")

    return True


if __name__ == "__main__":
    success = setup_google_auth()
    sys.exit(0 if success else 1)
