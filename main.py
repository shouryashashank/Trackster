import asyncio
import base64
import difflib
import glob
import logging
import os
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import flet as ft
import requests
import spotipy
import yt_dlp
from aiohttp import ClientTimeout
from dotenv import load_dotenv
try:
    from moviepy.editor import AudioFileClip  # moviepy 1.x
except ImportError:
    from moviepy.audio.io.AudioFileClip import AudioFileClip  # moviepy 2.x
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPE2, TRCK, TSRC, USLT
from pyDes import ECB, PAD_PKCS5, des
from pytube import Playlist, YouTube
from spotipy.oauth2 import SpotifyClientCredentials
from tqdm import tqdm
from yarl import URL

import apple
from db import (
    add_downloaded,
    add_failed,
    add_mismatch,
    add_synced,
    clear_failed,
    get_failed_titles,
    get_setting,
    get_synced_ids,
    init_db,
    migrate_env,
    remove_failed,
    set_setting,
)
from search import DownloadSong, Search, Song

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

ssl._create_default_https_context = ssl._create_unverified_context

search_base_url = "https://www.jiosaavn.com/api.php?__call=autocomplete.get&_format=json&_marker=0&cc=in&includeMetaTags=1&query="
song_base_url = "https://www.jiosaavn.com/api.php?__call=song.getDetails&cc=in&_marker=0%3F_marker%3D0&_format=json&pids="
lyrics_base_url = "https://www.jiosaavn.com/api.php?__call=lyrics.getLyricvideo_files&ctx=web6dot0&api_version=4&_format=json&_marker=0%3F_marker%3D0&lyrics_id="


class AppState:
    """Shared mutable app state, kept out of module globals."""

    def __init__(self):
        self.music_folder_path = "music-yt/"
        self.file_exists_action = ""
        self.use_spotify_for_metadata = True


state = AppState()


# --------------------------------------------------------------------------
# Filesystem helpers
# --------------------------------------------------------------------------

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '', filename)


def ensure_folder_path_ends_with_slash(folder_path):
    folder_path = folder_path.rstrip("/\\")
    return folder_path + os.sep


def make_alpha_numeric(string):
    return ''.join(char for char in string if char.isalnum())


# --------------------------------------------------------------------------
# Spotify client / metadata
# --------------------------------------------------------------------------

