import base64
import os
from unittest import mock

import main
import search
from pyDes import ECB, PAD_PKCS5, des


def _song_header_response():
    class R:
        def json(self):
            return {
                "topquery": {"data": [{"type": "song", "id": "999", "title": "Find Me"}]},
                "songs": {"data": [{"id": "999", "title": "Find Me",
                                    "more_info": {"primary_artists": "Artist"},
                                    "album": "Album"}]},
            }
    return R()


def _song_detail_response():
    class R:
        def json(self):
            return {
                "999": {
                    "encrypted_media_url": "ignore",
                    "primary_artists": "Artist",
                    "album": "Album",
                    "song": "Find Me",
                    "release_date": "2020-01-01",
                    "has_lyrics": "false",
                }
            }
    return R()


def test_search_song_topquery(monkeypatch):
    monkeypatch.setattr(main, "decrypt_url", lambda u: "https://cdn/song_320.mp4")
    responses = [_song_header_response(), _song_detail_response()]
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: responses.pop(0))
    result = main.search_song("Find Me")
    assert result["song"] == "Find Me"
    assert result["primary_artists"] == "Artist"
    assert result["album"] == "Album"
    assert result["url"] == "https://cdn/song_320.mp4"
    assert result["release_date"] == "2020-01-01"


def test_search_song_no_songs(monkeypatch):
    class R:
        def json(self):
            return {"topquery": {"data": []}, "songs": {"data": []}}
    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())
    assert main.search_song("nothing here") is None


def test_download_high_quality_not_found(monkeypatch):
    monkeypatch.setattr(main, "search_song", lambda q: None)
    assert main.download_high_quality("missing song") is None


def test_download_high_quality_success(monkeypatch, music_dir):
    monkeypatch.setattr(main.state, "music_folder_path", music_dir)
    monkeypatch.setattr(
        main,
        "search_song",
        lambda q: {
            "url": "https://cdn/song_320.mp4",
            "primary_artists": "Artist",
            "album": "Album",
            "song": "Cool Song: Part II",
            "release_date": "2021-05-05",
            "lyrics": "la la",
        },
    )

    class R:
        content = b"media-bytes"

    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())

    def fake_convert(video_file):
        audio_file = video_file.rsplit(".", 1)[0] + ".mp3"
        with open(audio_file, "wb") as f:
            f.write(b"converted")
        return audio_file

    # Fake AudioFileClip to convert the video file into the mp3
    class FakeClip:
        def __init__(self, path):
            self.out = fake_convert(path)

        def write_audiofile(self, path, **kwargs):
            with open(path, "wb") as f:
                f.write(b"converted")

        def close(self):
            pass

    monkeypatch.setattr(main, "AudioFileClip", FakeClip)
    result = main.download_high_quality("cool song")
    assert result["mp3"].endswith("Cool Song Part II.mp3")
    assert os.path.exists(result["mp3"])
    # the intermediate mp4 must be cleaned up
    assert not os.path.exists(result["mp3"].rsplit(".", 1)[0] + ".mp4")


def _encrypted_url():
    cipher = des(b"38346591", ECB, b"\0\0\0\0\0\0\0\0", pad=None, padmode=PAD_PKCS5)
    enc = base64.b64encode(
        cipher.encrypt(b"https://example.com/media/audio_96.mp4", padmode=PAD_PKCS5)
    ).decode()
    return enc


class _StreamingResp:
    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        return [b"x" * 1000 for _ in range(5)]


