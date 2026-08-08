"""Orchestration: turn source URLs into resolved, downloaded tracks.

UI-agnostic. Chain (see PLAN_TRACKPOD §3):

1. ``ingest_source``  -> create a Source + raw items (playlist rows).
2. ``ensure_tracks``  -> resolve each item to a Track row (Saavn -> YouTube).
3. ``download_tracks`` -> download pending Track rows into the library folder.

Dedup key is ``Track.title_id`` = lowercased "artist - title".
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from trackpod.core.models import Source, SourceItem, Track
from trackpod.core.sources import (
    DownloadSong,
    Search,
    find_youtube,
    get_album_info,
    get_apple_playlist,
    get_playlist_info,
    get_spotify_client,
    get_track_info,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kind detection
# ---------------------------------------------------------------------------

def detect_kind(external_url: str) -> str:
    """Map a URL to a source kind: spotify|youtube|apple, else 'artist'."""
    host = (urlparse(external_url).hostname or "").lower()
    if "spotify" in host:
        return "spotify"
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if "music.apple.com" in host or "itunes.apple.com" in host:
        return "apple"
    return "artist"


# ---------------------------------------------------------------------------
# Step 1: ingest
# ---------------------------------------------------------------------------

def _fetch_items(kind: str, external_url: str, sp) -> list[tuple[str, str, str]]:
    """Return ``(title, artist, ref)`` rows extracted from a source URL."""
    if kind == "spotify":
        if "/track/" in external_url:
            info = get_track_info(external_url, sp)
            return [(info["track_title"], info["artist_name"], external_url)] if info else []
        if "/album/" in external_url:
            return [(i["track_title"], i["artist_name"], external_url)
                    for i in get_album_info(external_url, sp)]
        return [(i["track_title"], i["artist_name"], external_url)
                for i in get_playlist_info(external_url, sp)]
    if kind == "apple":
        return [(term, "", external_url) for term in get_apple_playlist(external_url)]
    if kind == "youtube":
        return [("", "", external_url)]
    return []


def ingest_source(db, external_url: str, kind: str | None = None,
                  name: str | None = None):
    """Persist a Source + SourceItems for ``external_url``; return the Source.

    For Spotify, scrapes track rows using credentials from the settings store /
    env. For Apple, scrapes song search terms. Pass ``sp`` to reuse an existing
    client via :func:`ingest_source_with`.
    """
    kind = kind or detect_kind(external_url)
    sp = get_spotify_client() if kind == "spotify" else None
    if kind == "spotify" and sp is None:
        log.warning("Spotify credentials missing: source stored with no items.")
    return ingest_source_with(db, external_url, kind=kind, sp=sp, name=name)


def ingest_source_with(db, external_url: str, kind: str | None = None,
                       name: str | None = None, sp=None):
    """Like :func:`ingest_source` but with an injected Spotify client ``sp``."""
    kind = kind or detect_kind(external_url)
    name = name or f"{kind} · {external_url}"
    items = _fetch_items(kind, external_url, sp) if sp is not None else []
    with db.session() as session:
        source = Source(name=name, kind=kind, external_ref=external_url)
        session.add(source)
        session.flush()
        for title, artist, ref in items:
            session.add(SourceItem(source_id=source.id, title=title,
                                   artist=artist, ref=ref))
        session.commit()
        return source


# ---------------------------------------------------------------------------
# Step 2: resolve SourceItems -> Tracks
# ---------------------------------------------------------------------------

def title_id(artist: str, title: str) -> str:
    return f"{artist or ''} - {title or ''}".strip(" - ").lower()


def list_sources(db, source_id: int | None = None) -> list[Source]:
    """Return a Source (by id) or all Sources, within a fresh session."""
    with db.session() as session:
        if source_id:
            src = session.get(Source, source_id)
            return [src] if src else []
        return session.query(Source).all()


def count_tracks(db) -> int:
    with db.session() as session:
        return session.query(Track).count()


def _resolve_saavn(search: Search, item: SourceItem):
    """Resolve an item to a Saavn Song (with decrypted URL), or None."""
    query = f"{item.title} {item.artist}".strip()
    result = search.search(query)
    if not isinstance(result, dict):
        return None
    candidates = list(result.get("songs") or [])
    top = result.get("topresult") or {}
    first = candidates[0] if candidates else (top if isinstance(top, dict) else None)
    if not first:
        return None
    pid = first.get("id")
    if not pid:
        return None
    return search.enrich_song(pid)


def _track_from_saavn(song, base_title: str, base_artist: str, tid: str) -> Track:
    return Track(
        title=song.title or base_title,
        artist=song.subtitle or base_artist,
        album=song.album or "",
        year=str(song.year or ""),
        duration=int(song.duration or 0),
        artwork=song.image or "",
        title_id=tid,
        resolved_from="saavn",
        media_url=song.decrypted_media_url,
        state="pending" if song.decrypted_media_url else "to_resolve",
    )


def ensure_tracks(db, source, settings) -> list[Track]:
    """Resolve each of ``source``'s items to a Track row when title_id is new."""
    search = Search()
    new_tracks: list[Track] = []
    with db.session() as session:
        source = session.merge(source)
        for item in source.items:
            base_title = item.title or "unknown"
            base_artist = item.artist or ""
            tid = title_id(base_artist, base_title)
            if session.query(Track).filter_by(title_id=tid).first():
                continue

            track = None
            if settings.enable_saavn:
                song = _resolve_saavn(search, item)
                if song is not None:
                    track = _track_from_saavn(song, base_title, base_artist, tid)

            if track is None and settings.saavn_fallback_youtube:
                try:
                    watch_url = find_youtube(f"{base_title} {base_artist}".strip())
                    track = Track(title=base_title, artist=base_artist, title_id=tid,
                                  resolved_from="youtube", media_url=watch_url,
                                  state="to_resolve")
                except Exception as e:
                    log.warning("YouTube fallback failed for %s: %s", tid, e)

            if track is None:
                track = Track(title=base_title, artist=base_artist,
                              title_id=tid, state="failed")

            session.add(track)
            new_tracks.append(track)
        session.commit()
        return new_tracks


# ---------------------------------------------------------------------------
# Step 3: download
# ---------------------------------------------------------------------------

class _MediaTrack:
    """Song-like adapter exposing the fields DownloadSong reads."""

    def __init__(self, track: Track):
        self.decrypted_media_url = track.media_url
        self.title = track.title
        self.subtitle = track.artist if track.artist else None
        self.album = track.album or ""
        self.year = track.year or ""
        self.image = track.artwork or ""


def download_tracks(db, settings) -> list[str]:
    """Download pending tracks into ``settings.library_folder``. Returns paths."""
    output = settings.library_folder
    os.makedirs(output, exist_ok=True)
    downloaded: list[str] = []
    with db.session() as session:
        pending = session.query(Track).filter(
            Track.state.in_(["pending", "to_resolve"])
        )
        for track in pending:
            if not track.media_url:
                continue
            if track.resolved_from == "saavn":
                dl = DownloadSong(_MediaTrack(track), output_folder=output, skip=True)
            else:
                log.info("youtube download not yet wired in download_tracks: %s",
                         track.title_id)
                continue
            try:
                path = dl.download_song()
                track.state = "done"
                downloaded.append(path)
            except Exception as e:
                log.warning("Download failed for %s: %s", track.title_id, e)
                track.state = "failed"
            session.commit()
    return downloaded