def get_spotify_client():
    load_dotenv()
    client_id = get_setting("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = get_setting("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIPY_CLIENT_SECRET")
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


def search_spotify(search_term, sp):
    """search for the track on spotify"""
    search_results = sp.search(search_term, type="track", limit=1)
    if search_results["tracks"]["total"] == 0:
        return None
    track = search_results["tracks"]["items"][0]
    return track["external_urls"]["spotify"]


def get_track_info_spotify(track_url, sp):
    res = requests.get(track_url)
    if res.status_code != 200:
        for _ in range(3):
            res = requests.get(track_url)
            if res.status_code == 200:
                break
    if res.status_code != 200:
        log.error("Invalid Spotify track URL: %s", track_url)

    track = sp.track(track_url)

    return {
        "artist_name": track["artists"][0]["name"],
        "track_title": track["name"],
        "track_number": track["track_number"],
        "isrc": track["external_ids"].get("isrc") if track.get("external_ids") else "",
        "album_art": track["album"]["images"][1]["url"],
        "album_name": track["album"]["name"],
        "release_date": track["album"]["release_date"],
        "artists": [artist["name"] for artist in track["artists"]],
    }


def get_track_info_youtube(video):
    publish_date = getattr(video, "publish_date", None)
    release_date = publish_date.strftime("%Y-%m-%d") if publish_date else ""
    return {
        "artist_name": video.author,
        "track_title": video.title,
        "track_number": 0,
        "isrc": "",
        "album_art": video.thumbnail_url,
        "album_name": video.author,
        "release_date": release_date,
        "artists": [video.author],
    }


def get_track_info(track_url, sp, max_retries=3, initial_timeout=1):
    """Get track metadata from Spotify with retry logic for timeouts."""
    last_exception = None

    for attempt in range(max_retries + 1):  # +1 for the initial attempt
        try:
            track = sp.track(track_url)
            isrc = track["external_ids"].get("isrc") if track.get("external_ids") else None

            return {
                "artist_name": track["artists"][0]["name"],
                "track_title": track["name"],
                "track_number": track["track_number"],
                "isrc": isrc,
                "album_art": track["album"]["images"][1]["url"],
                "album_name": track["album"]["name"],
                "release_date": track["album"]["release_date"],
                "artists": [artist["name"] for artist in track["artists"]],
            }

        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = initial_timeout * (2 ** attempt)  # Exponential backoff
                print(f"Attempt {attempt + 1} failed. Retrying in {wait_time} seconds... Error: {str(e)}")
                time.sleep(wait_time)
            continue

    print(f"Failed to get track info after {max_retries + 1} attempts. Last error: {str(last_exception)}")
    return None


def get_playlist_info(sp_playlist, sp):
    res = requests.get(sp_playlist)
    if res.status_code != 200:
        raise ValueError("Invalid Spotify playlist URL")
    pl = sp.playlist(sp_playlist)
    if not pl["public"]:
        raise ValueError(
            "Can't download private playlists. Change your playlist's state to public."
        )
    playlist = sp.playlist_tracks(sp_playlist)

    tracks_item = playlist['items']

    while playlist['next']:
        playlist = sp.next(playlist)
        tracks_item.extend(playlist['items'])

    tracks = [item["track"] for item in tracks_item if item.get("track") and item["track"].get("id")]
    synced_ids = get_synced_ids()
    tracks_info = []
    for track in tqdm(tracks):
        if track["id"] in synced_ids:
            continue
        track_url = f"https://open.spotify.com/track/{track['id']}"
        track_info = get_track_info(track_url, sp)
        if track_info:
            tracks_info.append(track_info)
            add_synced(track["id"])
    return tracks_info


def get_album_info(sp_album, sp):
    res = requests.get(sp_album)
    if res.status_code != 200:
        raise ValueError("Invalid Spotify album URL")

    playlist = sp.album_tracks(sp_album)

    tracks_item = playlist['items']

    while playlist['next']:
        playlist = sp.next(playlist)
        tracks_item.extend(playlist['items'])

    synced_ids = get_synced_ids()

    def process_track(track):
        if track["id"] in synced_ids:
            return None
        track_url = f"https://open.spotify.com/track/{track['id']}"
        info = get_track_info(track_url, sp)
        if info:
            add_synced(track["id"])
        return info

    with ThreadPoolExecutor() as executor:
        results = list(tqdm(executor.map(process_track, tracks_item), total=len(tracks_item)))

    return [r for r in results if r]


# --------------------------------------------------------------------------
# Download engines
# --------------------------------------------------------------------------

def prompt_exists_action():
    """ask the user what happens if the file being downloaded already exists"""
    if state.file_exists_action == "SA":  # SA == 'Skip All'
        return False
    elif state.file_exists_action == "RA":  # RA == 'Replace All'
        return True

    print("This file already exists.")
    while True:
        resp = (
            input("replace[R] | replace all[RA] | skip[S] | skip all[SA]: ")
            .upper()
            .strip()
        )
        if resp in ("RA", "SA"):
            state.file_exists_action = resp
        if resp in ("R", "RA"):
            return True
        elif resp in ("S", "SA"):
            return False
        print("---Invalid response---")


def download_yt(yt, search_term):
    """download the video in mp3 format from youtube"""
    safe_title = "".join([c for c in yt.title if c not in ['/', '\\', '|', '?', '*', ':', '>', '<', '"']])
    final_path = os.path.join(state.music_folder_path, f"{safe_title}.mp3")
    exists = os.path.exists(final_path)
    if exists and not prompt_exists_action():
        return False

    tmp_dir = os.path.join(state.music_folder_path, "tmp") + os.sep
    os.makedirs(tmp_dir, exist_ok=True)
    out_base = os.path.join(tmp_dir, safe_title)
    yt_opts = {
        'format': 'bestaudio/best',
        'outtmpl': out_base + '.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
    }
    with yt_dlp.YoutubeDL(yt_opts) as ydl:
        ydl.download([yt.watch_url])

    mp3_file = out_base + '.mp3'
    if not os.path.exists(mp3_file):
        # yt-dlp may have sanitized the filename; find what it actually wrote
        matches = glob.glob(out_base + '.*')
        mp3_file = next((m for m in matches if m.lower().endswith('.mp3')), None)
        if mp3_file is None and matches:
            # no ffmpeg postprocessor available: convert the raw bestaudio file
            raw = matches[0]
            mp3_file = out_base + '.mp3'
            clip = AudioFileClip(raw)
            try:
                clip.write_audiofile(mp3_file)
            finally:
                clip.close()
            os.remove(raw)
    return mp3_file if mp3_file and os.path.exists(mp3_file) else None


def decrypt_url(url):
    des_cipher = des(b"38346591", ECB, b"\0\0\0\0\0\0\0\0",
                     pad=None, padmode=PAD_PKCS5)
    enc_url = base64.b64decode(url.strip())
    dec_url = des_cipher.decrypt(enc_url, padmode=PAD_PKCS5).decode('utf-8')
    dec_url = dec_url.replace("_96.mp4", "_320.mp4")
    return dec_url


def search_song(query):
    """Search JioSaavn for a song. Returns a metadata dict or None."""
    search_url = search_base_url + query
    response = requests.get(search_url, timeout=15)
    # First, try to find a song in the topquery data if available
    best_song_id = None
    best_diff = 0
    try:
        topquery_data = response.json().get('topquery', {}).get('data', [])
        for item in topquery_data:
            if item.get('type') == 'song' and item.get('id'):
                best_song_id = item['id']
                best_diff = 1.0  # highest similarity; exit early if exact match found
                break
    except Exception as e:
        log.warning("Failed to read topquery results: %s", e)

    # If a topquery song wasn't found, fall back to the existing logic
    if not best_song_id:
        try:
            songs = response.json().get('songs', {}).get('data', [])
        except Exception:
            songs = []
        if not songs:
            return None
        song_id = songs[0]['id']
        best_diff = 0
        best_song_id = song_id

        for song_data in songs:
            try:
                sid = song_data['id']
                output_query = f"{song_data['title']} {song_data['more_info']['primary_artists']} {song_data['album']}"
                diff_ratio = difflib.SequenceMatcher(None, query.lower(), output_query.lower()).ratio()
                if diff_ratio > best_diff:
                    best_diff = diff_ratio
                    best_song_id = sid
                if diff_ratio == 1:
                    break
            except Exception as e:
                print(f"Error processing song data: {e}")

    if not best_song_id:
        return None

    song_url = song_base_url + best_song_id
    response = requests.get(song_url, timeout=15)
    song_data = response.json()[best_song_id]

    has_lyrics = song_data['has_lyrics'] == 'true'
    lyrics = ""
    if has_lyrics:
        lyrics_url = lyrics_base_url + best_song_id
        try:
            lyrics_response = requests.get(lyrics_url, timeout=15)
            lyrics = lyrics_response.json()['lyrics']
        except Exception as e:
            print(f"Failed to get lyrics for {song_data['song']}: {e}")

    return {
        "url": decrypt_url(song_data['encrypted_media_url']),
        "primary_artists": song_data['primary_artists'],
        "album": song_data['album'],
        "song": song_data['song'],
        "release_date": song_data['release_date'],
        "lyrics": lyrics,
    }


def download_high_quality(search_term):
    song = search_song(search_term)
    if not isinstance(song, dict):
        return None
    song_url = song['url']
    sanitized_song_name = sanitize_filename(song['song'])
    file = os.path.join(state.music_folder_path, f"{sanitized_song_name}.mp3")
    # check if the file already exists
    if os.path.exists(file):
        if not prompt_exists_action():
            return "File already exists."
    response = requests.get(song_url)
    tmp_dir = os.path.join(state.music_folder_path, "tmp") + os.sep
    os.makedirs(tmp_dir, exist_ok=True)
    video_file = os.path.join(tmp_dir, f"{sanitized_song_name}.mp4")
    audio_file = os.path.join(tmp_dir, f"{sanitized_song_name}.mp3")
    with open(video_file, "wb") as f:
        f.write(response.content)
    FILETOCONVERT = AudioFileClip(video_file)
    FILETOCONVERT.write_audiofile(audio_file, bitrate="3000k")
    FILETOCONVERT.close()
    os.remove(video_file)
    song["mp3"] = audio_file
    return song


# --------------------------------------------------------------------------
# Metadata tagging
# --------------------------------------------------------------------------

def set_metadata(metadata, file_path, lyrics):
    """adds metadata to the downloaded mp3 file"""

    mp3file = ID3(file_path)

    mp3file["TPE1"] = TPE1(encoding=3, text=metadata["artist_name"])
    mp3file["TPE2"] = TPE2(encoding=3, text=metadata["artists"])
    mp3file["TALB"] = TALB(encoding=3, text=metadata["album_name"])
    mp3file["TIT2"] = TIT2(encoding=3, text=metadata["track_title"])
    mp3file["TDRC"] = TDRC(encoding=3, text=metadata.get("release_date") or "")
    mp3file["TRCK"] = TRCK(encoding=3, text=str(metadata.get("track_number") or 0))
    mp3file["TSRC"] = TSRC(encoding=3, text=metadata.get("isrc") or "")
    if lyrics:
        if mp3file.getall('USLT'):
            ulyrics = mp3file.getall('USLT')[0]
            ulyrics.text = lyrics
        else:
            ulyrics = USLT(encoding=3, desc='', text=lyrics)
            mp3file.add(ulyrics)
    mp3file.save()

    # add album cover
    album_art = metadata.get("album_art")
    if album_art:
        audio = ID3(file_path)
        with urllib.request.urlopen(album_art) as albumart:
            audio["APIC"] = APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=albumart.read()
            )
        audio.save(v2_version=3)