def test_download_song_end_to_end(monkeypatch, tmp_path):
    """Search-tab DownloadSong: decrypt -> download -> convert -> tag -> move."""
    output = str(tmp_path / "out")
    song = search.Song(
        {"id": "1", "title": "Song X", "image": None,
         "more_info": {"encrypted_media_url": _encrypted_url()}}
    )
    assert song.decrypted_media_url == "https://example.com/media/audio_320.mp4"

    monkeypatch.setattr(search.requests, "get", lambda *a, **k: _StreamingResp())

    class FakeClip:
        def __init__(self, path):
            pass

        def write_audiofile(self, path, **kwargs):
            with open(path, "wb") as f:
                f.write(b"audio")

        def close(self):
            pass

    monkeypatch.setattr(search, "AudioFileClip", FakeClip)
    final = search.DownloadSong(song, output_folder=output).download_song()
    assert final == os.path.join(output, "Song X.mp3")
    assert os.path.exists(final)
    # temp mp4 removed, no leftover
    tmp = os.path.join(output, "tmp")
    assert not [f for f in os.listdir(tmp)] or all(not f.endswith(".mp4") for f in os.listdir(tmp))


def test_download_song_skips_existing(monkeypatch, tmp_path):
    output = str(tmp_path / "out")
    os.makedirs(output, exist_ok=True)
    with open(os.path.join(output, "Song X.mp3"), "wb") as f:
        f.write(b"existing")
    song = search.Song({"id": "1", "title": "Song X", "image": None,
                        "more_info": {"encrypted_media_url": _encrypted_url()}})
    monkeypatch.setattr(search.requests, "get", lambda *a, **k: _StreamingResp())
    final = search.DownloadSong(song, output_folder=output, skip=True).download_song()
    assert final == os.path.join(output, "Song X.mp3")


def test_song_title_falls_back_to_song_key():
    song = search.Song({"id": "1", "song": "From The Details API", "type": "song"})
    assert song.title == "From The Details API"


def test_song_subtitle_falls_back_to_primary_artists():
    song = search.Song({"id": "1", "title": "T", "primary_artists": "Arjit"})
    assert song.subtitle == "Arjit"


def test_song_encrypted_url_from_top_level():
    enc = _encrypted_url()
    song = search.Song({"id": "1", "title": "T", "encrypted_media_url": enc})
    assert song.decrypted_media_url == "https://example.com/media/audio_320.mp4"


def test_search_results_include_songs_topquery_artist_album(monkeypatch):
    def _get(*a, **k):
        class R:
            status_code = 200

            def json(self):
                return {
                    "topquery": {"data": [{"type": "song", "id": "s1", "title": "Top Song"}]},
                    "songs": {"data": [
                        {"type": "song", "id": "s1", "title": "Top Song"},
                        {"type": "song", "id": "s2", "title": "Song Two"},
                    ]},
                    "artists": {"data": [{"type": "artist", "id": "a1", "title": "Arti St"}]},
                    "albums": {"data": [{"type": "album", "id": "al1", "title": "Alb Um"}]},
                }
        return R()

    monkeypatch.setattr(search.requests, "get", _get)
    res = search.Search().search("query")
    assert {s["id"] for s in res["songs"]} == {"s1", "s2"}
    assert [a["id"] for a in res["artists"]] == ["a1"]
    assert [al["id"] for al in res["albums"]] == ["al1"]
    assert res["topresult"]["id"] == "s1"


def test_search_returns_songs_bucket_only_with_stub(monkeypatch):
    def _get(*a, **k):
        class R:
            status_code = 200

            def json(self):
                return {"songs": {"data": [{"type": "song", "id": "s1", "title": "S"}]}}
        return R()

    monkeypatch.setattr(search.requests, "get", _get)
    res = search.Search().search("q")
    assert [s["id"] for s in res["songs"]] == ["s1"]


def test_enrich_song_returns_full_song(monkeypatch):
    enc = _encrypted_url()

    def _get(*a, **k):
        class R:
            status_code = 200

            def json(self):
                return {"123": {
                    "id": "123", "song": "Full Track", "type": "song",
                    "primary_artists": "Karta",
                    "encrypted_media_url": enc,
                }}
        return R()

    monkeypatch.setattr(search.requests, "get", _get)
    enriched = search.Search().enrich_song("123")
    assert enriched is not None
    assert enriched.title == "Full Track"
    assert enriched.subtitle == "Karta"
    assert enriched.decrypted_media_url == "https://example.com/media/audio_320.mp4"