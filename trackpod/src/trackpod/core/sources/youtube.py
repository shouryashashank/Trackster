"""YouTube fallback source + yt-dlp downloader (ported & repackaged).

Reused from Trackster2 (feature/direct-search-and-download, main.py):
``find_youtube`` (extract first watch?v from a YouTube results page) and the
yt-dlp mp3 download logic from ``download_yt``. Rewritten to be stateless:
folders/settings are passed in rather than read from a global UI state.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import urllib.request

import yt_dlp

log = logging.getLogger(__name__)

ILLEGAL = ['/', '\\', '|', '?', '*', ':', '>', '<', '"']


def sanitize(s: str) -> str:
    if not s:
        return "untitled"
    return "".join(c for c in s if c not in ILLEGAL)


def find_youtube(query: str) -> str:
    """Return the first YouTube watch URL for ``query`` or raise ValueError.

    Kept faithful to the original (retry loop + regex over ``watch?v=``) but
    dropped the legacy mojibake replacements.
    """
    phrase = query.replace(" ", "+")
    count = 0
    response = None
    while count < 5:
        try:
            search_link = (
                "https://www.youtube.com/results?search_query=" + phrase
            )
            response = urllib.request.urlopen(search_link)
            break
        except Exception as e:
            log.warning("YouTube search attempt %d failed: %s", count + 1, e)
            count += 1

    if response is None:
        raise ValueError(
            "Please check your internet connection and try again later."
        )

    search_results = re.findall(r"watch\?v=(\S{11})", response.read().decode())
    if not search_results:
        raise ValueError(f"No YouTube results for: {query}")
    return "https://www.youtube.com/watch?v=" + search_results[0]


def download_yt(watch_url: str, output_folder: str, preferred_quality: str = "192") -> str | None:
    """Download a YouTube ``watch_url`` to mp3 in ``output_folder``.

    Uses yt-dlp's FFmpegExtractAudio postprocessor. If it isn't available or
    the mp3 isn't written, falls back to moviepy conversion of the raw file.
    Returns the final mp3 path, or None on failure.
    """
    output_folder = output_folder if output_folder.endswith(os.sep) else output_folder + os.sep
    tmp_dir = os.path.join(output_folder, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    out_base = os.path.join(tmp_dir, "download")
    yt_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_base + ".%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": preferred_quality,
            }
        ],
    }
    with yt_dlp.YoutubeDL(yt_opts) as ydl:
        ydl.download([watch_url])

    mp3_file = out_base + ".mp3"
    if not os.path.exists(mp3_file):
        matches = glob.glob(out_base + ".*")
        mp3_file = next((m for m in matches if m.lower().endswith(".mp3")), None)
        if mp3_file is None and matches:
            raw = matches[0]
            mp3_file = out_base + ".mp3"
            try:
                from moviepy.audio.io.AudioFileClip import AudioFileClip
            except ImportError:  # moviepy 1.x
                from moviepy.editor import AudioFileClip
            clip = AudioFileClip(raw)
            try:
                clip.write_audiofile(mp3_file)
            finally:
                clip.close()
            os.remove(raw)
    return mp3_file if mp3_file and os.path.exists(mp3_file) else None
