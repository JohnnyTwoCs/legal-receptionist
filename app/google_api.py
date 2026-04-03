"""
Google Calendar and Sheets API wrapper using OAuth2 credentials.

Works on Render via stored refresh token. Falls back to npx locally.

Setup:
1. Run: python -m app.google_api --auth
2. Copy the refresh token into GOOGLE_REFRESH_TOKEN env var on Render
3. Also set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET on Render
"""

import json
import os
import sys

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
]

# OAuth client credentials loaded from env (set in .env or Render dashboard)
_DEFAULT_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
_DEFAULT_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

_credentials = None
_calendar_service = None
_sheets_service = None
_gmail_service = None


def _get_credentials():
    """Load OAuth2 credentials from env vars or local token file."""
    global _credentials
    if _credentials and _credentials.valid:
        return _credentials

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    # Check for refresh token in env (Render deployment)
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
    client_id = os.environ.get("GOOGLE_CLIENT_ID", _DEFAULT_CLIENT_ID)
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", _DEFAULT_CLIENT_SECRET)

    if refresh_token:
        _credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
        _credentials.refresh(Request())
        return _credentials

    # Check for local token file (dev machine)
    token_path = os.path.join(os.path.dirname(__file__), "..", ".tmp", "google_token.json")
    token_path = os.path.normpath(token_path)
    if os.path.isfile(token_path):
        _credentials = Credentials.from_authorized_user_file(token_path, SCOPES)
        if _credentials and _credentials.expired and _credentials.refresh_token:
            _credentials.refresh(Request())
            # Save refreshed token
            with open(token_path, "w") as f:
                f.write(_credentials.to_json())
        if _credentials and _credentials.valid:
            return _credentials

    return None


def get_calendar_service():
    """Get an authenticated Google Calendar API service."""
    global _calendar_service
    if _calendar_service:
        return _calendar_service

    creds = _get_credentials()
    if not creds:
        return None

    from googleapiclient.discovery import build
    _calendar_service = build("calendar", "v3", credentials=creds)
    return _calendar_service


def get_sheets_service():
    """Get an authenticated Google Sheets API service."""
    global _sheets_service
    if _sheets_service:
        return _sheets_service

    creds = _get_credentials()
    if not creds:
        return None

    from googleapiclient.discovery import build
    _sheets_service = build("sheets", "v4", credentials=creds)
    return _sheets_service


def get_gmail_service():
    """Get an authenticated Gmail API service for sending emails."""
    global _gmail_service
    if _gmail_service:
        return _gmail_service

    creds = _get_credentials()
    if not creds:
        return None

    from googleapiclient.discovery import build
    _gmail_service = build("gmail", "v1", credentials=creds)
    return _gmail_service


def is_available():
    """Check if Google API credentials are configured."""
    return _get_credentials() is not None


def run_auth_flow():
    """Run the one-time OAuth2 authorization flow to get a refresh token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": _DEFAULT_CLIENT_ID,
            "client_secret": _DEFAULT_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    # Set environment variable to allow scope changes without error
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8096, prompt="consent", access_type="offline")

    # Save token locally
    token_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".tmp"))
    os.makedirs(token_dir, exist_ok=True)
    token_path = os.path.join(token_dir, "google_token.json")
    with open(token_path, "w") as f:
        f.write(creds.to_json())

    print(f"\nToken saved to: {token_path}")
    print(f"\n{'=' * 60}")
    print(f"REFRESH TOKEN (copy this to Render env vars):")
    print(f"{'=' * 60}")
    print(f"{creds.refresh_token}")
    print(f"{'=' * 60}")
    print(f"\nSet these env vars on Render:")
    print(f"  GOOGLE_REFRESH_TOKEN = {creds.refresh_token}")
    print(f"  GOOGLE_CLIENT_ID     = {_DEFAULT_CLIENT_ID}")
    print(f"  GOOGLE_CLIENT_SECRET = {_DEFAULT_CLIENT_SECRET}")

    return creds


if __name__ == "__main__":
    if "--auth" in sys.argv:
        run_auth_flow()
    else:
        print("Usage: python -m app.google_api --auth")
        print("  Runs OAuth2 flow and prints refresh token for Render deployment")
