"""JioSaavn (Saavn) resolver — ported & repackaged from Trackster2.

Reused near-verbatim from the working resolver on the
`feature/direct-search-and-download` branch: Song (with title/subtitle
fallbacks + decrypted media url), Search.search / enrich_song /
get_songs_from_artist / get_songs_from_album, DownloadSong (sync + async
media download, mutagen tagging, album art, finalize). Kept UI-agnostic —
pure Python + network only.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import time
import urllib.request

import requests
from aiohttp import ClientTimeout
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1
from pyDes import ECB, PAD_PKCS5, des

try:  # moviepy 1.x
    from moviepy.editor import AudioFileClip
except ImportError:  # moviepy 2.x
    from moviepy.audio.io.AudioFileClip import AudioFileClip

DECRYPT_KEY = b"38346591"
DECRYPT_IV = b"\0\0\0\0\0\0\0\0"

SEARCH_URL = (
    "https://www.jiosaavn.com/api.php?__call=autocomplete.get"
    "&_format=json&_marker=0&cc=in&includeMetaTags=1&query="
)
SONG_DETAILS_URL = (
    "https://www.jiosaavn.com/api.php?__call=song.getDetails"
    "&cc=in&_marker=0%3F_marker%3D0&_format=json&pids="
)
ARTIST_URL = (
    "https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}"
    "&type=artist&n_song=50&n_album=50&sub_type=&category=latest"
    "&sort_order=desc&includeMetaTags=0&ctx=web6dot0&api_version=4"
    "&_format=json&_marker=0"
)
ALBUM_URL = (
    "https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}"
    "&type=album&includeMetaTags=0&ctx=web6dot0&api_version=4"
    "&_format=json&_marker=0"
)

log = logging.getLogger(__name__)


class Song:
    """A single JioSaavn song: metadata + (optionally) decrypted media URL.

    Initialize with the raw song JSON dict and access common fields as
    attributes. Use ``to_dict()`` for a JSON-serializable representation.
    """

    def __init__(self, song_json: dict | None = None):
        self.raw = song_json or {}
        self.id = self.raw.get("id")
        self.title = self.raw.get("title") or self.raw.get("song")
        self.subtitle = (
            self.raw.get("subtitle")
            or self.raw.get("primary_artists")
            or self.raw.get("singers")
        )
        self.type = self.raw.get("type")
        self.perma_url = self.raw.get("perma_url")
        self.image = self.raw.get("image")
        self.language = self.raw.get("language")
        self.year = self.raw.get("year")
        self.play_count = self.raw.get("play_count")
        self.explicit_content = self.raw.get("explicit_content")
        self.list_count = self.raw.get("list_count")
        self.more_info = self.raw.get("more_info", {})

        self.album_id = self.more_info.get("album_id")
        self.album = self.more_info.get("album")
        self.duration = self.more_info.get("duration")
        self.encrypted_media_url = (
            self.more_info.get("encrypted_media_url")
            or self.raw.get("encrypted_media_url")
        )
        self.decrypted_media_url = (
            self.decrypt_url(self.encrypted_media_url)
            if self.encrypted_media_url
            else None
        )
        self.vlink = self.more_info.get("vlink")
        self.artistMap = self.more_info.get("artistMap", {})

    def decrypt_url(self, url: str) -> str:
        """Decrypt a JioSaavn encrypted media URL ('_96.mp4' -> '_320.mp4')."""
        des_cipher = des(
            DECRYPT_KEY, ECB, DECRYPT_IV, pad=None, padmode=PAD_PKCS5
        )
        enc_url = base64.b64decode(url.strip())
        dec_url = des_cipher.decrypt(enc_url, padmode=PAD_PKCS5).decode("utf-8")
        return dec_url.replace("_96.mp4", "_320.mp4")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "type": self.type,
            "perma_url": self.perma_url,
            "image": self.image,
            "language": self.language,
            "year": self.year,
            "play_count": self.play_count,
            "explicit_content": self.explicit_content,
            "list_count": self.list_count,
            "more_info": self.more_info,
        }

    def __repr__(self) -> str:
        return f"<Song id={self.id!r} title={self.title!r}>"


class Search:
    """Search + fetch songs/albums/artists from JioSaavn."""

    def search(self, query: str) -> dict | str | None:
        """Return {topresult, songs, artists, albums} raw JSON dicts."""
        try:
            resp = requests.get(SEARCH_URL + query, timeout=10)
        except Exception as e:
            log.warning("Error fetching search results: %s", e)
            return None
        if resp.status_code != 200:
            log.warning("Error fetching search results (status %s)", resp.status_code)
            return None
        try:
            data = resp.json()
        except Exception:
            return None

        topresult = None
        songs: list[dict] = []
        artists: list[dict] = []
        albums: list[dict] = []

        top_query_data = data.get("topquery", {}).get("data", [])
        if isinstance(top_query_data, list) and top_query_data:
            topresult = top_query_data[0]

        for key, bucket in (("songs", songs), ("artists", artists), ("albums", albums)):
            for item in (data.get(key, {}).get("data") or [])[:5]:
                if item.get("type") == key[:-1] or key == "songs":
                    bucket.append(item)
            for item in top_query_data:
                if item.get("type") == key[:-1] and not any(
                    (x.get("id") or x.get("url")) == (item.get("id") or item.get("url"))
                    for x in bucket
                ):
                    bucket.append(item)

        if not songs and not artists and not albums and not topresult:
            self._scan(data, topresult, songs, artists, albums)

        def uniq(lst):
            seen = set()
            out = []
            for it in lst:
                id_ = it.get("id") or it.get("url") or it.get("perma_url") or repr(it)
                if id_ not in seen:
                    seen.add(id_)
                    out.append(it)
            return out

        songs = uniq(songs)[:5]
        artists = uniq(artists)[:3]
        albums = uniq(albums)[:3]

        if not topresult and not songs and not artists and not albums:
            return "not found"

        return {
            "topresult": topresult,
            "songs": songs,
            "artists": artists,
            "albums": albums,
        }

    @staticmethod
    def _scan(obj, topresult_ref, artists, albums, songs):
        def walk(o):
            nonlocal topresult_ref
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for elem in o:
                    if isinstance(elem, dict):
                        t = elem.get("type")
                        if t == "artist" and len(artists) < 3:
                            artists.append(elem)
                        elif t == "album" and len(albums) < 3:
                            albums.append(elem)
                        elif t == "song" and len(songs) < 3:
                            songs.append(elem)
                        if topresult_ref is None and t in ("artist", "album", "song"):
                            topresult_ref = elem
                        if (
                            len(artists) >= 3
                            and len(albums) >= 3
                            and len(songs) >= 3
                            and topresult_ref is not None
                        ):
                            return
                    walk(elem)

        walk(obj)

    def enrich_song(self, pid) -> Song | None:
        """Fetch full song JSON (incl. encrypted media URL) for a pid.

        The autocomplete search result only carries a stub (id + vlink); query
        ``song.getDetails`` by pid so a Song built from it has a usable
        ``decrypted_media_url``.
        """
        if not pid:
            return None
        try:
            resp = requests.get(SONG_DETAILS_URL + str(pid), timeout=15)
        except Exception as e:
            log.warning("Error fetching song details for %s: %s", pid, e)
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        detail = data.get(str(pid)) or next(iter(data.values()), None)
        if not detail:
            return None
        return Song(detail)

    def get_songs_from_artist(self, artist_json: dict) -> list[Song]:
        if not artist_json.get("id"):
            return []
        perma = artist_json.get("url")
        if not perma:
            return []
        token = perma.rstrip("/").split("/")[-1]
        if not token:
            return []
        songs_list: list[Song] = []
        page = 0
        while True:
            url = ARTIST_URL.format(token=token) + f"&p={page}"
            try:
                resp = requests.get(url, timeout=15)
            except Exception:
                break
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except Exception:
                break

            candidates = None
            for key in ("topSongs", "songs", "data", "songs_list"):
                v = data.get(key)
                if isinstance(v, list) and v:
                    candidates = v
                    break
            if not candidates:
                for v in data.values():
                    if (
                        isinstance(v, list)
                        and v
                        and isinstance(v[0], dict)
                        and v[0].get("type") == "song"
                    ):
                        candidates = v
                        break
            if not candidates:
                break
            for s in candidates:
                try:
                    songs_list.append(Song(s))
                except Exception as e:
                    log.warning("Error parsing song data, skipping... %s", e)
                    continue
            page += 1
        return songs_list

    def get_songs_from_album(self, album_json: dict) -> list[Song]:
        perma = album_json.get("url") or album_json.get("perma_url")
        if not perma:
            return []
        token = perma.rstrip("/").split("/")[-1]
        if not token:
            return []
        try:
            resp = requests.get(ALBUM_URL.format(token=token), timeout=15)
        except Exception:
            return []
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except Exception:
            return []

        candidates = data.get("list") or data.get("songs") or data.get("data") or []
        songs_list: list[Song] = []
        if isinstance(candidates, list):
            for s in candidates:
                try:
                    songs_list.append(Song(s))
                except Exception as e:
                    log.warning("Error parsing album song, skipping... %s", e)
                    continue
        else:
            for v in data.values():
                if (
                    isinstance(v, list)
                    and v
                    and isinstance(v[0], dict)
                    and v[0].get("type") == "song"
                ):
                    for s in v:
                        try:
                            songs_list.append(Song(s))
                        except Exception as e:
                            log.warning("Error parsing album song, skipping... %s", e)
                            continue
                    break
        return songs_list


class DownloadSong:
    """Download a Song to mp3, tag it (metadata + album art), and move it."""

    def __init__(self, song, output_folder: str = "music-yt", skip: bool = False):
        self.song = song
        self.output_folder = (
            output_folder if output_folder.endswith(os.sep) else output_folder + os.sep
        )
        self.skip = bool(skip)

    # -- helpers -----------------------------------------------------------

    def _paths(self) -> tuple[str, str, str, str]:
        title = self.song.title or "unknown"
        safe_title = "".join(
            c for c in title if c not in ["/", "\\", "|", "?", "*", ":", ">", "<", '"']
        )
        tmp_dir = os.path.join(self.output_folder, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        os.makedirs(self.output_folder, exist_ok=True)
        return (
            os.path.join(tmp_dir, f"{safe_title}.mp4"),
            os.path.join(tmp_dir, f"{safe_title}.mp3"),
            os.path.join(self.output_folder, f"{safe_title}.mp3"),
            title,
        )

    @staticmethod
    def _tag(song, audio_file: str) -> None:
        tags = ID3()
        artist_name = getattr(song, "subtitle", None) or getattr(song, "artistMap", None) or ""
        if isinstance(artist_name, dict):
            artist_name = ", ".join(v.get("name", "") for v in artist_name.values())
        tags["TPE1"] = TPE1(encoding=3, text=artist_name or "")
        tags["TALB"] = TALB(encoding=3, text=getattr(song, "album", "") or "")
        tags["TIT2"] = TIT2(encoding=3, text=getattr(song, "title", "") or "unknown")
        if getattr(song, "year", None):
            tags["TDRC"] = TDRC(encoding=3, text=str(song.year))
        tags.save(audio_file)

        if getattr(song, "image", None):
            with urllib.request.urlopen(song.image) as img:
                img_data = img.read()
            audio = ID3(audio_file)
            audio["APIC"] = APIC(
                encoding=3, mime="image/jpeg", type=3, desc="Cover", data=img_data
            )
            audio.save(v2_version=3)

    @staticmethod
    def _finalize(audio_file: str, final_file: str) -> None:
        if os.path.exists(final_file):
            os.remove(final_file)
        try:
            os.replace(audio_file, final_file)
        except Exception:
            try:
                shutil.copy2(audio_file, final_file)
                os.remove(audio_file)
            except Exception as e:
                log.warning("Failed to move/copy final file: %s", e)
                raise

    # -- sync --------------------------------------------------------------

    def download_song(self) -> str:
        """Download, convert to mp3, tag; return final mp3 path or raise."""
        if not self.song or not getattr(self.song, "decrypted_media_url", None):
            raise ValueError("Song has no decrypted URL")

        video_file, audio_file, final_file, title = self._paths()

        if self.skip and os.path.exists(final_file):
            log.info("Skipping existing file: %s", final_file)
            return final_file

        url = self.song.decrypted_media_url
        max_attempts, backoff = 3, 1

        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.get(url, stream=True, timeout=30)
                resp.raise_for_status()
                with open(video_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                break
            except Exception as e:
                log.warning("Attempt %s - failed to download %s: %s", attempt, title, e)
                if attempt == max_attempts:
                    raise
                time.sleep(backoff)
                backoff *= 2

        for attempt in range(1, max_attempts + 1):
            try:
                clip = AudioFileClip(video_file)
                try:
                    clip.write_audiofile(audio_file, bitrate="3000k")
                finally:
                    clip.close()
                break
            except Exception as e:
                log.warning("Attempt %s - failed to convert %s: %s", attempt, video_file, e)
                if attempt == max_attempts:
                    try:
                        os.remove(video_file)
                    except Exception:
                        pass
                    raise
                time.sleep(backoff)
                backoff *= 2

        try:
            os.remove(video_file)
        except Exception:
            pass

        for attempt in range(1, max_attempts + 1):
            try:
                self._tag(self.song, audio_file)
                break
            except Exception as e:
                log.warning("Attempt %s - failed to set metadata for %s: %s", attempt, title, e)
                if attempt == max_attempts:
                    log.warning("Giving up on tagging for %s", title)
                else:
                    time.sleep(backoff)
                    backoff *= 2

        self._finalize(audio_file, final_file)
        return final_file

    # -- async -------------------------------------------------------------

    async def download_song_async(self, session, semaphore) -> str:
        """Async version: download, convert, tag and return final path."""
        if not self.song or not getattr(self.song, "decrypted_media_url", None):
            raise ValueError("Song has no decrypted URL")

        title = self.song.title or "unknown"
        safe_title = "".join(
            c for c in title if c not in ["/", "\\", "|", "?", "*", ":", ">", "<", '"']
        )
        final_file = os.path.join(self.output_folder, f"{safe_title}.mp3")

        if self.skip and os.path.exists(final_file):
            log.info("Skipping existing file: %s", final_file)
            return final_file

        async with semaphore:
            video_file, audio_file, _final, title = self._paths()

            url = self.song.decrypted_media_url
            timeout = ClientTimeout(total=60)
            max_attempts, backoff = 3, 1

            for attempt in range(1, max_attempts + 1):
                try:
                    async with session.get(url, timeout=timeout) as resp:
                        resp.raise_for_status()
                        with open(video_file, "wb") as f:
                            async for chunk in resp.content.iter_chunked(8192):
                                f.write(chunk)
                    break
                except Exception as e:
                    log.warning("Attempt %s - failed to download (async) %s: %s", attempt, title, e)
                    if attempt == max_attempts:
                        raise
                    await asyncio.sleep(backoff)
                    backoff *= 2

            loop = asyncio.get_running_loop()

            def convert():
                clip = AudioFileClip(video_file)
                try:
                    clip.write_audiofile(audio_file, bitrate="3000k")
                finally:
                    clip.close()
                try:
                    os.remove(video_file)
                except Exception:
                    pass

            for attempt in range(1, max_attempts + 1):
                try:
                    await loop.run_in_executor(None, convert)
                    break
                except Exception as e:
                    log.warning("Attempt %s - failed to convert (async) %s: %s",
                                attempt, video_file, e)
                    if attempt == max_attempts:
                        raise
                    await asyncio.sleep(backoff)
                    backoff *= 2

            def tag():
                self._tag(self.song, audio_file)

            for attempt in range(1, max_attempts + 1):
                try:
                    await loop.run_in_executor(None, tag)
                    break
                except Exception as e:
                    log.warning("Attempt %s - failed to tag (async) %s: %s", attempt, title, e)
                    if attempt == max_attempts:
                        log.warning("Giving up on tagging for %s (async)", title)
                    else:
                        await asyncio.sleep(backoff)
                        backoff *= 2

            self._finalize(audio_file, final_file)
            return final_file
