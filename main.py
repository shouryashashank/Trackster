import flet as ft
import time
import os
from pytube import Playlist
from moviepy.editor import *
from mutagen.easyid3 import EasyID3
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.id3 import APIC, ID3
import urllib.request
from tqdm import tqdm
from dotenv import load_dotenv
import os
import re
import shutil
import time
import urllib.request
import pickle
from tqdm import tqdm
import spotipy
from moviepy.editor import *
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from pytube import YouTube
import pytube.exceptions
from rich.console import Console
from spotipy.oauth2 import SpotifyClientCredentials
from yarl import URL
import ssl
import sys, io
from bs4 import BeautifulSoup
import apple
import yt_dlp
from yt_dlp.utils import download_range_func
from moviepy.editor import *
import base64
from pyDes import *
import requests
import os
import urllib.request
import time
from moviepy.editor import AudioFileClip
from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TDRC, TRCK, TSRC, USLT, APIC
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import difflib
from search import Search, DownloadSong, Song



# buffer = io.StringIO()
# sys.stdout = sys.stderr = buffer

ssl._create_default_https_context = ssl._create_unverified_context
# pyinstaller --noconfirm --onefile --windowed --icon "D:\Code\github\music\Trackster\icon_for_an_app_called_trakster_used_to_download_spotify_and_youtube_playlist-removebg-preview.ico" --name "Trackster_101_Fix_Premium"  "D:\Code\github\music\Trackster\main.py"
file_exists_action=""
failed_download = False
high_quality = False
search_base_url = "https://www.jiosaavn.com/api.php?__call=autocomplete.get&_format=json&_marker=0&cc=in&includeMetaTags=1&query="
song_base_url = "https://www.jiosaavn.com/api.php?__call=song.getDetails&cc=in&_marker=0%3F_marker%3D0&_format=json&pids="
lyrics_base_url = "https://www.jiosaavn.com/api.php?__call=lyrics.getLyricvideo_files&ctx=web6dot0&api_version=4&_format=json&_marker=0%3F_marker%3D0&lyrics_id="
music_folder_path = "music-yt/"   # path to save the downloaded music
# SPOTIPY_CLIENT_ID = "" # Spotify API client ID  # keep blank if you dont need spotify metadata
# SPOTIPY_CLIENT_SECRET = ""  # Spotify API client secret

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def prompt_exists_action():
    """ask the user what happens if the file being downloaded already exists"""
    global file_exists_action
    if file_exists_action == "SA":  # SA == 'Skip All'
        return False
    elif file_exists_action == "RA":  # RA == 'Replace All'
        return True
    
    print("This file already exists.")
    while True:
        resp = (
            input("replace[R] | replace all[RA] | skip[S] | skip all[SA]: ")
            .upper()
            .strip()
        )
        if resp in ("RA", "SA"):
            file_exists_action = resp
        if resp in ("R", "RA"):
            return True
        elif resp in ("S", "SA"):
            return False
        print("---Invalid response---")

def make_alpha_numeric(string):
    return ''.join(char for char in string if char.isalnum())

def download_yt(yt,search_term):
    """download the video in mp3 format from youtube"""
    # remove chars that can't be in a windows file name
    yt.title = "".join([c for c in yt.title if c not in ['/', '\\', '|', '?', '*', ':', '>', '<', '"']])
    # don't download existing files if the user wants to skip them
    exists = os.path.exists(f"{music_folder_path}{yt.title}.mp3")
    if exists and not prompt_exists_action():
        return False

    # download the music
    yt_opts = {
        'extract_audio': True,
        'format': 'bestaudio', 
        'outtmpl': f"{music_folder_path}tmp/{yt.title}.mp4",
        }
    with yt_dlp.YoutubeDL(yt_opts) as ydl:
        ydl.download(yt.watch_url)
    # max_retries = 3
    # attempt = 0
    # video = None

    # while attempt < max_retries:
    #     try:
    #         video = yt.streams.filter(only_audio=True).first()
    #         if video:
    #             break
    #     except Exception as e:
    #         print(f"Attempt {attempt + 1}  {search_term} failed due to: {e}")
    #         attempt += 1
    # if not video:
    #     print(f"Failed to download {search_term}")
    #     # check if a file named failed_downloads.txt exists if not create one and append the failed download
    #     if not os.path.exists("failed_downloads.txt"):
    #         with open("failed_downloads.txt", "w") as f:
    #             f.write(f"{search_term}\n")
    #     else:
    #         with open("failed_downloads.txt", "a") as f:
    #             f.write(f"{search_term}\n")
    #     return False
    # vid_file = video.download(output_path=f"{music_folder_path}tmp")
    # # convert the downloaded video to mp3
    # base = os.path.splitext(vid_file)[0]
    # audio_file = base + ".mp3"
    # mp4_no_frame = AudioFileClip(vid_file)
    # mp4_no_frame.write_audiofile(audio_file, logger=None)
    # mp4_no_frame.close()
    # os.remove(vid_file)
    # os.replace(audio_file, f"{music_folder_path}tmp/{yt.title}.mp3")
    video_file = f"{music_folder_path}tmp/{yt.title}.mp4"
    audio_file = f"{music_folder_path}tmp/{yt.title}.mp3"
    FILETOCONVERT = AudioFileClip(video_file)
    FILETOCONVERT.write_audiofile(audio_file)
    FILETOCONVERT.close()
    os.remove(video_file)
    audio_file = f"{music_folder_path}tmp/{yt.title}.mp3"
    return audio_file

def decrypt_url(url):
    des_cipher = des(b"38346591", ECB, b"\0\0\0\0\0\0\0\0",
                     pad=None, padmode=PAD_PKCS5)
    enc_url = base64.b64decode(url.strip())
    dec_url = des_cipher.decrypt(enc_url, padmode=PAD_PKCS5).decode('utf-8')
    dec_url = dec_url.replace("_96.mp4", "_320.mp4")
    return dec_url

