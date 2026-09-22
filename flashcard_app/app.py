"""Launch the desktop app."""

from __future__ import annotations

import sys

from flashcard_app.db import Database
from flashcard_app.paths import database_path


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from flashcard_app.ui.main_window import MainWindow
    from flashcard_app.ui.theme import apply_theme

    app = QApplication(sys.argv)
    app.setApplicationName("Flashcards")
    app.setStyle("Fusion")
    db = Database(database_path())
    apply_theme(app, db.get_setting("theme", "light") or "light")
    window = MainWindow(db)
    window.show()
    code = app.exec()
    db.close()
    raise SystemExit(code)
