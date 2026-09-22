"""Main window: navigation, theme, and backups."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from flashcard_app.backup import maybe_auto_backup
from flashcard_app.db import Database
from flashcard_app.ui.dashboard import DashboardPage
from flashcard_app.ui.dialogs import shortcut_help
from flashcard_app.ui.importer_view import ImportPage
from flashcard_app.ui.library import LibraryPage
from flashcard_app.ui.search_view import SearchPage
from flashcard_app.ui.study import StudyPage
from flashcard_app.ui.theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle("Flashcards")
        self.resize(1120, 760)
        self.dashboard = DashboardPage(db)
        self.library = LibraryPage(db)
        self.study = StudyPage(db)
        self.importer = ImportPage(db)
        self.search = SearchPage(db)
        self.pages = {
            "dashboard": self.dashboard,
            "library": self.library,
            "study": self.study,
            "import": self.importer,
            "search": self.search,
        }
        self.stack = QStackedWidget()
        for page in self.pages.values():
            self.stack.addWidget(page)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 16, 12, 16)
        brand = QLabel("Flashcards")
        brand.setObjectName("appTitle")
        side_layout.addWidget(brand)
        side_layout.addSpacing(12)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("dashboard", "Dashboard"),
            ("library", "Library"),
            ("study", "Study"),
            ("import", "Import"),
            ("search", "Search"),
        ):
            button = QPushButton(label)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=key: self.open_page(name))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            side_layout.addWidget(button)
        side_layout.addStretch(1)
        self.theme_button = QPushButton("Dark theme")
        self.theme_button.clicked.connect(self.toggle_theme)
        backup_button = QPushButton("Back up now")
        backup_button.clicked.connect(lambda: self.backup(manual=True))
        side_layout.addWidget(self.theme_button)
        side_layout.addWidget(backup_button)

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(sidebar)
        shell_layout.addWidget(self.stack, 1)
        self.setCentralWidget(shell)
        self._build_menu()
        self._sync_theme_button()

        self.dashboard.study_due.connect(self._study_due)
        self.dashboard.browse_deck.connect(self._browse_deck)
        self.library.changed.connect(self.refresh_all)
        self.study.changed.connect(self.refresh_all)
        self.importer.changed.connect(self.refresh_all)
        self.search.changed.connect(self.refresh_all)

        self.backup_timer = QTimer(self)
        self.backup_timer.setInterval(30 * 60 * 1000)
        self.backup_timer.timeout.connect(lambda: self.backup(manual=False))
        self.backup_timer.start()
        self.open_page("dashboard")
        self.backup(manual=False)

    def open_page(self, key: str) -> None:
        self.stack.setCurrentWidget(self.pages[key])
        button = self.nav_buttons[key]
        if not button.isChecked():
            button.setChecked(True)
        self.pages[key].refresh()
        if key == "search":
            self.search.focus_query()

    def refresh_all(self) -> None:
        current = self.stack.currentWidget()
        for page in self.pages.values():
            if page is current or page is not self.study:
                page.refresh()

    def toggle_theme(self) -> None:
        current = self.db.get_setting("theme", "light") or "light"
        mode = "light" if current == "dark" else "dark"
        self.db.set_setting("theme", mode)
        app = _app()
        if app is not None:
            apply_theme(app, mode)
        self._sync_theme_button()
        self.dashboard.refresh()

    def backup(self, manual: bool = False) -> None:
        try:
            if manual:
                from flashcard_app.backup import backup_database

                path = backup_database(self.db)
                self.db.set_setting("last_backup_at", _now())
            else:
                path = maybe_auto_backup(self.db)
        except Exception as exc:  # surface disk and sqlite failures in the status bar
            self.statusBar().showMessage(f"Backup failed: {exc}")
            if manual:
                QMessageBox.warning(self, "Backup", str(exc))
            return
        if path is not None:
            self.statusBar().showMessage(f"Backed up to {path.name}")
            if manual:
                QMessageBox.information(self, "Backup", f"Saved {path}")
            self.dashboard.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        try:
            maybe_auto_backup(self.db)
        except Exception:
            pass
        self.db.close()
        super().closeEvent(event)

    def _study_due(self, deck_id: int) -> None:
        self.open_page("study")
        self.study.begin(None if deck_id < 0 else deck_id, due_only=True, shuffle=False)

    def _browse_deck(self, deck_id: int) -> None:
        self.open_page("library")
        self.library.set_deck(deck_id)

    def _new_card(self) -> None:
        self.open_page("library")
        self.library.new_card()

    def _sync_theme_button(self) -> None:
        mode = self.db.get_setting("theme", "light") or "light"
        self.theme_button.setText("Light theme" if mode == "dark" else "Dark theme")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self._action(file_menu, "New card", "Ctrl+N", self._new_card)
        self._action(file_menu, "Import", "Ctrl+I", lambda: self.open_page("import"))
        file_menu.addSeparator()
        self._action(file_menu, "Export JSON", None, lambda: self.library.export_cards("json"))
        self._action(file_menu, "Export CSV", None, lambda: self.library.export_cards("csv"))
        self._action(file_menu, "Export Anki", None, lambda: self.library.export_cards("anki"))
        file_menu.addSeparator()
        self._action(file_menu, "Back up now", "Ctrl+B", lambda: self.backup(manual=True))
        self._action(file_menu, "Quit", "Ctrl+Q", self.close)

        view_menu = self.menuBar().addMenu("View")
        self._action(view_menu, "Dashboard", "Ctrl+1", lambda: self.open_page("dashboard"))
        self._action(view_menu, "Library", "Ctrl+2", lambda: self.open_page("library"))
        self._action(view_menu, "Study", "Ctrl+3", lambda: self.open_page("study"))
        self._action(view_menu, "Import", "Ctrl+4", lambda: self.open_page("import"))
        self._action(view_menu, "Search", "Ctrl+5", lambda: self.open_page("search"))
        self._action(view_menu, "Find", "Ctrl+F", lambda: self.open_page("search"))
        self._action(view_menu, "Toggle theme", "Ctrl+D", self.toggle_theme)

        tools_menu = self.menuBar().addMenu("Tools")
        self._action(tools_menu, "Merge decks", None, self.library.merge_decks)
        self._action(tools_menu, "Rename tag", None, self.library.rename_tag)
        self._action(tools_menu, "Find duplicates", None, self.library.find_duplicates)

        help_menu = self.menuBar().addMenu("Help")
        self._action(
            help_menu,
            "Keyboard shortcuts",
            None,
            lambda: QMessageBox.information(self, "Keyboard shortcuts", shortcut_help()),
        )

    def _action(self, menu, label: str, shortcut: str | None, slot) -> None:
        action = QAction(label, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ApplicationShortcut)
        action.triggered.connect(slot)
        menu.addAction(action)


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance()


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")
