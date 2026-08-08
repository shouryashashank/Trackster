import os

from mutagen.id3 import ID3, TDRC, TIT2, TPE1, TSRC, USLT

import main


def _make_mp3(path):
    """Create a file that mutagen can read/write without real audio data."""
    tags = ID3()
    tags.save(path, v2_version=3)
    return path


def test_set_metadata_writes_all_fields(tmp_path):
    mp3 = _make_mp3(str(tmp_path / "song.mp3"))
    metadata = {
        "artist_name": "Artist One",
        "artists": ["Artist One", "Artist Two"],
        "album_name": "Album X",
        "track_title": "Track Title",
        "release_date": "2021-02-03",
        "track_number": 5,
        "isrc": "US1234567890",
        "album_art": "",
    }
    main.set_metadata(metadata, mp3, "")

    tags = ID3(mp3)
    assert str(tags["TPE1"].text[0]) == "Artist One"
    assert str(tags["TIT2"].text[0]) == "Track Title"
    assert str(tags["TALB"].text[0]) == "Album X"
    assert str(tags["TDRC"].text[0]) == "2021-02-03"
    assert str(tags["TRCK"].text[0]) == "5"
    assert str(tags["TSRC"].text[0]) == "US1234567890"


def test_set_metadata_handles_missing_optional_fields(tmp_path):
    """isrc/release_date/album_art being None must not crash mutagen."""
    mp3 = _make_mp3(str(tmp_path / "song.mp3"))
    metadata = {
        "artist_name": "A",
        "artists": ["A"],
        "album_name": "B",
        "track_title": "C",
        "release_date": None,
        "track_number": None,
        "isrc": None,
        "album_art": None,
    }
    main.set_metadata(metadata, mp3, "")  # should not raise
    tags = ID3(mp3)
    # empty isrc/release_date frames are dropped by mutagen; track_number falls back to 0
    assert str(tags["TRCK"].text[0]) == "0"
    assert "TSRC" not in tags


def test_set_metadata_writes_lyrics(tmp_path):
    mp3 = _make_mp3(str(tmp_path / "song.mp3"))
    metadata = {
        "artist_name": "A",
        "artists": ["A"],
        "album_name": "B",
        "track_title": "C",
        "release_date": "2020-01-01",
        "track_number": 1,
        "isrc": "",
        "album_art": None,
    }
    main.set_metadata(metadata, mp3, "Line one\nLine two")
    tags = ID3(mp3)
    assert str(tags.getall("USLT")[0].text) == "Line one\nLine two"


def test_set_metadata_adds_album_art(tmp_path):
    mp3 = _make_mp3(str(tmp_path / "song.mp3"))
    jpg = tmp_path / "cover.jpg"
    jpg.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    metadata = {
        "artist_name": "A",
        "artists": ["A"],
        "album_name": "B",
        "track_title": "C",
        "release_date": "2020-01-01",
        "track_number": 1,
        "isrc": "",
        "album_art": jpg.as_uri(),  # file:// URI -> no network needed
    }
    main.set_metadata(metadata, mp3, "")
    from mutagen.id3 import APIC

    tags = ID3(mp3)
    apic = tags.get("APIC:Cover")
    assert apic is not None
    assert apic.data.startswith(b"\xff\xd8\xff\xe0")