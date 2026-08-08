"""Source resolvers (Saavn, YouTube, Spotify, Apple)."""

from trackpod.core.sources.apple import get_playlist as get_apple_playlist
from trackpod.core.sources.jiosaavn import (
    DownloadSong,
    Search,
    Song,
)
from trackpod.core.sources.spotify import (
    get_album_info,
    get_playlist_info,
    get_spotify_client,
    get_track_info,
    search_spotify,
)
from trackpod.core.sources.youtube import download_yt, find_youtube

__all__ = [
    "DownloadSong",
    "Search",
    "Song",
    "get_album_info",
    "get_apple_playlist",
    "get_playlist_info",
    "get_spotify_client",
    "get_track_info",
    "search_spotify",
    "find_youtube",
    "download_yt",
]
