import requests
import base64
from pyDes import *
import os
import urllib.request
from moviepy.editor import AudioFileClip
from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TDRC, TRCK, TSRC, USLT, APIC

class Song:
    """Represents a single song and its metadata extracted from the API JSON.

    Initialize with the raw song JSON (dictionary) and access common fields as
    attributes. Use to_dict() to get a serializable representation.
    """
    def __init__(self, song_json: dict):
        self.raw = song_json or {}
        # common top-level fields
        self.id = self.raw.get('id')
        self.title = self.raw.get('title')
        self.subtitle = self.raw.get('subtitle')
        self.type = self.raw.get('type')
        self.perma_url = self.raw.get('perma_url')
        self.image = self.raw.get('image')
        self.language = self.raw.get('language')
        self.year = self.raw.get('year')
        self.play_count = self.raw.get('play_count')
        self.explicit_content = self.raw.get('explicit_content')
        self.list_count = self.raw.get('list_count')
        self.more_info = self.raw.get('more_info', {})

        # more_info nested fields (safely extracted)
        self.album_id = self.more_info.get('album_id')
        self.album = self.more_info.get('album')
        self.duration = self.more_info.get('duration')
        self.encrypted_media_url = self.more_info.get('encrypted_media_url')
        self.decrypted_media_url = self.decrypt_url(self.encrypted_media_url) if self.encrypted_media_url else None
        self.vlink = self.more_info.get('vlink')
        self.artistMap = self.more_info.get('artistMap', {})

    
    def decrypt_url(self,url):
        des_cipher = des(b"38346591", ECB, b"\0\0\0\0\0\0\0\0",
                        pad=None, padmode=PAD_PKCS5)
        enc_url = base64.b64decode(url.strip())
        dec_url = des_cipher.decrypt(enc_url, padmode=PAD_PKCS5).decode('utf-8')
        dec_url = dec_url.replace("_96.mp4", "_320.mp4")
        return dec_url
    
    def to_dict(self):
        """Return a JSON-serializable dict of song metadata."""
        return {
            'id': self.id,
            'title': self.title,
            'subtitle': self.subtitle,
            'type': self.type,
            'perma_url': self.perma_url,
            'image': self.image,
            'language': self.language,
            'year': self.year,
            'play_count': self.play_count,
            'explicit_content': self.explicit_content,
            'list_count': self.list_count,
            'more_info': self.more_info,
        }

    def __repr__(self):
        return f"<Song id={self.id!r} title={self.title!r}>"

class Search:
    def __init__(self):
        self.search_url ="https://www.jiosaavn.com/api.php?__call=autocomplete.get&_format=json&_marker=0&cc=in&includeMetaTags=1&query="

        pass

    def search(self, query):
        # Placeholder for search logic
        print(f"Searching for: {query}")
        search_url = self.search_url + query
        response = requests.get(search_url)
        if response.status_code == 200:
            # First, try to find a song in the topquery data if available
            try:
                top_query_data = response.json().get('topquery', {}).get('data', [])
                # Look for artist or album items and return the first matching item as JSON
                for item in top_query_data:
                    item_type = item.get('type')
                    if item_type in ('artist', 'album'):
                        return item  # return the JSON object for artist or album
                # If not found in topquery, try other fields in the response that may contain results
                data = response.json()
                # Search through all values in the JSON for lists of items
                def find_in_obj(obj):
                    if isinstance(obj, dict):
                        for v in obj.values():
                            res = find_in_obj(v)
                            if res is not None:
                                return res
                    elif isinstance(obj, list):
                        for elem in obj:
                            if isinstance(elem, dict) and elem.get('type') in ('artist', 'album'):
                                return elem
                            res = find_in_obj(elem)
                            if res is not None:
                                return res
                    return None

                found = find_in_obj(data)
                if found:
                    return found
                # nothing found
                return "not found"
            except Exception:
                return "not found"
        else:
            print("Error fetching search results")
            return None
    
    def get_songs_from_artist(self, artist_json):
        artist_id = artist_json.get('id')
        if not artist_id:
            return "Artist ID not found"
        perma = artist_json.get('url')
        if not perma:
            return []
        token = perma.rstrip('/').split('/')[-1]
        if not token:
            return []
        songs_list = []
        page = 0
        base = ('https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}'
                '&type=artist&n_song=50&n_album=50&sub_type=&category=latest'
                '&sort_order=desc&includeMetaTags=0&ctx=web6dot0&api_version=4'
                '&_format=json&_marker=0')
        while True:
            url = base.format(token=token) + f'&p={page}'
            print(f"Fetching songs from URL: {url}")
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

            candidates = []
            for key in ('topSongs', 'songs', 'data', 'songs_list'):
                v = data.get(key)
                if isinstance(v, list) and v:
                    candidates = v
                    break

            if not candidates:
                for v in data.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict) and v[0].get('type') == 'song':
                        candidates = v
                        break

            if not candidates:
                break

            for s in candidates:
                try:
                    songs_list.append(Song(s))
                except Exception as e:
                    print(f"Error parsing song data, skipping... {e}")
                    continue

            page += 1

        return songs_list
    
    def get_songs_from_album(self, album_json):
        """Fetch songs for an album JSON (same shape as the example).

        Extracts token from album 'url' (perma), calls the album API and returns
        a list of Song instances for each track in the album's 'list'.
        """
        perma = album_json.get('url') or album_json.get('perma_url')
        if not perma:
            return []
        token = perma.rstrip('/').split('/')[-1]
        if not token:
            return []

        url = (f'https://www.jiosaavn.com/api.php?__call=webapi.get&token={token}'
               '&type=album&includeMetaTags=0&ctx=web6dot0&api_version=4'
               '&_format=json&_marker=0')
        print(f"Fetching album data from URL: {url}")
        try:
            resp = requests.get(url, timeout=15)
        except Exception:
            return []
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except Exception:
            return []

        # album songs are usually under 'list'
        candidates = data.get('list') or data.get('songs') or data.get('data') or []
        songs_list = []
        if isinstance(candidates, list):
            for s in candidates:
                try:
                    songs_list.append(Song(s))
                except Exception as e:
                    print(f"Error parsing album song, skipping... {e}")
                    continue
        else:
            # if 'list' is a dict containing 'list' key etc.
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict) and v[0].get('type') == 'song':
                    for s in v:
                        try:
                            songs_list.append(Song(s))
                        except Exception as e:
                            print(f"Error parsing album song, skipping... {e}")
                            continue
                    break

        return songs_list