# --------------------------------------------------------------------------
# YouTube search
# --------------------------------------------------------------------------

def find_youtube(query):
    query = query.replace("é", "e")
    query = query.replace("’", "")
    query = query.replace("æ", "ae")
    query = query.replace("ñ", "n")
    query = query.replace("–", "+")
    query = query.replace("‘", "")
    query = query.replace("ú", "u")

    phrase = query.replace(" ", "+")
    search_link = "https://www.youtube.com/results?search_query=" + phrase
    count = 0
    while count < 5:
        try:
            search_link = str(URL(search_link))
            response = urllib.request.urlopen(search_link)
            break
        except Exception:
            count += 1
    else:
        raise ValueError("Please check your internet connection and try again later.")

    search_results = re.findall(r"watch\?v=(\S{11})", response.read().decode())
    first_vid = "https://www.youtube.com/watch?v=" + search_results[0]

    return first_vid


# --------------------------------------------------------------------------
# Flet UI helpers
# --------------------------------------------------------------------------

async def pick_folder(e):
    picker = ft.FilePicker()
    path = await picker.get_directory_path()
    if not path:
        directory_path.value = "Cancelled!"
    else:
        directory_path.value = path
        state.music_folder_path = ensure_folder_path_ends_with_slash(path)
        print(state.music_folder_path)
    directory_path.update()
    e.control.page.update()


directory_path = ft.Text("", size=14, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE))


def set_theme(e, color):
    e.control.page.theme = ft.Theme(color_scheme_seed=color)
    e.control.page.theme_mode = ft.ThemeMode.SYSTEM
    e.control.page.update()


def popup(page, text):
    dlg = ft.AlertDialog(
        title=ft.Text(text),
        on_dismiss=lambda e: None,
    )
    return dlg


def show_dialog(page, dialog):
    """Open a dialog compatibly across flet versions (open vs show_dialog)."""
    open_fn = getattr(page, "open", None) or getattr(page, "show_dialog", None)
    if open_fn is not None:
        open_fn(dialog)


class GestureDetector:
    def __init__(self):
        self.detector = ft.GestureDetector(
            on_pan_update=self.on_pan_update
        )

    def on_pan_update(self, e):
        if e.delta_x < 0:
            switch_to_sp_tab(e)
        elif e.delta_x > 0:
            switch_to_yt_tab(e)