def search_song(query):
    search_url = search_base_url + query
    response = requests.get(search_url)
    # First, try to find a song in the topquery data if available
    try:
        topquery_data = response.json().get('topquery', {}).get('data', [])
        for item in topquery_data:
            if item.get('type') == 'song' and item.get('id'):
                # Use the first song id found in topquery data
                best_song_id = item['id']
                best_diff = 1.0  # highest similarity; we will exit early if exact match found
                break
        else:
            best_song_id = None
            best_diff = 0
    except Exception:
        best_song_id = None
        best_diff = 0

    # If a topquery song wasn't found, fall back to the existing logic
    if not best_song_id:
        songs = response.json().get('songs', {}).get('data', [])
        if not songs:
            return "No songs found for the query."
        song_id = response.json()['songs']['data'][0]['id']
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
        return "No suitable song found."
    
    song_url = song_base_url + best_song_id
    response = requests.get(song_url)
    song_url = response.json()[best_song_id]['encrypted_media_url']
    primary_artists = response.json()[best_song_id]['primary_artists']
    album = response.json()[best_song_id]['album']
    song = response.json()[best_song_id]['song']
    release_date = response.json()[best_song_id]['release_date']

    has_lyrics = response.json()[best_song_id]['has_lyrics'] == 'true'
    lyrics = ""
    if has_lyrics:
        lyrics_url = lyrics_base_url + best_song_id
        try:
            lyrics_response = requests.get(lyrics_url)
            lyrics = lyrics_response.json()['lyrics']
        except Exception as e:
            print(f"Failed to get lyrics for {song}: {e}")
    
    return {
    "url": decrypt_url(song_url),
    "primary_artists": primary_artists,
    "album": album,
    "song": song,
    "release_date": release_date,
    "lyrics": lyrics
    }

def download_high_quality(search_term):
    song = search_song(search_term)
    if song == "No songs found for the query.": return song
    song_url = song['url']
    if not isinstance(song, dict):
        return "Unexpected response format."
    file  = f"{music_folder_path}{os.path.basename(song['song'])}.mp3"
    # check if the file already exists
    if os.path.exists(file):
        if not prompt_exists_action():
            return "File already exists."
    response = requests.get(song_url)
    # create new folder if it doesn't exist "tmp"
    if not os.path.exists(f"{music_folder_path}tmp"):
        os.makedirs(f"{music_folder_path}tmp")
    sanitized_song_name = sanitize_filename(song['song'])
    video_file = f"{music_folder_path}tmp/{sanitized_song_name}.mp4"
    audio_file = f"{music_folder_path}tmp/{sanitized_song_name}.mp3"
    with open(video_file, "wb") as f:
        f.write(response.content)
    FILETOCONVERT = AudioFileClip(video_file)
    FILETOCONVERT.write_audiofile(audio_file,bitrate="3000k")
    FILETOCONVERT.close()
    os.remove(video_file)
    song["mp3"] = audio_file
    return song
# def set_metadata(metadata, file_path,lyrics):
#     """adds metadata to the downloaded mp3 file"""

#     mp3file = ID3(file_path)

#     # add metadata
#     mp3file["albumartist"] = metadata["artist_name"]
#     mp3file["artist"] = metadata["artists"]
#     mp3file["album"] = metadata["album_name"]
#     mp3file["title"] = metadata["track_title"]
#     mp3file["date"] = metadata["release_date"]
#     mp3file["tracknumber"] = str(metadata["track_number"])
#     mp3file["isrc"] = metadata["isrc"]
#     if lyrics != "":
#         ulyrics = mp3file.getall('USLT')[0]

#         # change the lyrics text
#         ulyrics.text = lyrics
#         mp3file.setall('USLT', [ulyrics])
#     mp3file.save()

def set_metadata(metadata, file_path, lyrics):
    """adds metadata to the downloaded mp3 file"""

    mp3file = ID3(file_path)

    # add metadata
    mp3file["TPE1"] = TPE1(encoding=3, text=metadata["artist_name"])
    mp3file["TPE2"] = TPE2(encoding=3, text=metadata["artists"])
    mp3file["TALB"] = TALB(encoding=3, text=metadata["album_name"])
    mp3file["TIT2"] = TIT2(encoding=3, text=metadata["track_title"])
    mp3file["TDRC"] = TDRC(encoding=3, text=metadata["release_date"])
    mp3file["TRCK"] = TRCK(encoding=3, text=str(metadata["track_number"]))
    mp3file["TSRC"] = TSRC(encoding=3, text=metadata["isrc"])
    if lyrics != "":
        # Check if USLT frame exists, if not create a new one
        if mp3file.getall('USLT'):
            ulyrics = mp3file.getall('USLT')[0]
            ulyrics.text = lyrics
        else:
            ulyrics = USLT(encoding=3, desc='', text=lyrics)
            mp3file.add(ulyrics)
    mp3file.save()

    # add album cover
    audio = ID3(file_path)
    with urllib.request.urlopen(metadata["album_art"]) as albumart:
        audio["APIC"] = APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc=u'Cover',
            data=albumart.read()
        )
    audio.save()

    # add album cover
    audio = ID3(file_path)
    with urllib.request.urlopen(metadata["album_art"]) as albumart:
        audio["APIC"] = APIC(
            encoding=3, mime="image/jpeg", type=3, desc="Cover", data=albumart.read()
        )
    audio.save(v2_version=3)

def search_spotify(search_term : str, sp)->str:
    """search for the track on spotify"""
    search_results = sp.search(search_term, type="track", limit=1)
    if search_results["tracks"]["total"] == 0:
        return None
    track = search_results["tracks"]["items"][0]
    return track["external_urls"]["spotify"]

def get_track_info_spotify(track_url,sp):
    res = requests.get(track_url)
    if res.status_code != 200:
        # retry 3 times
        for i in range(3):
            res = requests.get(track_url)
            if res.status_code == 200:
                break
    if res.status_code != 200:
        print("Invalid Spotify track URL")

    track = sp.track(track_url)

    track_metadata = {
        "artist_name": track["artists"][0]["name"],
        "track_title": track["name"],
        "track_number": track["track_number"],
        "isrc": track["external_ids"]["isrc"],
        "album_art": track["album"]["images"][1]["url"],
        "album_name": track["album"]["name"],
        "release_date": track["album"]["release_date"],
        "artists": [artist["name"] for artist in track["artists"]],
    }

    return track_metadata

def get_track_info_youtube(video):

    track_metadata = {
        "artist_name": video.author,
        "track_title":  video.title,
        "track_number": 0,
        "isrc": "",
        "album_art": video.thumbnail_url,
        "album_name": video.author,
        "release_date": video.publish_date.strftime("%Y-%m-%d"),
        "artists": [video.author],
    }

    return track_metadata

def ensure_folder_path_ends_with_slash(folder_path):
    if not folder_path.endswith(os.sep):
        folder_path += os.sep
    return folder_path




    

