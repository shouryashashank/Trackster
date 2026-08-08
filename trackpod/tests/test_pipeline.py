"""Pipeline tests (offline: network source helpers are mocked)."""

from trackpod.core import pipeline
from trackpod.core.config import Settings
from trackpod.core.db import Database
from trackpod.core.models import Source, SourceItem


def _db(tmp_path) -> Database:
    db = Database(tmp_path / "lib.db")
    db.init()
    return db


def _source_with_items(db, items):
    with db.session() as session:
        src = Source(name="t", kind="spotify", external_ref="x")
        session.add(src)
        session.flush()
        for title, artist in items:
            session.add(SourceItem(source_id=src.id, title=title, artist=artist, ref="r"))
        session.commit()
        return src


def test_title_id_normalizes():
    assert pipeline.title_id("Artist", "Song") == "artist - song"
    assert pipeline.title_id("", "Song") == "song"
    assert pipeline.title_id("Artist", "") == "artist"


def test_detect_kind():
    assert pipeline.detect_kind("https://open.spotify.com/track/x") == "spotify"
    assert pipeline.detect_kind("https://music.apple.com/us/album/x") == "apple"
    assert pipeline.detect_kind("https://www.youtube.com/watch?v=x") == "youtube"
    assert pipeline.detect_kind("https://example.com/artist/x") == "artist"


def test_ingest_source_with_spotify_no_net(monkeypatch, tmp_path):
    db = _db(tmp_path)
    monkeypatch.setattr(pipeline, "get_playlist_info", lambda url, sp: [])
    src = pipeline.ingest_source_with(
        db, "https://open.spotify.com/playlist/abc", sp=object()
    )
    assert src.kind == "spotify"
    with db.session() as session:
        assert session.get(Source, src.id).kind == "spotify"


def test_ingest_source_apple_no_net(monkeypatch, tmp_path):
    db = _db(tmp_path)
    monkeypatch.setattr(pipeline, "get_apple_playlist", lambda url: [])
    src = pipeline.ingest_source(db, "https://music.apple.com/us/playlist/x")
    assert src.kind == "apple"
    with db.session() as session:
        assert session.get(Source, src.id).kind == "apple"


def test_ensure_tracks_uses_youtube_fallback_when_saavn_disabled(monkeypatch, tmp_path):
    db = _db(tmp_path)
    src = _source_with_items(db, [("Song A", "Artist A")])
    settings = Settings(db.settings_store())
    settings.set("enable_saavn", "false")

    monkeypatch.setattr(pipeline, "find_youtube", lambda q: "https://youtu.be/wa")
    tracks = pipeline.ensure_tracks(db, src, settings)
    assert len(tracks) == 1
    t = tracks[0]
    assert t.resolved_from == "youtube"
    assert t.media_url == "https://youtu.be/wa"
    assert t.state == "to_resolve"


def test_ensure_tracks_deduplicates_on_title_id(monkeypatch, tmp_path):
    db = _db(tmp_path)
    settings = Settings(db.settings_store())
    settings.set("enable_saavn", "false")
    monkeypatch.setattr(pipeline, "find_youtube", lambda q: "https://youtu.be/x")

    src = _source_with_items(db, [("Song B", "Artist B")])
    first = pipeline.ensure_tracks(db, src, settings)
    src2 = _source_with_items(db, [("Song B", "Artist B")])  # identical title_id
    second = pipeline.ensure_tracks(db, src2, settings)

    assert len(first) == 1
    assert len(second) == 0


def test_ensure_tracks_marks_failed_then_retry(monkeypatch, tmp_path):
    db = _db(tmp_path)
    settings = Settings(db.settings_store())
    settings.set("enable_saavn", "false")

    def boom(q):
        raise ValueError("no net")

    monkeypatch.setattr(pipeline, "find_youtube", boom)
    src = _source_with_items(db, [("Song C", "Artist C")])
    tracks = pipeline.ensure_tracks(db, src, settings)
    assert tracks[0].state == "failed"


def test_count_tracks(tmp_path):
    db = _db(tmp_path)
    assert pipeline.count_tracks(db) == 0