def navigation_drawer():
    spotify_client_id = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    spotify_client_secret = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    spotify_client_id.value = get_setting("SPOTIPY_CLIENT_ID") or ""
    spotify_client_secret.value = get_setting("SPOTIPY_CLIENT_SECRET") or ""

    def save_app_settings(e):
        try:
            set_setting("SPOTIPY_CLIENT_ID", spotify_client_id.value)
            set_setting("SPOTIPY_CLIENT_SECRET", spotify_client_secret.value)
        except Exception as err:
            print(err)
            return "app settings update failed"
        return "app settings updated"

    def yt_page_launch(e):
        e.control.page.launch_url('https://youtu.be/vT43uBHq974')

    def petreon_page_launch(e):
        e.control.page.launch_url('https://www.patreon.com/c/Predacons')

    def github_page_launch(e):
        e.control.page.launch_url('https://github.com/shouryashashank/Trackster')

    def email_page_launch(e):
        e.control.page.launch_url('https://www.patreon.com/messages/ffd73e51aa264a61842c446763dbaff9?mode=campaign&tab=chats')

    def close_end_drawer(e):
        e.control.page.end_drawer = end_drawer
        end_drawer.open = False
        e.control.page.update()

    end_drawer = ft.NavigationDrawer([
        ft.SafeArea(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(""),
                            ft.IconButton(icon=ft.Icons.CLOSE, on_click=close_end_drawer)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    ft.Text("Spotify client id:"),
                    spotify_client_id,
                    ft.Text("Spotify client secret:"),
                    spotify_client_secret,
                    ft.Button("Save", on_click=save_app_settings),
                    ft.TextButton("How To Get Spotify api api Keys", on_click=yt_page_launch),
                    ft.TextButton("Contact support", on_click=email_page_launch),
                    ft.TextButton("Get version with api key already added.", on_click=petreon_page_launch),
                    ft.TextButton("Help me buy a new phone", on_click=petreon_page_launch),
                    ft.TextButton("See source code", on_click=github_page_launch)

                ]
            ),
            minimum_padding=10,
        )
    ])

    def open_end_drawer(e):
        e.control.page.end_drawer = end_drawer
        end_drawer.open = True
        e.control.page.update()

    return open_end_drawer


def app_bar():
    view = ft.AppBar(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.MUSIC_NOTE, color=ft.Colors.PRIMARY),
                ft.Text("Trackster", weight=ft.FontWeight.BOLD, size=22),
            ],
            spacing=8,
        ),
        actions=[
            ft.IconButton(
                ft.Icons.MENU,
                style=ft.ButtonStyle(padding=10),
                tooltip="Settings",
                on_click=navigation_drawer(),
            )
        ],
        center_title=False,
        bgcolor=ft.Colors.with_opacity(0.04, ft.CupertinoColors.SYSTEM_BACKGROUND),
    )
    return view


def handle_nav_change(e):
    if e.control.selected_index == 0:
        switch_to_yt_tab(e)
    elif e.control.selected_index == 1:
        switch_to_sp_tab(e)
    elif e.control.selected_index == 2:
        switch_to_am_tab(e)
    elif e.control.selected_index == 3:
        switch_to_search_tab(e)


def nav_bar():
    view = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.ONDEMAND_VIDEO_ROUNDED, label="Youtube"),
            ft.NavigationBarDestination(icon=ft.Icons.MUSIC_NOTE, label="Spotify"),
            ft.NavigationBarDestination(icon=ft.Icons.APPLE_OUTLINED, label="Apple Music"),
            ft.NavigationBarDestination(icon=ft.Icons.SEARCH, label="Search"),
        ],
        on_change=handle_nav_change,
        border=ft.Border(top=ft.BorderSide(color=ft.CupertinoColors.SYSTEM_GREY2, width=0)),
        indicator_color=ft.Colors.PRIMARY_CONTAINER,
        bgcolor=ft.Colors.SURFACE,
    )
    return view


class FolderPicker(ft.Row):
    def build(self):
        view = ft.Row(
            [
                ft.Button(
                    "Select Folder",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=pick_folder,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.Padding(16, 12, 16, 12),
                    ),
                ),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.FOLDER, size=18, color=ft.Colors.PRIMARY),
                            directory_path,
                        ],
                        spacing=6,
                    ),
                    padding=ft.Padding(10, 8, 10, 8),
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    border_radius=8,
                    expand=True,
                ),
            ],
            spacing=12,
        )
        return view


def switch_to_yt_tab(e):
    e.control.page.title = "Youtube"
    set_theme(e, "Red")
    e.control.page.youtube_tab.visible = True
    e.control.page.spotify_tab.visible = False
    e.control.page.apple_music_tab.visible = False
    e.control.page.search_tab.visible = False
    e.control.page.navigation_bar.selected_index = 0
    e.control.page.update()


def switch_to_sp_tab(e):
    e.control.page.title = "Spotify"
    set_theme(e, "Green")
    e.control.page.youtube_tab.visible = False
    e.control.page.spotify_tab.visible = True
    e.control.page.apple_music_tab.visible = False
    e.control.page.search_tab.visible = False
    e.control.page.navigation_bar.selected_index = 1
    e.control.page.update()


def switch_to_am_tab(e):
    e.control.page.title = "Apple Music"
    set_theme(e, "Blue")
    e.control.page.youtube_tab.visible = False
    e.control.page.spotify_tab.visible = False
    e.control.page.apple_music_tab.visible = True
    e.control.page.search_tab.visible = False
    e.control.page.navigation_bar.selected_index = 2
    e.control.page.update()


