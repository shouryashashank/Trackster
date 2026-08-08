"""Apple Music playlist scraping (ported & repackaged from Trackster2 apple.py).

Reused verbatim: get_song_details (og:title) and get_playlist (music:song meta
sweep). Returns search terms for each song so the pipeline can resolve them.
UI-agnostic.
"""

from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


def get_song_details(link: str) -> str | None:
    """Return the song search term for an Apple Music song URL, or None."""
    try:
        response = requests.get(link, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.find("meta", attrs={"property": "og:title"})
        if title:
            content = title.get("content") or ""
            return content.replace("on Apple Music", "audio").strip()
        log.warning("No meta tag found for %s", link)
        return None
    except requests.RequestException as e:
        log.warning("Request error for %s: %s", link, e)
        return None
    except Exception as e:
        log.warning("An error occurred for %s: %s", link, e)
        return None


def get_playlist(url: str) -> list[str]:
    """Return a list of song search terms scraped from an Apple Music playlist."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        song_terms = []
        for item in soup.find_all("meta", attrs={"property": "music:song"}):
            match = re.search(r'content="(https?://[^"]+)"', str(item))
            if match:
                term = get_song_details(match.group(1))
                if term:
                    song_terms.append(term)
        return song_terms
    except requests.RequestException as e:
        log.warning("Request error for playlist %s: %s", url, e)
    except Exception as e:
        log.warning("An error occurred for playlist %s: %s", url, e)
    return []
