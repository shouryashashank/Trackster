"""Construct every UI control the app builds, without launching the server.

Catches flet API drift (constructor signatures, control names) that would only
fail at import/startup time.
"""

import urllib.request

import flet as ft

import main


def _controls():
    url = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    dd = ft.Dropdown(
        label="Song Exist Action",
        options=[ft.dropdown.Option("Replace all"), ft.dropdown.Option("Skip all")],
    )
    c1 = ft.Checkbox(label="Download only failed songs")
    c2 = ft.Checkbox(label="Download high quality audio")
    return url, dd, c1, c2


def test_downloader_views_construct():
    url, dd, c1, c2 = _controls()
    assert main.youtube_downloader(url, dd, c1) is not None
    assert main.spotify_downloader(url, dd, c1, c2) is not None
    assert main.apple_music_downloader(url, dd, c1, c2) is not None


def test_app_bar_and_nav_bar_construct():
    assert main.app_bar() is not None
    assert main.nav_bar() is not None


def test_navigation_drawer_constructs():
    open_drawer = main.navigation_drawer()
    assert callable(open_drawer)


def test_folder_picker_builds():
    fp = main.FolderPicker()
    assert fp.build() is not None


def test_popup_builds():
    dlg = main.popup(None, "hello")
    assert isinstance(dlg, ft.AlertDialog)


def test_gesture_detector_constructs():
    gd = main.GestureDetector()
    assert gd.detector is not None


class FakePage:
    """Minimal page stand-in so main(page) can be exercised without a server."""

    def __init__(self):
        self.overlay = []
        self.added = []

    def add(self, *controls):
        self.added.extend(controls)


def test_main_builds_full_ui():
    """Running main() must build every tab without any flet API errors."""
    page = FakePage()
    main.main(page)
    # reveal_tabs: page stores references to each tab; all should be present
    assert page.youtube_tab is not None
    assert page.spotify_tab is not None
    assert page.apple_music_tab is not None
    assert page.search_tab is not None
    assert len(page.added) == 4


def test_find_youtube_returns_url(monkeypatch):
    """find_youtube should parse a watch?v= link from the results page."""
    html = b'<a href="/watch?v=abcdefghijk">x</a>'

    class FakeResp:
        def read(self):
            return html

    monkeypatch.setattr(urllib.request, "urlopen", lambda u: FakeResp())
    result = main.find_youtube("hello world")
    assert result == "https://www.youtube.com/watch?v=abcdefghijk"