def switch_to_search_tab(e):
    e.control.page.title = "Search"
    set_theme(e, "Purple")
    e.control.page.youtube_tab.visible = False
    e.control.page.spotify_tab.visible = False
    e.control.page.apple_music_tab.visible = False
    e.control.page.search_tab.visible = True
    e.control.page.navigation_bar.selected_index = 3
    e.control.page.update()


# --------------------------------------------------------------------------
# Downloader views (run heavy work off the UI thread)
# --------------------------------------------------------------------------

def _download_view(label, do_work):
    """Build a progress container whose button runs do_work() in a thread."""
    t = ft.Text(value="", size=14, color=ft.Colors.ON_SURFACE_VARIANT)
    t2 = ft.Text(value="0", size=13, color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE))
    pb = ft.ProgressBar(value=0, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY))
    b = ft.FilledButton(
        label,
        icon=ft.Icons.DOWNLOAD,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding(20, 12, 20, 12),
        ),
    )

    def button_clicked(e):
        page = e.control.page
        b.disabled = True
        b.update()

        def runner():
            try:
                do_work(page, t, t2, pb)
            except Exception as err:
                print(err)
                show_dialog(page, popup(page, "⚠️ Failed to download. make sure all the options are properly selected, and the link is correct. restart and try again"))
            finally:
                b.disabled = False
                b.update()

        page.run_thread(runner)

    b.on_click = button_clicked
    view = ft.Container(
        content=ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    [
                        b,
                        ft.Divider(height=12, opacity=0),
                        t,
                        pb,
                        ft.Row([t2], alignment=ft.MainAxisAlignment.END),
                    ],
                    spacing=8,
                ),
            )
        ),
        width=float("inf"),
    )
    return view


def _set_spotify_for_work(page):
    sp = get_spotify_client()
    state.use_spotify_for_metadata = sp is not None
    if sp is None:
        show_dialog(page, popup(page, "⚠️ Failed to connect to Spotify API. Continuing without Spotify API, some song metadata will not be added"))
    return sp


def _custom_label(exists_action):
    custom_labels = {
        "Replace all": "RA",
        "Skip all": "SA",
        "Determine while downloading from CLI": "",
    }
    return custom_labels.get(exists_action, "")


def youtube_downloader(url, dd, c1):
    def do_work(page, t, t2, pb):
        link = url.value
        state.file_exists_action = _custom_label(dd.value)
        sp = _set_spotify_for_work(page)

        t.value = "Downloading"
        t.update()
        yt_playlist = Playlist(link)

        totalVideoCount = len(yt_playlist.videos)
        print("Total videos in playlist: 🎦", totalVideoCount)

        for index, video in enumerate(yt_playlist.videos):
            try:
                if c1.value:
                    if video.title not in get_failed_titles():
                        continue
                print("Downloading: " + video.title)
                t2.value = f"{index+1}/{totalVideoCount}"
                pb.value = ((index + 1) / totalVideoCount)
                t.value = "Downloading: " + video.title
                t.update()
                t2.update()
                pb.update()

                audio = download_yt(video, video.title)
                if audio:
                    if sp is not None:
                        try:
                            track_url = search_spotify(f"{video.author} {video.title}", sp)
                        except Exception as e:
                            print(e)
                            track_url = None
                        track_info = get_track_info_spotify(track_url, sp) if track_url else get_track_info_youtube(video)
                    else:
                        track_info = get_track_info_youtube(video)

                    set_metadata(track_info, audio, "")
                    final_path = f"{state.music_folder_path}{os.path.basename(audio)}"
                    os.replace(audio, final_path)
                    add_downloaded(video.title, final_path, "youtube")
                    remove_failed(video.title)
            except Exception as e:
                print(f"Failed to download {video.title} due to: {e}")
                add_failed(video.title)
                continue
        t.value = "Downloaded"
        t2.value = ""
        t.update()
        print("All videos downloaded successfully!")

    return _download_view("Download Playlist", do_work)


