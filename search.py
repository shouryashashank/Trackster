import requests
import base64
from pyDes import *

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

class DownloadSongs:
    def __init__(self, songList):
        self.songList = songList
    
    def download_songs(self):
        

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

if __name__ == "__main__":
    main()