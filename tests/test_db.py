import db


def test_settings_roundtrip():
    assert db.get_setting("missing_key") is None
    assert db.get_setting("missing_key", "fallback") == "fallback"
    db.set_setting("SPOTIPY_CLIENT_ID", "abc123")
    assert db.get_setting("SPOTIPY_CLIENT_ID") == "abc123"
    db.set_setting("SPOTIPY_CLIENT_ID", "xyz")
    assert db.get_setting("SPOTIPY_CLIENT_ID") == "xyz"


def test_failed_songs_lifecycle():
    db.add_failed("Song A", "network error")
    db.add_failed("Song B")
    assert db.get_failed_titles() == {"Song A", "Song B"}
    db.remove_failed("Song A")
    assert db.get_failed_titles() == {"Song B"}
    db.clear_failed()
    assert db.get_failed_titles() == set()


def test_failed_song_deduplicated():
    db.add_failed("Song A", "first")
    db.add_failed("Song A", "second reason")
    assert len(db.get_failed_titles()) == 1


def test_downloaded_songs():
    assert not db.is_downloaded("Never Downloaded")
    db.add_downloaded("Some Song", "/music/Some Song.mp3", "spotify")
    assert db.is_downloaded("Some Song")
    assert "Some Song" in db.get_downloaded_titles()


def test_synced_tracks():
    assert db.get_synced_ids() == set()
    db.add_synced("track_1")
    db.add_synced("track_2")
    db.add_synced("track_1")  # duplicate ignored
    assert db.get_synced_ids() == {"track_1", "track_2"}


def test_mismatches():
    assert db.get_mismatches() == []
    db.add_mismatch("Title", "Original", "Downloaded")
    rows = db.get_mismatches()
    assert rows[0]["title"] == "Title"
    assert rows[0]["original_artist"] == "Original"
    assert rows[0]["downloaded_artist"] == "Downloaded"


def test_migrate_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "SPOTIPY_CLIENT_ID=id_from_env\n"
        "SPOTIPY_CLIENT_SECRET=secret_from_env\n"
        "OTHER=ignored\n",
        encoding="utf-8",
    )
    db.migrate_env(str(env))
    assert db.get_setting("SPOTIPY_CLIENT_ID") == "id_from_env"
    assert db.get_setting("SPOTIPY_CLIENT_SECRET") == "secret_from_env"
    assert db.get_setting("OTHER") is None


def test_migrate_env_is_idempotent(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SPOTIPY_CLIENT_ID=first\n", encoding="utf-8")
    db.migrate_env(str(env))
    env.write_text("SPOTIPY_CLIENT_ID=second\n", encoding="utf-8")
    db.migrate_env(str(env))
    # existing value must not be overwritten on second run
    assert db.get_setting("SPOTIPY_CLIENT_ID") == "first"