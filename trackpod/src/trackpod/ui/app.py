"""PySide6 UI for Trackpod (M1) — Library / Queue / Search / Settings.

Requires PySide6 (the ``qt`` extra). All Qt imports live here so that the
headless core stays importable without Qt. Long-running calls (resolve /
download) run in a background ``QThread`` via a small ``Worker``.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trackpod.core import pipeline
from trackpod.core.config import Settings
from trackpod.core.db import Database
from trackpod.core.models import Track

log = logging.getLogger(__name__)


class _Worker(QThread):
    """Run a callable on a worker thread; emit the result or the error."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.succeeded.emit(self.fn(*self.args, **self.kwargs))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class LibraryPage(QWidget):
    """Read-only table of tracks currently tracked in the library."""

    HEADERS = ["Title", "Artist", "Album", "Year", "State", "Source"]

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)

    def refresh(self):
        with self.window.db.session() as session:
            rows = session.query(Track).all()
        self.table.setRowCount(len(rows))
        for i, t in enumerate(rows):
            values = [t.title, t.artist, t.album, t.year, t.state, t.resolved_from or ""]
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(value or ""))


class QueuePage(QWidget):
    """Pending tracks: resolve (Saavn → YouTube) and download."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.track_list = QListWidget()
        self.info = QLabel("No tracks yet.")
        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        row = QHBoxLayout()
        self.resolve_btn = QPushButton("Resolve")
        self.resolve_btn.clicked.connect(self._resolve_all)
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self._download_all)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        row.addWidget(self.resolve_btn)
        row.addWidget(self.download_btn)
        layout.addLayout(row)
        layout.addWidget(self.progress)
        layout.addWidget(self.track_list)

    def refresh(self):
        with self.window.db.session() as session:
            rows = session.query(Track).all()
        self.track_list.clear()
        for t in rows:
            self.track_list.addItem(QListWidgetItem(f"[{t.state}] {t.title} — {t.artist}"))
        self.info.setText(f"{len(rows)} track(s)")

    def _resolve_all(self):
        self._run(pipeline.ensure_tracks, self.window.db, self.window.settings)

    def _download_all(self):
        self._run(pipeline.download_tracks, self.window.db, self.window.settings)

    def _run(self, fn, *args):
        worker = _Worker(fn, *args)
        worker.succeeded.connect(self._done)
        worker.failed.connect(self._failed)
        worker.start()
        self.setEnabled(False)

    def _done(self, _result):
        self.setEnabled(True)
        self.refresh()
        self.window.library_page.refresh()

    def _failed(self, message):
        self.setEnabled(True)
        self.refresh()
        QMessageBox.critical(self, "Trackpod", f"Error:\n{message}")


class SearchPage(QWidget):
    """Add a source (Spotify / Apple / YouTube URL) and ingest its items."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Source URL (Spotify / Apple / YouTube playlist):"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://open.spotify.com/playlist/...")
        layout.addWidget(self.url_edit)

        row = QHBoxLayout()
        add_btn = QPushButton("Add source")
        add_btn.clicked.connect(self._on_add_source)
        ingest_btn = QPushButton("Resolve afterwards")
        ingest_btn.clicked.connect(self._on_add_source)
        row.addWidget(add_btn)
        row.addWidget(ingest_btn)
        layout.addLayout(row)

        self.log_widget = QListWidget()
        layout.addWidget(self.log_widget)

    def _on_add_source(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Trackpod", "Enter a URL first.")
            return
        try:
            source = pipeline.ingest_source(self.window.db, url)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Trackpod", f"Ingest failed:\n{e}")
            return
        self.log(f"Added source #{source.id}: {source.name}")
        self.window.queue_page.refresh()

    def log(self, text: str):
        self.log_widget.addItem(text)
        self.log_widget.scrollToBottom()


class SettingsPage(QWidget):
    """Bind the settings store to simple widgets."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        layout = QVBoxLayout(self)

        box = QGroupBox("Resolver")
        form = QVBoxLayout(box)
        self.saavn_check = QCheckBox("Enable JioSaavn resolver")
        self.saavn_check.setChecked(window.settings.enable_saavn)
        self.yt_fallback = QCheckBox("Fall back to YouTube when Saavn fails")
        self.yt_fallback.setChecked(window.settings.saavn_fallback_youtube)
        form.addWidget(self.saavn_check)
        form.addWidget(self.yt_fallback)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        form.addWidget(save_btn)
        layout.addWidget(box)

        folder_box = QGroupBox("Library folder")
        folder_form = QHBoxLayout(folder_box)
        self.folder_edit = QLineEdit(window.settings.library_folder)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        folder_form.addWidget(self.folder_edit)
        folder_form.addWidget(browse_btn)
        layout.addWidget(folder_box)

    def _save(self):
        s = self.window.settings
        s.set("enable_saavn", str(self.saavn_check.isChecked()).lower())
        s.set("saavn_fallback_youtube", str(self.yt_fallback.isChecked()).lower())
        s.set("library_folder", self.folder_edit.text().strip())
        QMessageBox.information(self, "Trackpod", "Settings saved.")

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose music folder")
        if path:
            self.folder_edit.setText(path)


class TrackpodWindow(QMainWindow):
    """Main window navigating between Library / Queue / Search / Settings."""

    def __init__(self, db: Database | None = None, settings: Settings | None = None):
        super().__init__()
        self.db = db or Database()
        self.db.init()
        self.settings = settings or Settings(self.db.settings_store())
        self.setWindowTitle("Trackpod")
        self.resize(920, 620)

        self.library_page = LibraryPage(self)
        self.queue_page = QueuePage(self)
        self.search_page = SearchPage(self)
        self.settings_page = SettingsPage(self)

        self.stack = QStackedWidget()
        for page in (self.library_page, self.queue_page, self.search_page, self.settings_page):
            self.stack.addWidget(page)
        self.setCentralWidget(self.stack)
        self._build_nav_menu()

        self.queue_page.refresh()
        self.library_page.refresh()

    def _build_nav_menu(self):
        menu = self.menuBar().addMenu("&Navigate")
        for label, page in (
            ("Library", self.library_page),
            ("Queue", self.queue_page),
            ("Search / Add Source", self.search_page),
            ("Settings", self.settings_page),
        ):
            action = QAction(label, self)
            page_index = self.stack.indexOf(page)
            action.triggered.connect(lambda _=False, i=page_index: self.stack.setCurrentIndex(i))
            menu.addAction(action)


def run_application(db: Database | None = None) -> int:
    """Start the Qt event loop with a TrackpodWindow. Returns exit code."""
    app = QApplication.instance() or QApplication([])
    window = TrackpodWindow(db=db)
    window.show()
    return app.exec()
