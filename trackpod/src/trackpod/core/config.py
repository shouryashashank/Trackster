"""App-wide settings and path resolution (UI-agnostic)."""

import os
import sys
from pathlib import Path


def user_data_dir() -> Path:
    """Per-user data directory (cross-platform). DB + config live here."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(base) / "trackpod"


def library_db_path(data_dir: Path | None = None) -> Path:
    """Path to the SQLite library database."""
    d = data_dir or user_data_dir()
    return d / "library.db"


def default_music_folder() -> str:
    """Default download folder (can be overridden in settings/library manager)."""
    return str(user_data_dir() / "Music")


class Settings:
    """Runtime settings, backed by the settings table in the library DB."""

    DEFAULT = {
        "library_folder": None,  # user-managed folder; defaults to default_music_folder
        "enable_saavn": "true",  # global toggle for the Saavn resolver
        "saavn_fallback_youtube": "true",  # try YouTube when Saavn fails/disabled
        "keep_tmp_files": "false",
        "concurrency": "4",
    }

    def __init__(self, store) -> None:
        """Wrap a key/value storage abstraction (see core.db.SettingsStore)."""
        self._store = store

    def get(self, key: str) -> str:
        return self._store.get(key) if self._store else self.DEFAULT.get(key, "")

    def get_bool(self, key: str, default: bool = True) -> bool:
        raw = self.get(key)
        if not raw:
            return default
        return raw.strip().lower() == "true"

    def get_int(self, key: str, default: int = 4) -> int:
        try:
            return int(self.get(key))
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value: str) -> None:
        if self._store is not None:
            self._store.set(key, str(value))

    @property
    def library_folder(self) -> str:
        folder = self.get("library_folder")
        return folder or default_music_folder()

    @property
    def enable_saavn(self) -> bool:
        return self.get_bool("enable_saavn", True)

    @property
    def saavn_fallback_youtube(self) -> bool:
        return self.get_bool("saavn_fallback_youtube", True)

    @property
    def concurrency(self) -> int:
        return max(1, self.get_int("concurrency", 4))
