"""Spotify metadata resolver (ported & repackaged from Trackster2 main.py).

Reused: get_spotify_client (reads SPOTIPY_* from the settings store or env),
search_spotify, get_track_info (with exponential-backoff retry),
get_playlist_info, get_album_info. Deduplication across runs is handled by the
Trackpod pipeline (SourceItem/Track), so the Trackster2 ``add_synced`` /
``get_synced_ids`` helpers are dropped here. UI-agnostic.
"""

from __future__ import annotations

import logging
import os

import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

log = logging.getLogger(__name__)


def get_spotify_client(store=None):
    """Return a Spotify API client, or None when credentials are missing.

    ``store`` is an optional key/value store (core.db.SettingsStore) checked
    before environment variables, mirroring the original ordering.
    """
    def _get(key: str) -> str:
        if store is not None:
            val = store.get(key)
            if val:
                return val
        return os.getenv(key, "")

    client_id = _get("SPOTIPY_CLIENT_ID")
    client_secret = _get("SPOTIPY_CLIENT_SECRET")
    if not client_id or not client_secret:
        log.warning("Spotify API credentials missing; continuing without metadata.")
        return None
    try:
        manager = SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
        return spotipy.Spotify(client_credentials_manager=manager)
    except Exception as e:
        log.error("Failed to connect to Spotify API: %s", e)
        return None


def search_spotify(search_term: str, sp):
    """Return the Spotify track share URL for the best match, or None."""
    if sp is None:
        return None
    search_results = sp.search(search_term, type="track", limit=1)
    if search_results["tracks"]["total"] == 0:
        return None
    return search_results["tracks"]["items"][0]["external_urls"]["spotify"]


def _track_to_info(track: dict) -> dict:
    """Normalize a Spotify track envelope into a metadata dict."""
    return {
        "artist_name": track["artists"][0]["name"],
        "track_title": track["name"],
        "track_number": track.get("track_number", 0),
        "isrc": (
            track["external_ids"].get("isrc")
            if track.get("external_ids") else ""
        ),
        "album_art": track["album"]["images"][1]["url"],
        "album_name": track["album"]["name"],
        "release_date": track["album"].get("release_date", ""),
        "artists": [a["name"] for a in track["artists"]],
    }


def get_track_info(track_url: str, sp,
                   max_retries: int = 3, initial_timeout: int = 1) -> dict | None:
    """Get track metadata from Spotify, with exponential-backoff retries."""
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            # make sure the URL is reachable before parsing (a valid track id
            # still parses fine, but this preserves the original guard)
            res = requests.get(track_url, timeout=15)
            if res.status_code != 200:
                raise ValueError(f"Invalid Spotify track URL: {track_url}")
            return _track_to_info(sp.track(track_url))
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries:
                wait = initial_timeout * (2 ** attempt)
                log.info("get_track_info attempt %d failed; retrying in %ss: %s",
                         attempt + 1, wait, exc)
                import time
                time.sleep(wait)
    log.error("Failed to get track info after %d attempts: %s",
              max_retries + 1, last_exception)
    return None


def get_playlist_info(sp_playlist: str, sp) -> list[dict]:
    """Return metadata dicts for every track in a public Spotify playlist."""
    res = requests.get(sp_playlist, timeout=15)
    if res.status_code != 200:
        raise ValueError("Invalid Spotify playlist URL")
    pl = sp.playlist(sp_playlist)
    if not pl.get("public"):
        raise ValueError(
            "Can't download private playlists. Change your playlist's state to public."
        )
    playlist = sp.playlist_tracks(sp_playlist)
    items = playlist["items"]
    while playlist["next"]:
        playlist = sp.next(playlist)
        items.extend(playlist["items"])

    tracks = [i["track"] for i in items if i.get("track") and i["track"].get("id")]
    infos = []
    for track in tracks:
        url = f"https://open.spotify.com/track/{track['id']}"
        info = get_track_info(url, sp)
        if info:
            infos.append(info)
    return infos


def get_album_info(sp_album: str, sp) -> list[dict]:
    """Return metadata dicts for each track in a Spotify album."""
    res = requests.get(sp_album, timeout=15)
    if res.status_code != 200:
        raise ValueError("Invalid Spotify album URL")

    playlist = sp.album_tracks(sp_album)
    items = playlist["items"]
    while playlist["next"]:
        playlist = sp.next(playlist)
        items.extend(playlist["items"])

    infos = []
    for track in items:
        url = f"https://open.spotify.com/track/{track['id']}"
        info = get_track_info(url, sp)
        if info:
            infos.append(info)
    return infos
