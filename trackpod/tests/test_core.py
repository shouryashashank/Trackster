"""Smoke tests for the core DB, models, and settings."""

from pathlib import Path

from trackpod.core.config import Settings, user_data_dir
from trackpod.core.db import Database
from trackpod.core.models import Source, Track, TrackFile, Artist


def test_user_data_dir_is_absolute_and_named():
    d = user_data_dir()
    assert isinstance(d, Path)
    assert d.name == "trackpod"
    assert d.is_absolute()


def test_init_creates_settings_table_and_seed(tmp_path):
    db = Database(tmp_path / "lib.db")
    db.init()
    store = db.settings_store()
    settings = Settings(store)
    assert settings.enable_saavn is True
    settings.set("enable_saavn", "false")
    assert Settings(store).enable_saavn is False


def test_settings_defaults_when_no_store():
    s = Settings(None)
    assert s.enable_saavn is True
    assert s.saavn_fallback_youtube is True
    assert s.concurrency == 4


def test_track_models_roundtrip(tmp_path):
    db = Database(tmp_path / "lib.db")
    db.init()
    with db.session() as session:
        track = Track(
            title="Song", artist="Artist", album="Album", title_id="song||artist", state="done"
        )
        track.files.append(TrackFile(file_path="a.mp3", source_qual="HQ", size_bytes=1024))
        artist = Artist(name="Artist", external_id="a1")
        session.add_all([track, artist])
        session.commit()
        ids = (track.id, artist.id)
    with db.session() as session:
        t = session.query(Track).filter_by(title_id="song||artist").one_or_none()
        assert t is not None and t.state == "done"
        assert len(t.files) == 1 and t.files[0].source_qual == "HQ"
        assert session.query(Artist).filter_by(name="Artist").one() is not None