# Open directory dialog
def get_directory_result(e: ft.FilePickerResultEvent):
    directory_path.value = e.path if e.path else "Cancelled!"
    directory_path.update()
    global music_folder_path
    music_folder_path = ensure_folder_path_ends_with_slash(e.path)
    print(music_folder_path)

get_directory_dialog = ft.FilePicker(on_result=get_directory_result)
directory_path = ft.Text()
def set_theme(e,color):
    e.control.page.theme = ft.Theme(color_scheme_seed=color)
    e.control.page.update()
def progress_bar():
    t = ft.Text(value="")
    t2 = ft.Text(value = "0")
    pb = ft.ProgressBar(value=0)
    # img = "https://picsum.photos/200/200?0"
    def button_clicked(e):
        t.value = "Downloading"
        t.update()
        b.disabled = True
        b.update()
        
        for i in range(0, 101):
            # view.content.controls[0].image_src = f"https://picsum.photos/id/{i+10}/200/300"
            # view.content.controls[0].image_opacity = 0.2
            t2.value = i
            pb.value = i * 0.01
            time.sleep(0.1)
            view.update()
            t2.update()
            pb.update()
        t.value = ""
        t2.value = ""
        t.update()
        b.disabled = False
        b.update()
    
    b = ft.ElevatedButton("Download Playlist", width=200000, on_click=button_clicked)
    view = ft.Container(
        
        content = ft.Column(
            [
                b,
                ft.Container(
                    # image_src=img,
                    # image_opacity= 0,
                    # image_fit= ft.ImageFit.COVER,
                    padding=10,
                    content=ft.Column([
                        ft.Divider(opacity=0),
                        t, 
                        pb,
                        t2,
                        ft.Divider(opacity=0)]),
                        
                    )
                
            ],)
    )
    return view
        
   
class GestureDetector:
    def __init__(self):
        self.detector = ft.GestureDetector(
            on_pan_update=self.on_pan_update
        )
    def on_pan_update(self,e):
        if e.delta_x<0:
            switch_to_sp_tab(e)
        elif e.delta_x>0:
            switch_to_yt_tab(e)
def navigation_drawer():
    spotify_client_id = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    spotify_client_secret = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    spotify_client_id.value = os.getenv('SPOTIPY_CLIENT_ID')
    spotify_client_secret.value = os.getenv('SPOTIPY_CLIENT_SECRET')
    def save_app_settings(e):
        try:
            env_str = "SPOTIPY_CLIENT_ID=" + spotify_client_id.value + "\nSPOTIPY_CLIENT_SECRET=" + spotify_client_secret.value
            with open(".env", "a+") as f:
                f.seek(0)  # Move the cursor to the beginning of the file
                f.truncate()  # Clear the file content
                f.write(env_str)
        except Exception as e:
            print(e)
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
                            ft.IconButton(icon=ft.icons.CLOSE,on_click=close_end_drawer)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    ft.Text("Spotify client id:"),
                    spotify_client_id,
                    ft.Text("Spotify client secret:"),
                    spotify_client_secret,
                    ft.ElevatedButton("Save",on_click=save_app_settings),
                    ft.TextButton("How To Get Spotify api api Keys",on_click=yt_page_launch),
                    ft.TextButton("Contact support",on_click=email_page_launch),
                    ft.TextButton("Get version with api key already added.",on_click=petreon_page_launch),
                    ft.TextButton("Help me buy a new phone",on_click=petreon_page_launch),
                    ft.TextButton("See source code",on_click=github_page_launch)

                ]
            ),
            minimum_padding= 10,
        )
    ])
    
    def open_end_drawer(e):
        e.control.page.end_drawer = end_drawer
        end_drawer.open = True
        e.control.page.update()

    return open_end_drawer
    

def popup(page,text):
    return ft.AlertDialog(
        title=ft.Text(text),
        on_dismiss=lambda e: page.add(ft.Text("Non-modal dialog dismissed")),
    )

def drop_down():
    
    return ft.Dropdown(
            label="Song Exist Action",
            hint_text="What to do when that song already exist in your directory?",
            options=[
                ft.dropdown.Option("Replace all"),
                ft.dropdown.Option("Skip all"),
            ],
            autofocus=True,
        )

def app_bar():
    view = ft.AppBar(
        title=ft.Text("Trackster"),
        actions=[
            ft.IconButton(ft.icons.MENU, style=ft.ButtonStyle(padding=0),on_click=navigation_drawer())
        ],
        bgcolor=ft.colors.with_opacity(0.04, ft.cupertino_colors.SYSTEM_BACKGROUND),
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
            ft.NavigationBarDestination(icon=ft.icons.ONDEMAND_VIDEO_ROUNDED, label="Youtube"),
            ft.NavigationBarDestination(icon=ft.icons.MUSIC_NOTE, label="Spotify"),
            ft.NavigationBarDestination(icon=ft.icons.APPLE_OUTLINED, label="Apple Music"),
            ft.NavigationBarDestination(icon=ft.icons.SEARCH, label="Search"),
        ],
        on_change=handle_nav_change,
        border=ft.Border(
            top=ft.BorderSide(color=ft.cupertino_colors.SYSTEM_GREY2, width=0)
        ),
    )
    return view 


class FolderPicker(ft.Row):
    def build(self):
        view = ft.Row(
                [
                    ft.ElevatedButton(
                        "Select Folder",
                        icon=ft.icons.FOLDER_OPEN,
                        on_click=lambda _: get_directory_dialog.get_directory_path()
                    ),
                    directory_path,
                    # ft.Text(value="Select Output Direcotry to save the playlist", italic=False, selectable=False, style='labelSmall', ),
                ]
            )
        return view
def switch_to_yt_tab(e):
    e.control.page.title= "Youtube"
    set_theme(e,"Red")
    e.control.page.youtube_tab.visible = True
    e.control.page.spotify_tab.visible = False
    e.control.page.apple_music_tab.visible = False
    e.control.page.search_tab.visible = False
    e.control.page.navigation_bar.selected_index = 0
    e.control.page.update()

def switch_to_sp_tab(e):
    e.control.page.title= "Spotify"
    set_theme(e,"Green")
    e.control.page.youtube_tab.visible = False
    e.control.page.spotify_tab.visible = True
    e.control.page.apple_music_tab.visible = False
    e.control.page.search_tab.visible = False
    e.control.page.navigation_bar.selected_index = 1
    e.control.page.update()

