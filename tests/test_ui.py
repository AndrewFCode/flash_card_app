import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from flashcard_app.db import Database
from flashcard_app.models import SearchFilters
from flashcard_app.parser import parse_notes
from flashcard_app.ui.main_window import MainWindow
from flashcard_app.ui.theme import apply_theme


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance() or QApplication([])
    apply_theme(application, "light")
    return application


def test_study_search_import_and_theme(qapp, tmp_path):
    db = Database(tmp_path / "cards.db")
    deck_id = db.create_deck("Biology")
    created = db.create_card(deck_id, "What is ATP?", "Energy currency of the cell", ["energy"])
    window = MainWindow(db)
    window.show()
    qapp.processEvents()

    assert window.dashboard.due_tile.value.text() == "1"
    window.open_page("study")
    window.study.begin(deck_id, due_only=True, shuffle=False)
    assert "What is ATP?" in window.study.card_face.face.text()
    QTest.keyClick(window.study.card_face, Qt.Key_Space)
    qapp.processEvents()
    assert "Energy currency" in window.study.card_face.face.text()
    assert window.study.rate_buttons["good"].isVisible()
    QTest.keyClick(window.study.card_face, Qt.Key_3)
    qapp.processEvents()
    reviewed = db.get_card(created.id)
    assert reviewed.review_count == 1
    assert reviewed.interval_days == 1
    assert "Session complete" in window.study.progress.text()

    window.open_page("search")
    window.search.query.setText("currency")
    window.search.run_search()
    assert window.search.table.rowCount() == 1

    window.importer._show_parsed(parse_notes("Osmosis: Movement of water"), "notes.md")
    assert window.importer.table.rowCount() == 1
    window.importer.save_selected()
    qapp.processEvents()
    assert len(db.search_cards(SearchFilters())) == 2

    window.toggle_theme()
    assert db.get_setting("theme") == "dark"
    window.toggle_theme()
    assert db.get_setting("theme") == "light"
    window.close()
