import apple


def test_get_playlist_parses_songs(monkeypatch):
    html = """<html><head>
      <meta property="music:song" content="https://music.apple.com/us/song/111">
      <meta property="music:song" content="https://music.apple.com/us/song/222">
    </head></html>"""

    class R:
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr(apple.requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(
        apple, "get_song_details", lambda url: f"Song {url[-3:]}"
    )
    result = apple.get_playlist("https://music.apple.com/playlist")
    assert result == ["Song 111", "Song 222"]


def test_get_playlist_filters_none(monkeypatch):
    html = """<html><head>
      <meta property="music:song" content="https://music.apple.com/us/song/1">
      <meta property="music:song" content="https://music.apple.com/us/song/2">
    </head></html>"""

    class R:
        text = html

        def raise_for_status(self):
            pass

    monkeypatch.setattr(apple.requests, "get", lambda *a, **k: R())

    def details(url):
        return "Song One" if url.endswith("/1") else None

    monkeypatch.setattr(apple, "get_song_details", details)
    result = apple.get_playlist("https://music.apple.com/playlist")
    assert result == ["Song One"]


def test_get_song_details_strips_suffix():
    from bs4 import BeautifulSoup

    html = '<meta property="og:title" content="My Song on Apple Music">'
    soup = BeautifulSoup(html, "html.parser")

    class R:
        text = str(soup)

        def raise_for_status(self):
            pass

    from unittest import mock

    with mock.patch.object(apple.requests, "get", return_value=R()):
        result = apple.get_song_details("https://music.apple.com/song/1")
    assert result == "My Song audio"