def spotify_downloader(url, dd, c1, c2):
    def do_work(page, t, t2, pb):
        link = url.value
        state.file_exists_action = _custom_label(dd.value)
        sp = _set_spotify_for_work(page)
        if sp is None:
            t.value = "Spotify API credentials are required to read playlists/albums. Open the menu (top-right) and add your Spotify Client ID and Secret, then retry."
            t.update()
            return

        t.value = "Fetching Playlist meta data (dont freak out if it takes a while 😅 it will take about a minute for 300 songs)"
        t.update()

        if "track" in link:
            songs = [get_track_info(link, sp)]
        elif "playlist" in link:
            songs = get_playlist_info(link, sp)
        else:
            songs = get_album_info(link, sp)
        if not songs:
            t.value = "No songs to download."
            t.update()
            return

        t.value = "Starting Download"
        t.update()
        downloaded_names = set()

        totalVideoCount = len(songs)
        for i, track_info in enumerate(songs):
            try:
                if dd.value == "Skip all":
                    if os.path.exists(f"{state.music_folder_path}{track_info['track_title']}.mp3"):
                        print("Skipping: " + track_info["track_title"])
                        continue
                if c1.value:
                    if track_info["track_title"] not in get_failed_titles():
                        continue
                print("Downloading: " + track_info["track_title"])
                t2.value = f"{i+1}/{totalVideoCount}"
                pb.value = ((i + 1) / totalVideoCount)
                t.value = "Downloading: " + track_info["track_title"]
                t.update()
                t2.update()
                pb.update()
                if track_info["track_title"] in downloaded_names:
                    continue

                search_term = f"{track_info['artist_name']} {track_info['track_title']} audio"
                hq_search_term = f"{track_info['track_title']} {track_info['artist_name']} {track_info['album_name']}"
                lyrics = ""
                if c2.value:
                    song = download_high_quality(hq_search_term)
                    if song == "File already exists.":
                        print("Skipping: " + track_info["track_title"])
                        continue
                    if song is None:
                        try:
                            print("No songs found for the query in high quality song server.", search_term)
                            print("Trying to download from youtube")
                            video_link = find_youtube(search_term)
                            yt = YouTube(video_link)
                            audio = download_yt(yt, search_term)
                        except Exception:
                            print("No songs found for the query in high quality song server.", search_term)
                            add_failed(track_info["track_title"])
                            print("Skipping... adding to failed downloads. redownload with low quality in next run")
                            continue
                    else:
                        artist = song['song'] + " " + song['primary_artists'] + " " + song['album']
                        diff_ratio = difflib.SequenceMatcher(None, artist.lower(), (track_info['track_title'] + " " + track_info["artist_name"] + " " + track_info["album_name"]).lower()).ratio()
                        if diff_ratio < 0.7:
                            try:
                                print("songs found for the query in high quality song server. very different from the one in spotify", search_term)
                                print("Trying to download from youtube")
                                video_link = find_youtube(search_term)
                                yt = YouTube(video_link)
                                audio = download_yt(yt, search_term)
                            except Exception:
                                print("No songs found for the query in high quality song server.", search_term)
                                add_failed(track_info["track_title"])
                                print("Skipping... adding to failed downloads. redownload with low quality in next run")
                                continue
                        elif diff_ratio < 0.9:
                            print("Artist name mismatch. Skipping...")
                            add_mismatch(track_info["track_title"], track_info["artist_name"], artist)
                            continue
                        audio = song["mp3"]
                        lyrics = song["lyrics"]
                else:
                    video_link = find_youtube(search_term)
                    yt = YouTube(video_link)
                    audio = download_yt(yt, search_term)
                if audio:
                    set_metadata(track_info, audio, lyrics)
                    sanitized_title = sanitize_filename(track_info['track_title'])
                    destination_path = os.path.join(state.music_folder_path, f"{sanitized_title}.mp3")
                    os.replace(audio, destination_path)
                    downloaded_names.add(track_info["track_title"])
                    add_downloaded(track_info["track_title"], destination_path, "spotify")
                    remove_failed(track_info["track_title"])
                else:
                    print("File exists. Skipping...")
            except Exception as e:
                tt = track_info["track_title"]
                print(f"Failed to download {tt} due to: {e}")
                add_failed(tt)
                continue
        t.value = "Downloaded"
        t2.value = ""
        t.update()
        print("All songs downloaded successfully!")
        show_dialog(page, popup(page, "All songs downloaded successfully!"))

    return _download_view("Download Playlist", do_work)


def apple_music_downloader(url, dd, c1, c2):
    def do_work(page, t, t2, pb):
        link = url.value
        state.file_exists_action = _custom_label(dd.value)
        sp = _set_spotify_for_work(page)

        t.value = "Fetching Playlist meta data (dont freak out if it takes a while 😅 it will take about a minute for 100 songs)"
        t.update()

        am_playlist = apple.get_playlist(link)

        totalVideoCount = len(am_playlist)
        print("Total songs in playlist:", totalVideoCount)

        for index, song in enumerate(am_playlist):
            try:
                if dd.value == "Skip all":
                    if os.path.exists(f"{state.music_folder_path}{song}.mp3"):
                        print("Skipping: " + song)
                        continue
                if c1.value:
                    if song not in get_failed_titles():
                        continue
                print("Downloading: " + song)
                t2.value = f"{index+1}/{totalVideoCount}"
                pb.value = ((index + 1) / totalVideoCount)
                t.value = "Downloading: " + song
                t.update()
                t2.update()
                pb.update()
                lyrics = ""
                if c2.value:
                    song_js = download_high_quality(song)
                    if song_js == "File already exists.":
                        print("Skipping: " + song)
                        continue
                    if song_js is None:
                        try:
                            print("No songs found for the query in high quality song server.", song)
                            print("Trying to download from youtube")
                            video_link = find_youtube(song)
                            yt = YouTube(video_link)
                            audio = download_yt(yt, song)
                        except Exception:
                            print("No songs found for the query in high quality song server.", song)
                            add_failed(song)
                            print("Skipping... adding to failed downloads. redownload with low quality in next run")
                            continue
                    else:
                        audio = song_js["mp3"]
                        lyrics = song_js["lyrics"]
                else:
                    video_link = find_youtube(song)
                    yt = YouTube(video_link)
                    audio = download_yt(yt, song)
                if audio:
                    if sp is not None:
                        try:
                            spotify_search_term = song.replace(" by", "").replace(" audio", "")
                            track_url = search_spotify(spotify_search_term, sp)
                        except Exception as e:
                            print(e)
                            track_url = None
                        track_info = get_track_info_spotify(track_url, sp) if track_url else get_track_info_youtube(yt)
                    else:
                        track_info = get_track_info_youtube(yt)

                    set_metadata(track_info, audio, lyrics)
                    final_path = f"{state.music_folder_path}{os.path.basename(audio)}"
                    os.replace(audio, final_path)
                    add_downloaded(song, final_path, "apple_music")
                    remove_failed(song)
            except Exception as e:
                print(f"Failed to download {song} due to: {e}")
                add_failed(song)
                continue
        t.value = "Downloaded"
        t2.value = ""
        t.update()
        print("All songs downloaded successfully!")
        show_dialog(page, popup(page, "All songs downloaded successfully!"))

    return _download_view("Download Playlist", do_work)


