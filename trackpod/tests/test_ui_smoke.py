"""Offscreen UI smoke test (skipped when PySide6 is not installed)."""

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_window_constructs_offscreen(tmp_path):
    from PySide6.QtWidgets import QApplication

    from trackpod.core.db import Database
    from trackpod.core.models import Track
    from trackpod.ui.app import TrackpodWindow

    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / "lib.db")
    db.init()
    with db.session() as session:
        session.add(Track(title="Hi", artist="You", title_id="you - hi"))
        session.commit()

    win = TrackpodWindow(db=db)
    assert win.stack.count() == 4
    win.queue_page.refresh()
    win.library_page.refresh()
    assert win.library_page.table.rowCount() >= 1
    win.close()
    app.processEvents()
