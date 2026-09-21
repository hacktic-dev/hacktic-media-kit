#!/usr/bin/env python3
"""Update stats.json with current Hacktic YouTube channel statistics.

This script is intended to run from GitHub Actions on a schedule. It reads all
credentials from environment variables only, fetches public channel statistics
from the YouTube Data API v3 and the rolling 28-day views from the YouTube
Analytics API, then writes stats.json at the repository root.

It never prints or stores secrets or tokens, and it only rewrites stats.json
when the headline numbers have actually changed.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

STATS_PATH = "stats.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

TOKEN_URI = "https://oauth2.googleapis.com/token"

ANALYTICS_MAX_DAYS_BACK = 14

# Temporary override for the 28-day views metric.
# The YouTube Analytics API lags a day or two, so immediately after a traffic
# spike the "last 28 days" figure can temporarily read too low. While today's
# date is on or before VIEWS_OVERRIDE_UNTIL, use VIEWS_OVERRIDE_VALUE instead of
# the API number. After that date it disengages automatically and the live API
# value is used again. To remove the override early, delete these two lines.
VIEWS_OVERRIDE_UNTIL = "2026-09-20"
VIEWS_OVERRIDE_VALUE = 119500

# The three "Proven track record" videos shown on the site, keyed by the
# element IDs in index.html. Their lifetime view counts come from the Data API,
# which updates near-real-time (no Analytics lag).
TRACK_VIDEOS = {
    "track-playstation": "yIkDdE-utjA",  # How to create a PS1 style horror game in Unity
    "track-blender": "8--xYWCY_bc",      # How to make PS1 style models in Blender
    "track-voxel": "WKTZgf7ZDGs",        # Retro low res pixelated look in Unity
}


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def build_credentials():
    client_id = require_env("YOUTUBE_CLIENT_ID")
    client_secret = require_env("YOUTUBE_CLIENT_SECRET")
    refresh_token = require_env("YOUTUBE_REFRESH_TOKEN")
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def resolve_channel_id(youtube, channel_id):
    """Return the channel ID to use, discovering it if none was provided."""
    if channel_id:
        return channel_id

    response = youtube.channels().list(part="id", mine=True).execute()
    items = response.get("items") or []
    if not items:
        raise RuntimeError(
            "No YOUTUBE_CHANNEL_ID provided and no channel found for the "
            "authenticated account."
        )
    resolved = items[0]["id"]
    print(f"Using channel discovered from the authenticated account: {resolved}")
    return resolved


def get_channel_stats(youtube, channel_id):
    """Return (subscribers, lifetime_views) from the Data API v3."""
    response = youtube.channels().list(part="statistics", id=channel_id).execute()
    items = response.get("items") or []
    if not items:
        raise RuntimeError(f"No channel found for channel ID {channel_id!r}")

    statistics = items[0].get("statistics") or {}
    if "subscriberCount" not in statistics or "viewCount" not in statistics:
        raise RuntimeError(
            "Channel statistics are not publicly available "
            "(subscriberCount or viewCount missing)."
        )

    subscribers = int(statistics["subscriberCount"])
    lifetime_views = int(statistics["viewCount"])
    return subscribers, lifetime_views


def get_track_video_views(youtube):
    """Return {label: view_count} for each configured track-record video."""
    ids = list(TRACK_VIDEOS.values())
    response = youtube.videos().list(part="statistics", id=",".join(ids)).execute()
    by_id = {}
    for item in response.get("items") or []:
        view_count = (item.get("statistics") or {}).get("viewCount")
        if view_count is not None:
            by_id[item["id"]] = int(view_count)

    missing = [label for label, vid in TRACK_VIDEOS.items() if vid not in by_id]
    if missing:
        raise RuntimeError(
            f"Could not retrieve view counts for track videos: {', '.join(missing)}"
        )

    return {label: by_id[vid] for label, vid in TRACK_VIDEOS.items()}


def query_analytics_views(analytics, channel_id, start, end):
    """Return total views for the period, or None if no data is available yet."""
    try:
        response = (
            analytics.reports()
            .query(
                ids=f"channel=={channel_id}",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views",
            )
            .execute()
        )
    except HttpError as exc:
        # A 400 here usually means the requested range has no data yet.
        # Let the caller retry with an earlier end date.
        if exc.resp.status == 400:
            return None
        raise

    rows = response.get("rows")
    if not rows:
        return None

    try:
        return int(rows[0][0])
    except (IndexError, TypeError, ValueError):
        return None


def get_latest_28_day_views(analytics, channel_id):
    """Return (views, end_date) for the latest populated rolling 28-day window.

    YouTube Analytics data lags behind the current date, so instead of assuming
    yesterday has data, walk backwards until a populated window is found.
    """
    today = date.today()
    for days_back in range(1, ANALYTICS_MAX_DAYS_BACK + 1):
        end = today - timedelta(days=days_back)
        start = end - timedelta(days=27)
        views = query_analytics_views(analytics, channel_id, start, end)
        if views is not None:
            if days_back > 1:
                print(
                    f"Analytics not yet available for the most recent days; "
                    f"using the 28-day window ending {end.isoformat()}."
                )
            return views, end

    raise RuntimeError(
        "Could not find a populated 28-day window within the last "
        f"{ANALYTICS_MAX_DAYS_BACK} days."
    )


def load_existing(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_stats(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main():
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID", "").strip()
    credentials = build_credentials()

    try:
        youtube = build("youtube", "v3", credentials=credentials)
        analytics = build("youtubeAnalytics", "v2", credentials=credentials)

        channel_id = resolve_channel_id(youtube, channel_id)
        subscribers, lifetime_views = get_channel_stats(youtube, channel_id)
        views_28_days, analytics_end = get_latest_28_day_views(analytics, channel_id)
        track_video_views = get_track_video_views(youtube)

        if date.today() <= date.fromisoformat(VIEWS_OVERRIDE_UNTIL):
            print(
                f"Holding 28-day views at {VIEWS_OVERRIDE_VALUE} "
                f"(override until {VIEWS_OVERRIDE_UNTIL})."
            )
            views_28_days = VIEWS_OVERRIDE_VALUE
    except RefreshError as exc:
        print(
            "OAuth refresh failed. Verify YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET "
            "and YOUTUBE_REFRESH_TOKEN.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    except HttpError as exc:
        reason = getattr(exc.resp, "reason", "unknown")
        status = getattr(exc.resp, "status", "unknown")
        print(f"YouTube API request failed (HTTP {status} {reason}).", file=sys.stderr)
        raise SystemExit(1) from exc
    except (RuntimeError, ValueError) as exc:
        print(f"Failed to retrieve channel statistics: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    new_stats = {
        "subscribers": subscribers,
        "views28Days": views_28_days,
        "lifetimeViews": lifetime_views,
        "analyticsEndDate": analytics_end.isoformat(),
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "videos": track_video_views,
    }

    existing = load_existing(STATS_PATH)
    if existing and all(
        existing.get(key) == new_stats[key]
        for key in ("subscribers", "views28Days", "lifetimeViews", "videos")
    ):
        print("Headline stats unchanged; not rewriting stats.json.")
        return

    write_stats(STATS_PATH, new_stats)
    print(f"Wrote {STATS_PATH}: {json.dumps(new_stats)}")


if __name__ == "__main__":
    main()