# --------------------------------------------------------------------------
# App entry point
# --------------------------------------------------------------------------

def main(page: ft.Page):
    init_db()
    migrate_env()

    page.adaptive = True
    page.appbar = app_bar()
    page.navigation_bar = nav_bar()
    page.theme = ft.Theme(color_scheme_seed="Red")

    folder_picker = FolderPicker()
    url = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    dd = ft.Dropdown(
        label="Song Exist Action",
        hint_text="What to do when that song already exist in your directory?",
        options=[
            ft.dropdown.Option("Replace all"),
            ft.dropdown.Option("Skip all"),
        ],
        autofocus=True,
    )
    c1 = ft.Checkbox(label="Download only failed songs", value=False)
    c2 = ft.Checkbox(label="Download high quality audio", value=False)
    gesture_detector = GestureDetector()

    def tab_layout(folder_picker, url, dd, label):
        return [
            ft.Card(
                content=ft.Container(
                    padding=16,
                    content=ft.Column(
                        [
                            folder_picker,
                            ft.Divider(height=16, opacity=0),
                            ft.Text(label, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                            url,
                            ft.Divider(height=12, opacity=0),
                            dd,
                        ],
                        spacing=6,
                    ),
                )
            ),
            ft.Divider(height=12, opacity=0),
        ]

    def _tab(*children, visible=False):
        return ft.Container(
            ft.ListView(
                [
                    ft.Container(
                        ft.Column(children, spacing=8),
padding=ft.Padding(12, 12, 12, 12),
                    )
                ],
                spacing=10,
                padding=ft.Padding(12, 0, 12, 0),
            ),
            visible=visible,
        )

    yt_children = [
        *tab_layout(folder_picker, url, dd, "Enter Youtube playlist url:"),
        ft.Row([c1], spacing=10),
        youtube_downloader(url, dd, c1),
        gesture_detector.detector,
    ]
    sp_children = [
        *tab_layout(folder_picker, url, dd, "Enter Spotify playlist or album url:"),
        ft.Row([c1, c2], spacing=14),
        spotify_downloader(url, dd, c1, c2),
        gesture_detector.detector,
    ]
    am_children = [
        *tab_layout(folder_picker, url, dd, "Enter Apple Music playlist or album url:"),
        ft.Row([c1, c2], spacing=14),
        apple_music_downloader(url, dd, c1, c2),
        gesture_detector.detector,
    ]

    youtube_tab = _tab(*yt_children, visible=True)
    spotify_tab = _tab(*sp_children, visible=False)
    apple_music_tab = _tab(*am_children, visible=False)

    # --- Search tab: allows searching artist/album and batch downloading ---
    search_query = ft.TextField(keyboard_type=ft.KeyboardType.TEXT, width=800, hint_text="Type artist, album or song and press Search", prefix_icon=ft.Icons.SEARCH)
    search_candidates_dropdown = ft.Dropdown(label="Select result", width=800, options=[], on_select=lambda e: None)
    search_result_title = ft.Text("", size=18, weight=ft.FontWeight.W_500)
    search_result_subtitle = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    search_result_image = ft.Image(src="", width=96, height=96, border_radius=12, fit=ft.BoxFit.COVER)
    search_result_box = ft.Row(
        [
            search_result_image,
            ft.Column([search_result_title, search_result_subtitle], spacing=4),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
    )
    search_progress = ft.ProgressBar(value=0, color=ft.Colors.PRIMARY, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY))
    search_progress.visible = False

    def perform_search(e):
        q = search_query.value.strip()
        if not q:
            return
        search_progress.visible = True
        search_progress.value = 0
        search_result_title.value = "Searching..."
        search_result_subtitle.value = ""
        search_result_image.src = ""
        search_btn.disabled = True
        search_progress.update()
        search_result_title.update()
        search_result_subtitle.update()
        search_result_image.update()
        search_btn.update()
        e.control.page.update()

        def runner():
            try:
                res = Search().search(q)
            except Exception as err:
                print(f"Search failed: {err}")
                res = None
            _apply_search_results(e.control.page, res)

        e.control.page.run_thread(runner)

    def _apply_search_results(page, res):
        search_btn.disabled = False
        search_progress.visible = False
        search_progress.value = 0
        if not res or res == "not found":
            search_result_title.value = "No result found"
            search_result_subtitle.value = ""
            search_result_image.src = ""
            search_candidates_dropdown.options = []
            search_candidates_dropdown.value = None
            candidates_map = {}
        else:
            candidates = []
            candidates_map = {}
            idx = 0

            def add(kind, item):
                nonlocal idx
                title = (item.get('title') or item.get('name') or item.get('perma_url') or '')[:60]
                label = f"{kind.title()}: {title}"
                key = f"c_{idx}"
                candidates.append(ft.dropdown.Option(key=key, text=label))
                candidates_map[key] = item
                idx += 1

            for a in res.get('songs', []):
                add('song', a)
            if res.get('topresult'):
                top = res['topresult']
                if top.get('type') == 'song':
                    add('song', top)
                else:
                    add('topresult', top)
            for a in res.get('artists', []):
                add('artist', a)
            for al in res.get('albums', []):
                add('album', al)

            search_candidates_dropdown.options = candidates
            search_candidates_dropdown.value = candidates[0].key if candidates else None

            if candidates:
                sel_key = search_candidates_dropdown.value
                _show_candidate(sel_key, candidates_map)

        page._search_candidates_map = candidates_map
        search_candidates_dropdown.update()
        search_result_title.update()
        search_result_subtitle.update()
        search_result_image.update()
        search_progress.update()
        search_btn.update()
        page.update()

    def _show_candidate(sel_key, candidates_map):
        sel_item = candidates_map.get(sel_key)
        if not sel_item:
            search_result_title.value = "No result"
            search_result_subtitle.value = ""
            search_result_image.src = ""
            return
        title = sel_item.get('title') or sel_item.get('name') or ''
        search_result_title.value = title + f"  ({sel_item.get('type', '')})"
        sub = []
        if sel_item.get('more_info'):
            sub.append(sel_item['more_info'].get('primary_artists') or '')
            sub.append(sel_item['more_info'].get('album') or '')
        elif sel_item.get('type') == 'album':
            sub.append(f"{len(sel_item.get('list') or [])} tracks")
        search_result_subtitle.value = " · ".join([s for s in sub if s])
        search_result_image.src = sel_item.get('image') or sel_item.get('album_art') or ''

    def candidate_changed(e):
        sel_key = e.control.value
        candidates_map = getattr(e.control.page, '_search_candidates_map', {})
        _show_candidate(sel_key, candidates_map)
        search_result_title.update()
        search_result_subtitle.update()
        search_result_image.update()
        e.control.page.update()

    search_candidates_dropdown.on_select = candidate_changed

    def start_download(e):
        sel_key = search_candidates_dropdown.value
        candidates_map = getattr(e.control.page, '_search_candidates_map', {})
        sel = candidates_map.get(sel_key)
        if not sel:
            print("Nothing selected to download")
            return

        async def run_download():
            s = Search()
            typ = sel.get('type')
            if typ == 'artist':
                songs = s.get_songs_from_artist(sel) or []
            elif typ == 'album':
                songs = s.get_songs_from_album(sel) or []
            elif typ == 'song':
                enriched = s.enrich_song(sel.get('id'))
                songs = [enriched] if enriched else []
            else:
                print("Unsupported type for download")
                return
            if not songs:
                print("No songs found to download")
                return
            total = len(songs)
            print(f"Starting download of {total} songs...")
            song_count.value = f"Songs to download: {total}"
            song_count.update()
            e.control.page.update()
            sem = asyncio.Semaphore(10)
            timeout = aiohttp.ClientTimeout(total=120)
            completed = 0
            async with aiohttp.ClientSession(timeout=timeout) as session:
                tasks = [DownloadSong(song, output_folder=state.music_folder_path, skip=True).download_song_async(session, sem) for song in songs]
                for fut in asyncio.as_completed(tasks):
                    try:
                        path = await fut
                        print(f"Downloaded: {path}, {completed}/{total} songs. ")
                        completed += 1
                        search_progress.value = completed / total
                        search_progress.update()
                        downloaded_count.value = f"Downloaded {completed}/{total} songs."
                        downloaded_count.update()
                        e.control.page.update()
                    except Exception as ex:
                        print(f"Song download failed: {ex}")
            if completed == total:
                downloaded_count.value = f"all done! Downloaded {completed} songs."
            else:
                downloaded_count.value = f"Download completed with errors. Downloaded {completed}/{total} songs. JUST CLICK DOWNLOAD AGAIN TO GET THE MISSED ONES"
            downloaded_count.update()
            e.control.page.update()

        def runner():
            try:
                asyncio.run(run_download())
                print("Download runner completed")
            except Exception as err:
                print(f"Download runner failed: {err}")

        e.control.page.run_thread(runner)

    search_btn = ft.FilledButton(
        "Search",
        icon=ft.Icons.SEARCH,
        on_click=perform_search,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )
    download_btn = ft.FilledButton(
        "Download",
        icon=ft.Icons.DOWNLOAD,
        on_click=start_download,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding(24, 14, 24, 14),
        ),
    )
    song_count = ft.Text("", size=14, weight=ft.FontWeight.W_500)
    downloaded_count = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)

    search_tab = ft.Container(
        ft.ListView(
            [
                ft.Container(
                    ft.Column(
                        [
                            folder_picker,
                            ft.Divider(height=12, opacity=0),
                            ft.Card(
                                content=ft.Container(
                                    padding=16,
                                    content=ft.Column([
                                        ft.Text("Search songs, artists or albums",
                                                size=15, weight=ft.FontWeight.W_600),
                                        ft.Text("Search on JioSaavn (Saavn) and batch download tracks.",
                                                size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Divider(height=12, opacity=0),
                                        ft.Row([search_query, search_btn], spacing=8),
                                        ft.Divider(height=8, opacity=0),
                                        search_candidates_dropdown,
                                        ft.Divider(height=8, opacity=0),
                                        search_result_box,
                                    ], spacing=10),
                                )
                            ),
                            ft.Divider(height=8, opacity=0),
                            ft.Card(
                                content=ft.Container(
                                    padding=16,
                                    content=ft.Column([
                                        download_btn,
                                        song_count,
                                        search_progress,
                                        downloaded_count,
                                    ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.START),
                                )
                            ),
                            gesture_detector.detector,
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding(12, 12, 12, 12),
                )
            ],
            spacing=10,
        ),
        visible=False,
    )

    page.spotify_tab = spotify_tab
    page.youtube_tab = youtube_tab
    page.apple_music_tab = apple_music_tab
    page.search_tab = search_tab
    

    page.add(
        youtube_tab, spotify_tab, apple_music_tab, search_tab
    )


if __name__ == "__main__":
    ft.run(main=main)
