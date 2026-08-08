import base64
import os

import main
from pyDes import ECB, PAD_PKCS5, des


def test_sanitize_filename():
    assert main.sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"
    assert main.sanitize_filename("plain name.mp3") == "plain name.mp3"
    assert main.sanitize_filename("") == ""


def test_ensure_folder_path_ends_with_slash():
    # both separator styles normalize to a single trailing os.sep
    assert main.ensure_folder_path_ends_with_slash("C:/music") == "C:/music" + os.sep
    assert main.ensure_folder_path_ends_with_slash("C:/music/") == "C:/music" + os.sep
    assert main.ensure_folder_path_ends_with_slash("C:\\music\\") == "C:\\music" + os.sep


def test_make_alpha_numeric():
    assert main.make_alpha_numeric("a b-c_123") == "abc123"
    assert main.make_alpha_numeric("") == ""


def test_decrypt_url_roundtrip():
    url = "https://example.com/media/song_96.mp4"
    cipher = des(b"38346591", ECB, b"\0\0\0\0\0\0\0\0", pad=None, padmode=PAD_PKCS5)
    enc = base64.b64encode(cipher.encrypt(url.encode("utf-8"), padmode=PAD_PKCS5)).decode()
    dec = main.decrypt_url(enc)
    assert dec == "https://example.com/media/song_320.mp4"


def test_prompt_exists_action_skip_all(music_dir, monkeypatch):
    monkeypatch.setattr(main.state, "file_exists_action", "SA")
    assert main.prompt_exists_action() is False
    assert main.prompt_exists_action() is False


def test_prompt_exists_action_replace_all(monkeypatch):
    monkeypatch.setattr(main.state, "file_exists_action", "RA")
    assert main.prompt_exists_action() is True


def test_download_yt_skips_when_file_exists(music_dir, monkeypatch):
    """When the file already exists and action is 'skip all', no download happens."""
    monkeypatch.setattr(main.state, "music_folder_path", music_dir)
    monkeypatch.setattr(main.state, "file_exists_action", "SA")
    existing = os.path.join(music_dir, "Existing Song.mp3")
    open(existing, "wb").close()

    class FakeYT:
        title = "Existing Song"
        watch_url = "https://www.youtube.com/watch?v=abc"

    called = []

    def fake_download(*args, **kwargs):
        called.append("downloaded")

    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", fake_download)
    assert main.download_yt(FakeYT(), "Existing Song") is False
    assert called == []


def test_download_yt_replaces_when_action_ra(music_dir, monkeypatch, tmp_path):
    """'replace all' downloads even if the final file exists."""
    monkeypatch.setattr(main.state, "music_folder_path", music_dir)
    monkeypatch.setattr(main.state, "file_exists_action", "RA")
    existing = os.path.join(music_dir, "Existing Song.mp3")
    open(existing, "wb").close()

    class FakeYT:
        title = "Existing Song"
        watch_url = "https://www.youtube.com/watch?v=abc"

    # fake the yt-dlp download + moviepy conversion
    class FakeYDLError(Exception):
        pass

    downloaded = {}

    def fake_ydl_download(*args, **kwargs):
        # simulate yt-dlp writing the extracted mp3
        out = os.path.join(music_dir, "tmp", "Existing Song.mp3")
        with open(out, "wb") as f:
            f.write(b"audio")
        downloaded["path"] = out

    class FakeYDL:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            fake_ydl_download(urls)

    monkeypatch.setattr(main.yt_dlp, "YoutubeDL", FakeYDL)
    result = main.download_yt(FakeYT(), "Existing Song")
    assert result == os.path.join(music_dir, "tmp", "Existing Song.mp3")
    assert os.path.exists(result)