class DownloadSong:
    def __init__(self, song, output_folder="music-yt"):
        self.song = song
        self.output_folder = output_folder if output_folder.endswith(os.sep) else output_folder + os.sep

    def download_song(self) -> str:
        """Download the song using decrypted_media_url, convert to mp3, and add metadata and album art.

        Returns the path to the final mp3 file on success, or raises an exception on failure.
        """
        if not self.song or not getattr(self.song, 'decrypted_media_url', None):
            raise ValueError("Song has no decrypted URL")

        # prepare folders
        tmp_dir = os.path.join(self.output_folder, 'tmp')
        os.makedirs(tmp_dir, exist_ok=True)
        os.makedirs(self.output_folder, exist_ok=True)

        # sanitize filename
        title = self.song.title or "unknown"
        safe_title = "".join(c for c in title if c not in ['/', '\\', '|', '?', '*', ':', '>', '<', '"'])

        video_file = os.path.join(tmp_dir, f"{safe_title}.mp4")
        audio_file = os.path.join(tmp_dir, f"{safe_title}.mp3")
        final_file = os.path.join(self.output_folder, f"{safe_title}.mp3")

        # download the media
        url = self.song.decrypted_media_url
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(video_file, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # convert to mp3 (high quality similar to main.py)
        clip = AudioFileClip(video_file)
        try:
            clip.write_audiofile(audio_file, bitrate="3000k")
        finally:
            clip.close()

        # remove downloaded mp4
        try:
            os.remove(video_file)
        except Exception:
            pass

        # add metadata using mutagen
        try:
            tags = ID3()
            # artist
            artist_name = getattr(self.song, 'subtitle', None) or getattr(self.song, 'artistMap', None) or ''
            if isinstance(artist_name, dict):
                # if artistMap present, join names
                artist_name = ', '.join(v.get('name', '') for v in artist_name.values())
            tags['TPE1'] = TPE1(encoding=3, text=artist_name or '')
            # album (use album or album_id)
            tags['TALB'] = TALB(encoding=3, text=getattr(self.song, 'album', '') or '')
            tags['TIT2'] = TIT2(encoding=3, text=title)
            # release year if available
            if getattr(self.song, 'year', None):
                tags['TDRC'] = TDRC(encoding=3, text=str(self.song.year))
            # track number not available here; leave blank
            tags.save(audio_file)

            # add album art if image available
            if getattr(self.song, 'image', None):
                with urllib.request.urlopen(self.song.image) as img:
                    img_data = img.read()
                audio = ID3(audio_file)
                audio['APIC'] = APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img_data)
                audio.save(v2_version=3)
        except Exception as e:
            # continue even if tagging fails
            print(f"Warning: failed to set metadata for {title}: {e}")

        # move final file to output folder
        try:
            if os.path.exists(final_file):
                os.remove(final_file)
            os.replace(audio_file, final_file)
        except Exception:
            # fallback to copy
            import shutil
            shutil.copy2(audio_file, final_file)
            os.remove(audio_file)

        return final_file

def main():
    search_instance = Search()
    query = "From zero"
    result = search_instance.search(query)
    print(result)
    if result:
        if result.get('type') == 'artist':
            print("Fetching songs for artist...")
            songs = search_instance.get_songs_from_artist(result)
            for song in songs:
                print(song.to_dict())
        elif result.get('type') == 'album':
            print("Fetching songs for album...")
            songs = search_instance.get_songs_from_album(result)
            for song in songs:
                print(song.to_dict())
                DownloadSong(song).download_song()

if __name__ == "__main__":
    main()