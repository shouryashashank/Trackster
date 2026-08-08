import os
import sqlite3
import logging

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trackster.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS downloaded_songs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                title         TEXT NOT NULL,
                file_path     TEXT,
                source        TEXT,
                downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS failed_songs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL UNIQUE,
                reason     TEXT,
                failed_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mismatched_songs (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                title              TEXT,
                original_artist    TEXT,
                downloaded_artist  TEXT,
                created_at         TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS synced_tracks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                spotify_id TEXT UNIQUE,
                synced_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return default
    try:
        return row["value"]
    except Exception:
        return row[0]


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


# --------------------------------------------------------------------------
# Downloaded songs
# --------------------------------------------------------------------------

def add_downloaded(title, file_path="", source=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO downloaded_songs (title, file_path, source) "
            "VALUES (?, ?, ?)",
            (title, file_path, source),
        )


def is_downloaded(title):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM downloaded_songs WHERE title = ? LIMIT 1", (title,)
        ).fetchone()
    return row is not None


def get_downloaded_titles():
    with get_conn() as conn:
        rows = conn.execute("SELECT title FROM downloaded_songs").fetchall()
    return {row["title"] for row in rows}


# --------------------------------------------------------------------------
# Failed songs
# --------------------------------------------------------------------------

def add_failed(title, reason=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO failed_songs (title, reason) VALUES (?, ?) "
            "ON CONFLICT(title) DO UPDATE SET reason = excluded.reason, "
            "failed_at = CURRENT_TIMESTAMP",
            (title, reason),
        )


def remove_failed(title):
    with get_conn() as conn:
        conn.execute("DELETE FROM failed_songs WHERE title = ?", (title,))


def get_failed_titles():
    with get_conn() as conn:
        rows = conn.execute("SELECT title FROM failed_songs").fetchall()
    return {row["title"] for row in rows}


def clear_failed():
    with get_conn() as conn:
        conn.execute("DELETE FROM failed_songs")


# --------------------------------------------------------------------------
# Mismatched songs
# --------------------------------------------------------------------------

def add_mismatch(title, original_artist, downloaded_artist):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO mismatched_songs (title, original_artist, "
            "downloaded_artist) VALUES (?, ?, ?)",
            (title, original_artist, downloaded_artist),
        )


def get_mismatches():
    with get_conn() as conn:
        return conn.execute(
            "SELECT title, original_artist, downloaded_artist "
            "FROM mismatched_songs"
        ).fetchall()


# --------------------------------------------------------------------------
# Synced Spotify tracks
# --------------------------------------------------------------------------

def add_synced(spotify_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO synced_tracks (spotify_id) VALUES (?) "
            "ON CONFLICT(spotify_id) DO NOTHING",
            (spotify_id,),
        )


def get_synced_ids():
    with get_conn() as conn:
        rows = conn.execute("SELECT spotify_id FROM synced_tracks").fetchall()
    return {row["spotify_id"] for row in rows}


# --------------------------------------------------------------------------
# .env migration (one-time)
# --------------------------------------------------------------------------

def migrate_env(env_path=".env"):
    """Import SPOTIPY_CLIENT_ID/SECRET from .env into settings once."""
    if get_setting("SPOTIPY_CLIENT_ID") is not None:
        return
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET") and value:
                    set_setting(key, value)
    except Exception as e:
        log.warning("Failed to migrate .env: %s", e)
