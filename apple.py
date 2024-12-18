import requests
from bs4 import BeautifulSoup
import re
import tqdm

def get_song_details(link):
    try:
        response = requests.get(link)
        response.raise_for_status()  
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        title = soup.find('meta', attrs = {"property":"og:title"})
        if title:
            content = title.get('content')
            content = content.replace("on AppleÂ\xa0Music", "audio")
            return content
        else:
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
        response = requests.get(url)
        response.raise_for_status()  
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        applelinks = soup.find_all('meta', attrs={"property": "music:song"})
        song_list = []
        for link in tqdm.tqdm(enumerate(applelinks), total=len(applelinks), desc="Processing songs"):
            link_str = str(link[1])
            match = re.search(r'content="(https?://[^"]+)"', link_str)
            if match:
                url = match.group(1)
                song_search_term = get_song_details(url)
                song_list.append(song_search_term)
        return song_list
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return []
