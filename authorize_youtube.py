#!/usr/bin/env python3
"""One-time local helper to obtain a YouTube OAuth refresh token.

Run this script ON YOUR OWN MACHINE, never in GitHub Actions. It opens a
browser so you can sign in as the owner of the Hacktic YouTube channel and
authorize the read-only YouTube scopes. It then prints:

  1. the refresh token (paste into a GitHub secret), and
  2. the channel ID(s) owned by the signed-in account.

Usage:

    python authorize_youtube.py [path/to/client_secret.json]

The OAuth client details come from the downloaded "Desktop app" client secret
file (default: client_secret.json). If that file is not present, the script
falls back to the YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET environment
variables, and prompts for them if they are missing.

WARNING: A refresh token is a long-lived credential. Paste it into GitHub
repository secrets and NEVER commit it, print it in logs, or share it.
"""

import os
import sys
import webbrowser
import wsgiref.simple_server
from urllib.parse import parse_qs

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"


def get_value(name):
    value = os.environ.get(name, "").strip()
    if not value:
        value = input(f"{name}: ").strip()
    if not value:
        raise SystemExit(f"{name} is required.")
    return value


def build_flow(argv):
    secrets_path = argv[1] if len(argv) > 1 else "client_secret.json"
    if os.path.exists(secrets_path):
        print(f"Using OAuth client from {secrets_path}")
        return InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)

    client_id = get_value("YOUTUBE_CLIENT_ID")
    client_secret = get_value("YOUTUBE_CLIENT_SECRET")
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": ["http://localhost"],
        }
    }
    return InstalledAppFlow.from_client_config(client_config, SCOPES)


class _CallbackHandler:
    def __init__(self):
        self.error = None
        self.code = None
        self.state = None

    def __call__(self, environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""))
        self.error = query.get("error", [None])[0]
        self.code = query.get("code", [None])[0]
        self.state = query.get("state", [None])[0]
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [
            b"<!doctype html><title>Hacktic authorization</title>"
            b"<p>Authorization complete. You can close this tab and return "
            b"to the terminal.</p>"
        ]


def main():
    print(
        "Local one-time YouTube authorization.\n"
        "This will sign in to the Hacktic YouTube account.\n"
    )
    flow = build_flow(sys.argv)

    handler = _CallbackHandler()
    server = wsgiref.simple_server.make_server("localhost", 0, handler)
    port = server.server_port
    flow.redirect_uri = f"http://localhost:{port}/"

    auth_url, expected_state = flow.authorization_url(
        access_type="offline", prompt="consent"
    )

    print()
    print("Open this URL in your browser to authorize Hacktic:")
    print()
    print(auth_url)
    print()
    try:
        if webbrowser.open(auth_url, new=2):
            print("A browser tab was opened. If nothing appeared, copy the URL above.")
        else:
            print("Could not open a browser automatically. Copy the URL above.")
    except Exception:
        print("Could not open a browser automatically. Copy the URL above.")
    print()
    print("Waiting for authorization (the page will redirect to localhost)...")

    server.handle_request()
    server.server_close()

    if handler.error:
        raise SystemExit(f"Authorization was denied or failed: {handler.error}")
    if handler.code is None:
        raise SystemExit("No authorization code was received.")
    if expected_state and handler.state != expected_state:
        raise SystemExit("OAuth state mismatch; please retry.")

    flow.fetch_token(code=handler.code)
    credentials = flow.credentials

    print()
    print("=" * 72)
    print("YOUR REFRESH TOKEN")
    print("=" * 72)
    print(credentials.refresh_token)
    print("=" * 72)
    print()
    print("Store this value as the YOUTUBE_REFRESH_TOKEN GitHub secret.")
    print("NEVER commit this token or share it.")
    print()

    try:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", credentials=credentials)
        response = youtube.channels().list(part="id,snippet", mine=True).execute()
        items = response.get("items") or []
        if items:
            print("Channels owned by this account:")
            for item in items:
                title = item.get("snippet", {}).get("title", "?")
                channel_id = item.get("id", "?")
                print(f"  {title}  ->  {channel_id}")
        else:
            print("No channels found for this account.")
    except Exception as exc:  # channel listing is optional; token is the goal
        print(f"(Could not list channels: {exc})", file=sys.stderr)


if __name__ == "__main__":
    main()