def switch_to_am_tab(e):
    e.control.page.title= "Apple Music"
    set_theme(e,"Blue")
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

def get_track_info(track_url, sp, max_retries=3, initial_timeout=1):
    """
    Get track metadata from Spotify with retry logic for timeouts.
    
    Args:
        track_url (str): Spotify track URL
        sp: Authenticated Spotipy client
        max_retries (int): Maximum number of retry attempts
        initial_timeout (float): Initial timeout between retries in seconds (will exponentially increase)
    
    Returns:
        dict: Track metadata or None if all attempts fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):  # +1 for the initial attempt
        try:
            track = sp.track(track_url)
            isrc = track["external_ids"].get("isrc") if track.get("external_ids") else None

            track_metadata = {
                "artist_name": track["artists"][0]["name"],
                "track_title": track["name"],
                "track_number": track["track_number"],
                "isrc": isrc,
                "album_art": track["album"]["images"][1]["url"],
                "album_name": track["album"]["name"],
                "release_date": track["album"]["release_date"],
                "artists": [artist["name"] for artist in track["artists"]],
            }
            
            return track_metadata
            
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = initial_timeout * (2 ** attempt)  # Exponential backoff
                print(f"Attempt {attempt + 1} failed. Retrying in {wait_time} seconds... Error: {str(e)}")
                time.sleep(wait_time)
            continue
    
    # If we get here, all attempts failed
    print(f"Failed to get track info after {max_retries + 1} attempts. Last error: {str(last_exception)}")
    return None

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
        except:
            count += 1
    else:
        raise ValueError("Please check your internet connection and try again later.")
        

    search_results = re.findall(r"watch\?v=(\S{11})", response.read().decode())
    first_vid = "https://www.youtube.com/watch?v=" + search_results[0]

    return first_vid

def get_playlist_info(sp_playlist,sp):
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

    tracks = [item["track"] for item in tracks_item]
    tracks_info = []
    track_id = []
    # load tracks_id from synced.txt
    if os.path.exists("synced.txt"):
        with open("synced.txt", "r") as f:
            track_id = f.read().splitlines()
    updated_tracks = []
    try:
        for track in tqdm(tracks):
            # check if the track['id'] is not none
            if track["id"] is None:
                continue

            if track["id"] in track_id:
                continue
            
            updated_tracks.append(track["id"])

            track_url = f"https://open.spotify.com/track/{track['id']}"
            track_info = get_track_info(track_url,sp)
            # make a progress bar
            
            tracks_info.append(track_info)
    except Exception as e:
        print(f"Failed to get track info for {track['name']} due to: {e}")
    # save the updated tracks_id to synced_updated.txt
    try:
        with open("synced_updated.txt", "w") as f:
            f.write("\n".join(updated_tracks))
    except Exception as e:
        print(f"Failed to save updated tracks: {e}")
    return tracks_info

def get_album_info(sp_album,sp):
    res = requests.get(sp_album)
    if res.status_code != 200:
        raise ValueError("Invalid Spotify playlist URL")
    # pl = sp.album(sp_album)
    
    playlist = sp.album_tracks(sp_album)

    tracks_item = playlist['items']

    while playlist['next']:
        playlist = sp.next(playlist)
        tracks_item.extend(playlist['items'])

    # tracks = [item["track"] for item in tracks_item]
    tracks_info = []
    track_id = []
    # load tracks_id from synced.txt
    if os.path.exists("synced.txt"):
        with open("synced.txt", "r") as f:
            track_id = f.read().splitlines()
    updated_tracks = []
    def process_track(track):
        updated_tracks.append(track["id"])
        if track["id"] in track_id:
            return None
        track_url = f"https://open.spotify.com/track/{track['id']}"
        return get_track_info(track_url, sp)

    with ThreadPoolExecutor() as executor:
        results = list(tqdm(executor.map(process_track, tracks_item), total=len(tracks_item)))

    tracks_info.extend(filter(None, results))
        # make a progress bar
        
    # save the updated tracks_id to synced_updated.txt
    with open("synced_updated.txt", "w") as f:
        f.write("\n".join(updated_tracks))
    return tracks_info

def main(page: ft.Page):
    page.adaptive = True
    page.appbar = app_bar()
    page.navigation_bar = nav_bar()
    # hide all dialogs in overlay
    folder_picker = FolderPicker()
    url = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    pb = ft.ProgressBar()
    c1 = ft.Checkbox(label="Download only failed songs", value=False)
    c2 = ft.Checkbox(label="Download high quality audio", value=False)
    # c2 = ft.Checkbox(label="Download high quality audio (🙏 please get it from petreon or build from source to eneble this)", value=False,disabled=True)
    # def switch_to_yt_tab(e):
    #     page.title= "Youtube"
    #     youtube_tab.visible = True
    #     spotify_tab.visible = False
    #     page.navigation_bar.selected_index = 0
    #     page.update
    
    # def switch_to_sp_tab(e):
    #     page.title= "Spotify"
    #     youtube_tab.visible = False
    #     spotify_tab.visible = True
    #     page.navigation_bar.selected_index = 1
    #     page.update
    page.theme = ft.Theme(color_scheme_seed="Red")   
    gesture_detector = GestureDetector()
    dd = ft.Dropdown(
            label="Song Exist Action",
            hint_text="What to do when that song already exist in your directory?",
            options=[
                ft.dropdown.Option("Replace all"),
                ft.dropdown.Option("Skip all"),
            ],
            autofocus=True,
        )
    # link = "https://www.youtube.com/watch?v=uelHwf8o7_U&list=PLGyF7r13ifSqeOxzefZfjiSgSoBK2W4fQ"
    # exists_action ="Replace all"
    def downloader():
        try:
            t = ft.Text(value="")
            t2 = ft.Text(value = "0")
            pb = ft.ProgressBar(value=0)
            def button_clicked(e):
                link = url.value
                exists_action = dd.value
                t.value = "Downloading"
                t.update()
                b.disabled = True
                b.update()
                custom_labels = {
                    "Replace all": "RA",
                    "Skip all": "SA",
                    "Determine while downloading from CLI": "",
                }
                global file_exists_action 
                file_exists_action = custom_labels[exists_action]
                use_spotify_for_metadata = True
                try:
                    load_dotenv()
                    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
                    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
                    client_credentials_manager = SpotifyClientCredentials(
                        client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET
                    )
                    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                except Exception as e:
                    use_spotify_for_metadata = False
                    print(f"Failed to connect to Spotify API: {e}")
                    print("Continuing without Spotify API, some song metadata will not be added")
                    exception_popup = popup(page,f"⚠️ Failed to connect to Spotify API: {e}  .  Continuing without Spotify API, some song metadata will not be added")
                    page.open(exception_popup)
                # link = input("Enter YouTube Playlist URL: ✨")

                yt_playlist = Playlist(link)



                totalVideoCount = len(yt_playlist.videos)
                print("Total videos in playlist: 🎦", totalVideoCount)

                for index, video in enumerate(yt_playlist.videos):
                    try:
                        if c1.value:
                            if os.path.exists("failed_downloads.txt"):
                                with open("failed_downloads.txt", "r") as f:
                                    failed_songs = f.read().splitlines()
                                if video.title not in failed_songs:
                                    continue
                        print("Downloading: "+video.title)
                        t2.value = f"{index+1}/{totalVideoCount}"
                        pb.value = ((index+1)/totalVideoCount)
                        
                        view.update()
                        t2.update()
                        pb.update()
                    
                        audio = download_yt(video,video.title)
                        if audio:
                            if(use_spotify_for_metadata):
                                try:
                                    track_url = search_spotify(f"{video.author} {video.title}",sp)
                                except Exception as e:
                                    print(e)
                                    track_url = None
                                if not track_url:
                                    track_info = get_track_info_youtube(video)
                                else:
                                    track_info = get_track_info_spotify(track_url,sp)
                            else:
                                track_info = get_track_info_youtube(video)

                            set_metadata(track_info, audio,"")
                            os.replace(audio, f"{music_folder_path}{os.path.basename(audio)}")
                    except Exception as e:
                        print(f"Failed to download {video.title} due to: {e}")
                        with open("failed_downloads.txt", "a") as f:
                            f.write(f"{video.title}\n")
                        continue
                t.value = "Downloaded"
                t2.value = ""
                t.update()
                b.disabled = False
                b.update()
                print("All videos downloaded successfully!")
            b = ft.ElevatedButton("Download Playlist", width=200000, on_click=button_clicked)
            view = ft.Container(
                
                content = ft.Column(
                    [
                        b,
                        ft.Container(
                            # image_src=img,
                            # image_opacity= 0,
                            # image_fit= ft.ImageFit.COVER,
                            padding=10,
                            content=ft.Column([
                                ft.Divider(opacity=0),
                                t, 
                                pb,
                                t2,
                                ft.Divider(opacity=0)]),
                                
                            )
                        
                    ],)
            )
            return view
            # return "All videos downloaded successfully!"
        except Exception as e:
            print(e)
            exception_popup = popup(page,f"⚠️ Failed to download. make sure all the options are properly selected, and the link is correct. restart and try again")
            page.open(exception_popup)

    def downloader_spotify():
        t = ft.Text(value="")
        t2 = ft.Text(value = "0")
        pb = ft.ProgressBar(value=0)
        def button_clicked(e):
            print("Downloading: here you will se a progress bar. if that progress bar is stuck that means, spotify is rate limiting you. wait for a while and try again or download the 'no spotify key' version. for now there is no work around this. sorry for the inconvenience")
            link = url.value
            exists_action = dd.value
            t.value = "Fetching Playlist meta data (dont freak out if it takes a while 😅 it will take about a minute for 300 songs)"
            t.update()
            b.disabled = True
            b.update()
            try:
                custom_labels = {
                    "Replace all": "RA",
                    "Skip all": "SA",
                    "Determine while downloading from CLI": "",
                }
                global file_exists_action 
                file_exists_action = custom_labels[exists_action]
                use_spotify_for_metadata = True
                try:
                    load_dotenv()
                    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
                    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
                    client_credentials_manager = SpotifyClientCredentials(
                        client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET
                    )
                    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                except Exception as e:
                    use_spotify_for_metadata = False
                    print(f"Failed to connect to Spotify API: {e}")
                    print("Continuing without Spotify API, some song metadata will not be added")
                    exception_popup = popup(page,f"⚠️ Failed to connect to Spotify API: {e}  .  Continuing without Spotify API, some song metadata will not be added")
                    page.open(exception_popup)
                # link = input("Enter YouTube Playlist URL: ✨")
            
                if "track" in link:
                    songs = [get_track_info(link,sp)]
                elif "playlist" in link:
                    songs = get_playlist_info(link,sp)
                else:
                    songs = get_album_info(link,sp)
                # pickle the songs list
                # with open("songs.pkl", "wb") as f:
                #     pickle.dump(songs, f)
                # with open("songs.pkl", "rb") as f:
                #     songs = pickle.load(f)
                t.value = "Starting Download"
                t.update()
                downloaded = 0
                song_name_list = []
                if os.path.exists("song_names.txt"):
                    if input("only download the songs that are not already downloaded [y/n]: ").strip() == "y":  
                        with open("song_names.txt", "r") as f:
                            song_name_list = f.read().splitlines()
                # check if downloaded.txt exists
                # if os.path.exists("downloaded.txt"):
                #     if input("Resume download? [y/n]: ").strip() == "y":  
                #         with open("downloaded.txt", "r") as f:
                #             downloaded = int(f.read())
                totalVideoCount = len(songs)
                for i, track_info in enumerate(songs):
                    try:
                        #  check if the song is already downloaded at  f"{music_folder_path}{search_term}.mp3" 
                        if dd.value == "Skip all":
                            if os.path.exists(f"{music_folder_path}{track_info['track_title']}.mp3"):
                                print("Skipping: "+track_info["track_title"])
                                continue
                        if c1.value:
                            if os.path.exists("failed_downloads.txt"):
                                with open("failed_downloads.txt", "r", encoding="utf-8") as f:
                                    failed_songs = f.read().splitlines()
                                if track_info["track_title"] not in failed_songs:
                                    continue
                        print("Downloading: "+track_info["track_title"])
                        t2.value = f"{i+1}/{totalVideoCount}"
                        pb.value = ((i+1)/totalVideoCount)
                        t.value = "Downloading: "+track_info["track_title"]
                        t.update()
                        view.update()
                        t2.update()
                        pb.update()
                        if track_info["track_title"] in song_name_list:
                            continue
                        if downloaded > i:
                            continue
                        search_term = f"{track_info['artist_name']} {track_info['track_title']} audio"
                        hq_search_term = f"{track_info['track_title']} {track_info['artist_name']} {track_info['album_name']}"
                        lyrics = ""
                        if c2.value:
                            song = download_high_quality(hq_search_term)
                            if song == "No songs found for the query.":
                                try:
                                    print("No songs found for the query in high quality song server." , search_term)
                                    print("Trying to download from youtube")
                                    video_link = find_youtube(search_term)
                                    yt = YouTube(video_link)
                                    audio = download_yt(yt,search_term)
                                except Exception as e:
                                    print("No songs found for the query in high quality song server." , search_term)
                                    tt = track_info["track_title"]
                                    with open("failed_downloads.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{tt}\n")
                                    print("Skipping... adding to failed_downloads.txt redownload with low quality in next run" )
                                    continue
                            else:
                                artist = song['song'] + " " + song['primary_artists'] + " " + song['album']
                                diff_ratio = difflib.SequenceMatcher(None, artist.lower(), (track_info['track_title'] + " " +track_info["artist_name"]+ " " +track_info["album_name"]).lower()).ratio()
                                # compare the artist name from the song and the artist name from the track_info
                                if (diff_ratio<0.7):
                                    try:
                                        print("songs found for the query in high quality song server. very different from the one in spotify" , search_term)
                                        print("Trying to download from youtube")
                                        video_link = find_youtube(search_term)
                                        yt = YouTube(video_link)
                                        audio = download_yt(yt,search_term)
                                    except Exception as e:
                                        print("No songs found for the query in high quality song server." , search_term)
                                        tt = track_info["track_title"]
                                        with open("failed_downloads.txt", "a", encoding="utf-8") as f:
                                            f.write(f"{tt}\n")
                                        print("Skipping... adding to failed_downloads.txt redownload with low quality in next run" )
                                        continue

                                elif (diff_ratio<0.9):
                                    print("Artist name mismatch. Skipping...")
                                    tt = track_info["track_title"]
                                    aa = track_info["artist_name"]
                                    with open("mismatched_downloads.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{tt}    ||   Orignal artist :  {aa}    ||    Downloaded artist:   {artist}\n")
                                    continue
                                audio = song["mp3"]
                                lyrics = song["lyrics"]
                        else:
                            video_link = find_youtube(search_term)
                            yt = YouTube(video_link)
                            audio = download_yt(yt,search_term)
                        if audio:
                            # track_info["track_number"] = downloaded + 1
                            set_metadata(track_info, audio,lyrics)
                            sanitized_title = sanitize_filename(track_info['track_title'])
                            destination_path = os.path.join(music_folder_path, f"{sanitized_title}.mp3")
                            os.replace(audio, destination_path)
                            downloaded += 1
                            # save the downloaded count to a file
                            with open("downloaded.txt", "w") as f:
                                f.write(str(downloaded))
                        else:
                            print("File exists. Skipping...")
                    except Exception as e:
                        tt = track_info["track_title"]
                        print(f"Failed to download {tt} due to: {e}")
                        with open("failed_downloads.txt", "a", encoding="utf-8") as f:
                            f.write(f"{tt}\n")
                        continue
                t.value = "Downloaded"
                t2.value = ""
                t.update()
                b.disabled = False
                b.update()
                print("All songs downloaded successfully!")
                print("Few more steps to go. 🚀")
                print("1. Open the downloaded folder and check if all the songs are downloaded.")
                print("2. open mismatched_downloads.txt and check if any songs are mismatched. most of them should be fine but still manually check the songs. if it is not the song you wanted, delete the song from the folder.")
                print("3. restart the app and download again but with high quality audio turned off. this will download the songs from youtube. make sure to select skip all in the song exist action dropdown.")
                print("4. open failed_downloads.txt and download the songs that are failed to download.")
                completion_popup = popup(page,"All songs downloaded successfully!\n Few more steps to go. 🚀 \n1. Open the downloaded folder and check if all the songs are downloaded. \n2. open mismatched_downloads.txt and check if any songs are mismatched. most of them should be fine but still manually check the songs. if it is not the song you wanted, delete the song from the folder.\n3. restart the app and download again but with high quality audio turned off. this will download the songs from youtube. make sure to select skip all in the song exist action dropdown.")
                page.open(completion_popup)
            except Exception as e:
                print(e)
                exception_popup = popup(page,f"⚠️ Failed to download. make sure all the options are properly selected, and the link is correct. restart and try again ({e})")
                page.open(exception_popup)
        b = ft.ElevatedButton("Download Playlist", width=200000, on_click=button_clicked)
        view = ft.Container(
            
            content = ft.Column(
                [
                    b,
                    ft.Container(
                        # image_src=img,
                        # image_opacity= 0,
                        # image_fit= ft.ImageFit.COVER,
                        padding=10,
                        content=ft.Column([
                            ft.Divider(opacity=0),
                            t, 
                            pb,
                            t2,
                            ft.Divider(opacity=0)]),
                            
                        )
                    
                ],)
        )
        return view
    
    def downloader_apple_music():
        try:
            t = ft.Text(value="")
            t2 = ft.Text(value = "0")
            pb = ft.ProgressBar(value=0)
            def button_clicked(e):
                
                link = url.value
                exists_action = dd.value
                t.value = "Fetching Playlist meta data (dont freak out if it takes a while 😅 it will take about a minute for 100 songs)"
                t.update()
                b.disabled = True
                b.update()
                custom_labels = {
                    "Replace all": "RA",
                    "Skip all": "SA",
                    "Determine while downloading from CLI": "",
                }
                global file_exists_action 
                file_exists_action = custom_labels[exists_action]
                use_spotify_for_metadata = True
                try:
                    load_dotenv()
                    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
                    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
                    client_credentials_manager = SpotifyClientCredentials(
                        client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET
                    )
                    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
                except Exception as e:
                    use_spotify_for_metadata = False
                    print(f"Failed to connect to Spotify API: {e}")
                    print("Continuing without Spotify API, some song metadata will not be added")
                    exception_popup = popup(page,f"⚠️ Failed to connect to Spotify API: {e}  .  Continuing without Spotify API, some song metadata will not be added")
                    page.open(exception_popup)
                # link = input("Enter YouTube Playlist URL: ✨")

                am_playlist = apple.get_playlist(link)



                totalVideoCount = len(am_playlist)
                print("Total songs in playlist:", totalVideoCount)

                for index, song in enumerate(am_playlist):
                    try:
                        #  check if the song is already downloaded at  f"{music_folder_path}{search_term}.mp3" 
                        if dd.value == "Skip all":
                            if os.path.exists(f"{music_folder_path}{song}.mp3"):
                                print("Skipping: "+song)
                                continue
                        if c1.value:
                            if os.path.exists("failed_downloads.txt"):
                                with open("failed_downloads.txt", "r") as f:
                                    failed_songs = f.read().splitlines()
                                if song not in failed_songs:
                                    continue
                        print("Downloading: "+song)
                        t2.value = f"{index+1}/{totalVideoCount}"
                        pb.value = ((index+1)/totalVideoCount)
                        
                        view.update()
                        t2.update()
                        pb.update()
                        lyrics = ""
                        if c2.value:
                            song_js = download_high_quality(song)
                            if song_js == "No songs found for the query.":
                                try:
                                    print("No songs found for the query in high quality song server." , song)
                                    print("Trying to download from youtube")
                                    video_link = find_youtube(song)
                                    yt = YouTube(video_link)
                                    audio = download_yt(yt,song)
                                except Exception as e:
                                    print("No songs found for the query in high quality song server." , song)
                                    with open("failed_downloads.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{song}\n")
                                    print("Skipping... adding to failed_downloads.txt redownload with low quality in next run" )
                                    continue
                            else:
                                audio = song_js["mp3"]
                                lyrics = song_js["lyrics"]
                        else:
                            video_link = find_youtube(song)
                            yt = YouTube(video_link)
                            audio = download_yt(yt,song)
                        if audio:
                            if(use_spotify_for_metadata):
                                try:
                                    spotify_search_term = song.replace(" by", "").replace(" audio", "")
                                    track_url = search_spotify(spotify_search_term,sp)
                                except Exception as e:
                                    print(e)
                                    track_url = None
                                if not track_url:
                                    track_info = get_track_info_youtube(yt)
                                else:
                                    track_info = get_track_info_spotify(track_url,sp)
                            else:
                                track_info = get_track_info_youtube(yt)

                            set_metadata(track_info, audio,lyrics)
                            os.replace(audio, f"{music_folder_path}{os.path.basename(audio)}")
                    except Exception as e:
                        print(f"Failed to download {song} due to: {e}")
                        with open("failed_downloads.txt", "a") as f:
                            f.write(f"{song}\n")
                        continue
                t.value = "Downloaded"
                t2.value = ""
                t.update()
                b.disabled = False
                b.update()
                print("All songs downloaded successfully!")
                print("Few more steps to go. 🚀")
                print("1. Open the downloaded folder and check if all the songs are downloaded.")
                print("2. some songs downloaded from the high quality audio server might not be the song you wanted. please check the songs manually and delete the songs that are not the song you wanted.")
                print("3. restart the app and download again but with high quality audio turned off. this will download the songs from youtube. make sure to select skip all in the song exist action dropdown.")
                print("4. open failed_downloads.txt and download the songs that are failed to download.")
                completion_popup = popup(page,"All songs downloaded successfully!\n Few more steps to go. 🚀 \n1. Open the downloaded folder and check if all the songs are downloaded. \n2. some songs downloaded from the high quality audio server might not be the song you wanted. please check the songs manually and delete the songs that are not the song you wanted.\n3. restart the app and download again but with high quality audio turned off. this will download the songs from youtube. make sure to select skip all in the song exist action dropdown.")
                page.open(completion_popup)
            b = ft.ElevatedButton("Download Playlist", width=200000, on_click=button_clicked)
            view = ft.Container(
                
                content = ft.Column(
                    [
                        b,
                        ft.Container(
                            # image_src=img,
                            # image_opacity= 0,
                            # image_fit= ft.ImageFit.COVER,
                            padding=10,
                            content=ft.Column([
                                ft.Divider(opacity=0),
                                t, 
                                pb,
                                t2,
                                ft.Divider(opacity=0)]),
                                
                            )
                        
                    ],)
            )
            return view
            # return "All videos downloaded successfully!"
        except Exception as e:
            print(e)
            exception_popup = popup(page,f"⚠️ Failed to download. make sure all the options are properly selected, and the link is correct. restart and try again")
            page.open(exception_popup)

    youtube_tab = ft.Container(
        ft.SafeArea(
            content=ft.Column(
                [
                    ft.Divider(opacity=0, height= 20),
                    folder_picker,
                    ft.Divider(opacity=0, height= 20),
                    ft.Text("Enter Youtube playlist url:"),
                    url,
                    ft.Divider(opacity=0),  
                    dd,
                    ft.Divider(opacity=0),
                    # ft.ElevatedButton(text="Download Playlist",width=200000),
                    c1,
                    ft.Divider(opacity=0),
                    downloader(),
                    # ft.FilledButton("sp",on_click=switch_to_sp_tab)
                    gesture_detector.detector,

                ]
            )
        ),
        visible= True
    )

    spotify_tab = ft.Container(
        ft.SafeArea(
            content=ft.Column(
                [
                    ft.Divider(opacity=0, height= 20),
                    folder_picker,
                    ft.Divider(opacity=0, height= 20),
                    ft.Text("Enter Spotify playlist or album url:"),
                    url,
                    ft.Divider(opacity=0),  
                    dd,
                    ft.Divider(opacity=0),
                    ft.Row([c1,c2]),
                    ft.Divider(opacity=0),
                    # ft.ElevatedButton(text="Download Playlist",width=200000),
                    downloader_spotify(),
                    # ft.FilledButton("yt",on_click=switch_to_yt_tab)
                    gesture_detector.detector,
                ]
            )
        ),
        visible= False
    )
    apple_music_tab = ft.Container(
        ft.SafeArea(
            content=ft.Column(
                [
                    ft.Divider(opacity=0, height= 20),
                    folder_picker,
                    ft.Divider(opacity=0, height= 20),
                    ft.Text("Enter Apple Music playlist or album url:"),
                    url,
                    ft.Divider(opacity=0),  
                    dd,
                    ft.Divider(opacity=0),
                    ft.Row([c1,c2]),
                    ft.Divider(opacity=0),
                    # ft.ElevatedButton(text="Download Playlist",width=200000),
                    downloader_apple_music(),
                    # ft.FilledButton("yt",on_click=switch_to_yt_tab)
                    gesture_detector.detector,
                ]
            )
        ),
        visible= False
    )

    # --- Search tab: allows searching artist/album and batch downloading ---
    search_query = ft.TextField(keyboard_type=ft.KeyboardType.TEXT, width=800, hint_text="Type artist or album and press Search")
    # Dropdown to select one candidate from topresult, artists and albums
    search_candidates_dropdown = ft.Dropdown(label="Select result", width=800, options=[], on_change=lambda e: None)
    # Show a preview (image + title) for the selected candidate
    search_result_title = ft.Text("", size=16)
    search_result_image = ft.Image(src="", width=100, height=100)
    search_result_box = ft.Row([search_result_image, ft.Column([search_result_title])])
    search_progress = ft.ProgressBar(value=0)

    def perform_search(e):
        q = search_query.value.strip()
        if not q:
            return
        s = Search()
        try:
            res = s.search(q)
        except Exception as err:
            print(f"Search failed: {err}")
            res = None
        # clear previous
        search_result_title.value = ""
        search_result_image.src = ""
        search_result_title.update()
        search_result_image.update()
        if not res or res == "not found":
            search_result_title.value = "No result"
            search_result_title.update()
            search_result_image.update()
            # clear dropdown
            search_candidates_dropdown.options = []
            search_candidates_dropdown.update()
            e.control.page.update()
            return

        # Build a flat list of candidates with labels and keep full items in a map
        candidates = []
        candidates_map = {}
        idx = 0
        if res.get('topresult'):
            item = res['topresult']
            label = f"Top: {item.get('title') or item.get('name') or item.get('perma_url','')[:40]}"
            key = f"c_{idx}"
            candidates.append(ft.dropdown.Option(key=key, text=label))
            candidates_map[key] = item
            idx += 1

        for a in res.get('artists', []):
            label = f"Artist: {a.get('title') or a.get('name') or a.get('perma_url','')[:40]}"
            key = f"c_{idx}"
            candidates.append(ft.dropdown.Option(key=key, text=label))
            candidates_map[key] = a
            idx += 1

        for al in res.get('albums', []):
            label = f"Album: {al.get('title') or al.get('name') or al.get('perma_url','')[:40]}"
            key = f"c_{idx}"
            candidates.append(ft.dropdown.Option(key=key, text=label))
            candidates_map[key] = al
            idx += 1

        # populate dropdown
        search_candidates_dropdown.options = candidates
        search_candidates_dropdown.value = candidates[0].key if candidates else None
        # save map on page for download
        e.control.page._search_candidates_map = candidates_map

        # update preview to first candidate
        if candidates:
            sel_key = search_candidates_dropdown.value
            sel_item = candidates_map.get(sel_key)
            title = sel_item.get('title') or sel_item.get('name') or ''
            img = sel_item.get('image') or sel_item.get('album_art') or ''
            search_result_title.value = title + f"  ({sel_item.get('type','')})"
            search_result_image.src = img
        else:
            search_result_title.value = "No result"
            search_result_image.src = ''

        search_candidates_dropdown.update()
        search_result_title.update()
        search_result_image.update()
        e.control.page.update()

    # update preview when user selects different candidate
    def candidate_changed(e):
        sel_key = e.control.value
        candidates_map = getattr(e.control.page, '_search_candidates_map', {})
        sel_item = candidates_map.get(sel_key)
        if not sel_item:
            search_result_title.value = "No result"
            search_result_image.src = ""
        else:
            title = sel_item.get('title') or sel_item.get('name') or ''
            img = sel_item.get('image') or sel_item.get('album_art') or ''
            search_result_title.value = title + f"  ({sel_item.get('type','')})"
            search_result_image.src = img
        search_result_title.update()
        search_result_image.update()
        e.control.page.update()

    # wire dropdown change to handler
    search_candidates_dropdown.on_change = candidate_changed

    def start_download(e):
        # read selected candidate
        sel_key = search_candidates_dropdown.value
        candidates_map = getattr(e.control.page, '_search_candidates_map', {})
        sel = candidates_map.get(sel_key)
        if not sel:
            print("Nothing selected to download")
            return

        async def run_download():
            s = Search()
            # decide artist or album or single song
            typ = sel.get('type')
            if typ == 'artist':
                songs = s.get_songs_from_artist(sel)
            elif typ == 'album':
                songs = s.get_songs_from_album(sel)
            elif typ == 'song':
                # single song -> wrap in list
                songs = [Song(sel)] if 'Song' in globals() else [sel]
            else:
                print("Unsupported type for download")
                return

            total = len(songs)
            if total == 0:
                print("No songs found to download")
                return
            print(f"Starting download of {total} songs...")
            song_count.value = f"Songs to download: {total}"
            song_count.update()
            e.control.page.update()
            sem = asyncio.Semaphore(10)
            timeout = aiohttp.ClientTimeout(total=120)
            completed = 0
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # create tasks in batches of 10
                tasks = [DownloadSong(song, output_folder=music_folder_path, skip=True).download_song_async(session, sem) for song in songs]
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

        # run async download without blocking UI thread
        try:
            asyncio.run(run_download())
            print("Download runner completed")
        
        except Exception as err:
            print(f"Download runner failed: {err}")

    search_btn = ft.ElevatedButton("Search", on_click=perform_search)
    download_btn = ft.ElevatedButton("Download", on_click=start_download)
    song_count = ft.Text("")
    downloaded_count = ft.Text("")

    search_tab = ft.Container(
        ft.SafeArea(
            content=ft.Column([
                ft.Divider(opacity=0, height=20),
                folder_picker,
                ft.Divider(opacity=0, height=20),
                ft.Text("Search Artist or Album:"),
                ft.Row([search_query, search_btn]),
                ft.Divider(opacity=0),
                search_candidates_dropdown,
                search_result_box,                
                ft.Divider(opacity=0),
                download_btn,
                song_count,
                search_progress,
                downloaded_count,
                gesture_detector.detector,

            ])
        ),
        visible=False
    )

    page.spotify_tab=spotify_tab
    page.youtube_tab = youtube_tab
    page.apple_music_tab = apple_music_tab
    page.search_tab = search_tab
    page.overlay.extend([ get_directory_dialog])
    
    page.add(
        youtube_tab,spotify_tab,apple_music_tab, search_tab
    )
    for i in range(0, 101):
            pb.value = i * 0.01
            time.sleep(0.1)
            page.update()


ft.app(target=main)