import re

import requests
import tqdm
from bs4 import BeautifulSoup


def get_song_details(link):
    try:
        response = requests.get(link, timeout=15)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        title = soup.find('meta', attrs={"property": "og:title"})
        if title:
            content = title.get('content')
            content = content.replace("on Apple Music", "audio")
            return content.strip()
        print("No meta tag found")
        return None
    except requests.RequestException as e:
        print(f"Request error: {e}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_playlist(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        applelinks = soup.find_all('meta', attrs={"property": "music:song"})
        song_list = []
        for item in tqdm.tqdm(applelinks, desc="Processing songs"):
            link_str = str(item)
            match = re.search(r'content="(https?://[^"]+)"', link_str)
            if match:
                song_search_term = get_song_details(match.group(1))
                if song_search_term:
                    song_list.append(song_search_term)
        return song_list
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return []
