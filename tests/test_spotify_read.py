import db
import main


class R:
    status_code = 200


def _track_json(tid, name="Track"):
    return {
        "artists": [{"name": "Artist"}],
        "name": name,
        "track_number": 1,
        "external_ids": {"isrc": "US123"},
        "album": {"images": [None, {"url": "http://img/x.jpg"}, None],
                  "name": "Album", "release_date": "2020-01-01"},
    }


def test_get_playlist_info_fetches_and_syncs(monkeypatch):
    class FakeSp:
        def playlist(self, url):
            return {"public": True}

        def playlist_tracks(self, url):
            return {"items": [{"track": {"id": "t1"}}, {"track": {"id": "t2"}},
                              {"track": None}], "next": None}

        def track(self, url):
            return _track_json(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())
    result = main.get_playlist_info("https://open.spotify.com/playlist/x", FakeSp())
    assert [r["track_title"] for r in result] == ["Track", "Track"]
    # only successfully-fetched tracks are marked synced
    assert db.get_synced_ids() == {"t1", "t2"}


def test_get_playlist_info_paginates(monkeypatch):
    class FakeSp:
        def playlist(self, url):
            return {"public": True}

        def playlist_tracks(self, url):
            return {"items": [{"track": {"id": "p1"}}], "next": "more"}

        def next(self, playlist):
            return {"items": [{"track": {"id": "p2"}}], "next": None}

        def track(self, url):
            return _track_json(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())
    result = main.get_playlist_info("https://open.spotify.com/playlist/x", FakeSp())
    assert len(result) == 2
    assert db.get_synced_ids() == {"p1", "p2"}


def test_get_playlist_info_skips_already_synced(monkeypatch):
    db.add_synced("old1")
    synced_calls = []

    class FakeSp:
        def playlist(self, url):
            return {"public": True}

        def playlist_tracks(self, url):
            return {"items": [{"track": {"id": "old1"}}, {"track": {"id": "new1"}}],
                    "next": None}

        def track(self, url):
            synced_calls.append(url)
            return _track_json(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())
    result = main.get_playlist_info("https://open.spotify.com/playlist/x", FakeSp())
    assert len(result) == 1
    # only the new track was fetched via the API
    assert synced_calls == ["https://open.spotify.com/track/new1"]


def test_get_album_info_parallel(monkeypatch):
    class FakeSp:
        def album_tracks(self, url):
            return {"items": [{"id": "a1"}, {"id": "a2"}], "next": None}

        def track(self, url):
            return _track_json(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())
    result = main.get_album_info("https://open.spotify.com/album/x", FakeSp())
    assert len(result) == 2
    assert db.get_synced_ids() == {"a1", "a2"}


def test_get_playlist_info_rejects_private(monkeypatch):
    class FakeSp:
        def playlist(self, url):
            return {"public": False}

        def playlist_tracks(self, url):
            return {"items": [], "next": None}

    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())
    import pytest

    with pytest.raises(ValueError):
        main.get_playlist_info("https://open.spotify.com/playlist/x", FakeSp())


def test_get_track_info_spotify_parses(monkeypatch):
    class FakeSp:
        def track(self, url):
            return _track_json("t9", "Nice Song")

    monkeypatch.setattr(main.requests, "get", lambda *a, **k: R())
    info = main.get_track_info_spotify("https://open.spotify.com/track/t9", FakeSp())
    assert info["artist_name"] == "Artist"
    assert info["track_title"] == "Nice Song"
    assert info["isrc"] == "US123"
    assert info["album_art"] == "http://img/x.jpg"


def test_get_spotify_client_missing_creds(monkeypatch):
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "get_setting", lambda k, d=None: None)
    monkeypatch.setattr(main.os, "getenv", lambda k, d=None: None)
    assert main.get_spotify_client() is None
