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
import requests
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
# import sys, io

# buffer = io.StringIO()
# sys.stdout = sys.stderr = buffer
ssl._create_default_https_context = ssl._create_unverified_context

file_exists_action=""
failed_download = False
music_folder_path = "music-yt/"   # path to save the downloaded music
# SPOTIPY_CLIENT_ID = "" # Spotify API client ID  # keep blank if you dont need spotify metadata
# SPOTIPY_CLIENT_SECRET = ""  # Spotify API client secret

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
    max_retries = 3
    attempt = 0
    video = None

    while attempt < max_retries:
        try:
            video = yt.streams.filter(only_audio=True).first()
            if video:
                break
        except Exception as e:
            print(f"Attempt {attempt + 1}  {search_term} failed due to: {e}")
            attempt += 1
    if not video:
        print(f"Failed to download {search_term}")
        # check if a file named failed_downloads.txt exists if not create one and append the failed download
        if not os.path.exists("failed_downloads.txt"):
            with open("failed_downloads.txt", "w") as f:
                f.write(f"{search_term}\n")
        else:
            with open("failed_downloads.txt", "a") as f:
                f.write(f"{search_term}\n")
        return False
    vid_file = video.download(output_path=f"{music_folder_path}tmp")
    # convert the downloaded video to mp3
    base = os.path.splitext(vid_file)[0]
    audio_file = base + ".mp3"
    mp4_no_frame = AudioFileClip(vid_file)
    mp4_no_frame.write_audiofile(audio_file, logger=None)
    mp4_no_frame.close()
    os.remove(vid_file)
    os.replace(audio_file, f"{music_folder_path}tmp/{yt.title}.mp3")
    audio_file = f"{music_folder_path}tmp/{yt.title}.mp3"

    return audio_file

def set_metadata(metadata, file_path):
    """adds metadata to the downloaded mp3 file"""

    mp3file = EasyID3(file_path)

    # add metadata
    mp3file["albumartist"] = metadata["artist_name"]
    mp3file["artist"] = metadata["artists"]
    mp3file["album"] = metadata["album_name"]
    mp3file["title"] = metadata["track_title"]
    mp3file["date"] = metadata["release_date"]
    mp3file["tracknumber"] = str(metadata["track_number"])
    mp3file["isrc"] = metadata["isrc"]
    mp3file.save()

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
def nav_bar():
    view = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.ONDEMAND_VIDEO_ROUNDED, label="Youtube"),
            ft.NavigationBarDestination(icon=ft.icons.MUSIC_NOTE, label="Spotify")
            
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
    e.control.page.navigation_bar.selected_index = 0
    e.control.page.update()

def switch_to_sp_tab(e):
    e.control.page.title= "Spotify"
    set_theme(e,"Green")
    e.control.page.youtube_tab.visible = False
    e.control.page.spotify_tab.visible = True
    e.control.page.navigation_bar.selected_index = 1
    e.control.page.update()

def get_track_info(track_url,sp):
    
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
    for track in tqdm(tracks):
        updated_tracks.append(track["id"])
        if track["id"] in track_id:
            continue
        track_url = f"https://open.spotify.com/track/{track['id']}"
        track_info = get_track_info(track_url,sp)
        # make a progress bar
        
        tracks_info.append(track_info)
    # save the updated tracks_id to synced_updated.txt
    with open("synced_updated.txt", "w") as f:
        f.write("\n".join(updated_tracks))
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
    for track in tqdm(tracks_item):
        updated_tracks.append(track["id"])
        if track["id"] in track_id:
            continue
        track_url = f"https://open.spotify.com/track/{track['id']}"
        track_info = get_track_info(track_url,sp)
        # make a progress bar
        
        tracks_info.append(track_info)
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

                            set_metadata(track_info, audio)
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
            link = url.value
            exists_action = dd.value
            t.value = "Fetching Playlist meta data (dont freak out if it takes a while 😅 it will take about a minute for 100 songs)"
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
                        if c1.value:
                            if os.path.exists("failed_downloads.txt"):
                                with open("failed_downloads.txt", "r") as f:
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
                        video_link = find_youtube(search_term)
                        yt = YouTube(video_link)
                        audio = download_yt(yt,search_term)
                        if audio:
                            # track_info["track_number"] = downloaded + 1
                            set_metadata(track_info, audio)
                            os.replace(audio, f"{music_folder_path}{os.path.basename(audio)}")
                            downloaded += 1
                            # save the downloaded count to a file
                            with open("downloaded.txt", "w") as f:
                                f.write(str(downloaded))
                        else:
                            print("File exists. Skipping...")
                    except Exception as e:
                        tt = track_info["track_title"]
                        print(f"Failed to download {tt} due to: {e}")
                        with open("failed_downloads.txt", "a") as f:
                            f.write(f"{tt}\n")
                        continue
                t.value = "Downloaded"
                t2.value = ""
                t.update()
                b.disabled = False
                b.update()
                print("All videos downloaded successfully!")
            except Exception as e:
                print(e)
                exception_popup = popup(page,f"⚠️ Failed to download. make sure all the options are properly selected, and the link is correct. restart and try again")
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
                    c1,
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
    page.spotify_tab=spotify_tab
    page.youtube_tab = youtube_tab
    page.overlay.extend([ get_directory_dialog])
    
    page.add(
        youtube_tab,spotify_tab
    )
    for i in range(0, 101):
            pb.value = i * 0.01
            time.sleep(0.1)
            page.update()


ft.app(target=main)