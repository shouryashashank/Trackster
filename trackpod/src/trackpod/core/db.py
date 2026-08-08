"""DB engine/session factory + settings storage (SQLAlchemy)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from trackpod.core.config import library_db_path
from trackpod.core.models import Base


class SettingsStore:
    """Simple key/value settings table backing core.config.Settings."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str) -> str | None:
        from sqlalchemy import text

        result = self.session.execute(
            text("SELECT value FROM settings WHERE key = :k"), {"k": key}
        ).fetchone()
        return result[0] if result else None

    def set(self, key: str, value: str) -> None:
        from sqlalchemy import text

        self.session.execute(
            text(
                "INSERT INTO settings (key, value) VALUES (:k, :v) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            ),
            {"k": key, "v": str(value)},
        )
        self.session.commit()


def _settings_get_ddl(session: Session) -> None:
    from sqlalchemy import text

    session.execute(
        text(
            "CREATE TABLE IF NOT EXISTS settings ("
            "key TEXT PRIMARY KEY, value TEXT)"
        )
    )
    session.commit()


class Database:
    """Owns the engine + session factory for the library DB."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or library_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(
            f"sqlite:///{self.path}", echo=False, future=True
        )
        self.Session = sessionmaker(bind=self.engine, future=True)

    def init(self) -> None:
        Base.metadata.create_all(self.engine)
        with self.Session() as session:
            _settings_get_ddl(session)

    def session(self) -> Session:
        return self.Session()

    def settings_store(self) -> SettingsStore:
        with self.session() as session:
            _settings_get_ddl(session)
        return SettingsStore(self.session())