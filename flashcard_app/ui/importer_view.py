"""Import notes, pasted text, and deck files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashcard_app.db import Database
from flashcard_app.duplicates import first_duplicate
from flashcard_app.exchange import load_exchange_file
from flashcard_app.models import ImportedCard, SearchFilters
from flashcard_app.parser import parse_delimited_lines, parse_file, parse_notes
from flashcard_app.tags import parse_tags
from flashcard_app.ui.theme import theme_colors


@dataclass
class _Extra:
    source_file: str | None = None
    imported: ImportedCard | None = None


class ImportPage(QWidget):
    changed = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.extras: list[_Extra] = []
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        title = QLabel("Import")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        intro = QLabel(
            "Bring in notes, a paste, or a deck file. Edit the preview, then save the rows you want."
        )
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        layout.addWidget(intro)

        self.deck_combo = QComboBox()
        self.deck_combo.setEditable(True)
        if self.deck_combo.lineEdit() is not None:
            self.deck_combo.lineEdit().setPlaceholderText("Deck for new cards")
        deck_row = QHBoxLayout()
        deck_row.addWidget(QLabel("Deck"))
        deck_row.addWidget(self.deck_combo, 1)
        layout.addLayout(deck_row)

        tabs = QTabWidget()
        tabs.addTab(self._notes_tab(), "Notes file")
        tabs.addTab(self._paste_tab(), "Paste")
        tabs.addTab(self._deck_tab(), "Deck file")
        layout.addWidget(tabs)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Include", "Front", "Back", "Deck", "Tags", "Note"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        save_row = QHBoxLayout()
        save = QPushButton("Save selected")
        save.setObjectName("primary")
        save.clicked.connect(self.save_selected)
        clear = QPushButton("Clear preview")
        clear.clicked.connect(self.clear_preview)
        self.preview_label = QLabel("")
        self.preview_label.setObjectName("muted")
        save_row.addWidget(save)
        save_row.addWidget(clear)
        save_row.addWidget(self.preview_label)
        save_row.addStretch(1)
        layout.addLayout(save_row)
        self._reload_decks()

    def refresh(self) -> None:
        self._reload_decks()

    def clear_preview(self) -> None:
        self.table.setRowCount(0)
        self.extras = []
        self.preview_label.setText("")

    def save_selected(self) -> None:
        records: list[ImportedCard] = []
        default_deck = self.deck_combo.currentText().strip() or "General"
        for row in range(self.table.rowCount()):
            include = self.table.item(row, 0)
            if include is None or include.checkState() != Qt.Checked:
                continue
            front = self.table.item(row, 1).text().strip()
            back = self.table.item(row, 2).text().strip()
            deck = self.table.item(row, 3).text().strip() or default_deck
            tags = parse_tags(self.table.item(row, 4).text())
            extra = self.extras[row]
            imported = extra.imported
            records.append(
                ImportedCard(
                    front=front,
                    back=back,
                    deck=deck,
                    tags=tags,
                    source_file=extra.source_file,
                    ease_factor=None if imported is None else imported.ease_factor,
                    interval_days=None if imported is None else imported.interval_days,
                    repetitions=None if imported is None else imported.repetitions,
                    due_date=None if imported is None else imported.due_date,
                    confidence=None if imported is None else imported.confidence,
                    review_count=None if imported is None else imported.review_count,
                    created_at=None if imported is None else imported.created_at,
                    last_reviewed_at=None if imported is None else imported.last_reviewed_at,
                )
            )
        if not records:
            QMessageBox.information(self, "Import", "Select at least one card to save.")
            return
        try:
            saved = self.db.import_cards(records, default_deck)
        except ValueError as exc:
            QMessageBox.warning(self, "Import", str(exc))
            return
        if saved == 0:
            QMessageBox.information(self, "Import", "Selected rows need both a front and a back.")
            return
        self.clear_preview()
        self.preview_label.setText(f"Saved {saved} card{'s' if saved != 1 else ''}.")
        self.changed.emit()

    def _notes_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        browse = QPushButton("Choose file")
        browse.clicked.connect(self._choose_notes)
        self.notes_path = QLabel("Plain text, Markdown, or PDF")
        self.notes_path.setObjectName("muted")
        layout.addWidget(browse)
        layout.addWidget(self.notes_path, 1)
        return page

    def _paste_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.paste = QPlainTextEdit()
        self.paste.setPlaceholderText(
            "Paste notes to detect cards, or enter one card per line:\n"
            "What is mitosis? | Cell division that produces two identical daughter cells"
        )
        self.paste.setMinimumHeight(120)
        buttons = QHBoxLayout()
        detect = QPushButton("Detect cards")
        detect.clicked.connect(self._parse_paste)
        split = QPushButton("Split on |")
        split.clicked.connect(self._split_paste)
        buttons.addWidget(detect)
        buttons.addWidget(split)
        buttons.addStretch(1)
        layout.addWidget(self.paste)
        layout.addLayout(buttons)
        return page

    def _deck_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        browse = QPushButton("Choose deck file")
        browse.clicked.connect(self._choose_deck_file)
        hint = QLabel("JSON, CSV, or Anki plain text")
        hint.setObjectName("muted")
        layout.addWidget(browse)
        layout.addWidget(hint, 1)
        return page

    def _choose_notes(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Import notes",
            "",
            "Notes (*.txt *.md *.markdown *.pdf)",
        )
        if not path:
            return
        self.notes_path.setText(path)
        try:
            cards = parse_file(Path(path))
        except Exception as exc:  # pypdf and OS errors surface here
            QMessageBox.warning(self, "Import", str(exc))
            return
        self._show_parsed(cards, Path(path).name)

    def _parse_paste(self) -> None:
        self._show_parsed(parse_notes(self.paste.toPlainText()), None)

    def _split_paste(self) -> None:
        self._show_parsed(parse_delimited_lines(self.paste.toPlainText()), None)

    def _choose_deck_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Import deck",
            "",
            "Deck files (*.json *.csv *.txt)",
        )
        if not path:
            return
        try:
            records = load_exchange_file(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "Import", str(exc))
            return
        default_deck = self.deck_combo.currentText().strip() or "Imported"
        rows = [
            (
                record.front,
                record.back,
                record.deck or default_deck,
                ", ".join(record.tags),
                _Extra(source_file=record.source_file or Path(path).name, imported=record),
            )
            for record in records
        ]
        self._fill(rows)

    def _show_parsed(self, cards, source_name: str | None) -> None:
        deck = self.deck_combo.currentText().strip() or "Imported"
        rows = [
            (card.front, card.back, deck, "", _Extra(source_file=source_name))
            for card in cards
        ]
        self._fill(rows)

    def _fill(self, rows: list[tuple[str, str, str, str, _Extra]]) -> None:
        existing = [(card.id, card.front) for card in self.db.search_cards(SearchFilters())]
        seen = list(existing)
        flagged = 0
        prepared = []
        for front, back, deck, tags, extra in rows:
            match = first_duplicate(front, seen)
            note = ""
            include = True
            if match:
                note = f"Possible duplicate of “{match}”"
                include = False
                flagged += 1
            prepared.append((include, front, back, deck, tags, note, extra))
            seen.append((None, front))
        self.table.setRowCount(len(prepared))
        self.extras = []
        mode = self.db.get_setting("theme", "light") or "light"
        warn = QColor(theme_colors(mode)["warn"])
        for row, (include, front, back, deck, tags, note, extra) in enumerate(prepared):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            check.setCheckState(Qt.Checked if include else Qt.Unchecked)
            self.table.setItem(row, 0, check)
            values = [front, back, deck, tags, note]
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if column < 5:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if note:
                    item.setBackground(warn)
                self.table.setItem(row, column, item)
            if note:
                check.setBackground(warn)
            self.extras.append(extra)
        if not prepared:
            self.preview_label.setText("No cards detected.")
        else:
            self.preview_label.setText(
                f"{len(prepared)} detected · {flagged} possible duplicate{'s' if flagged != 1 else ''}"
            )

    def _reload_decks(self) -> None:
        current = self.deck_combo.currentText()
        self.deck_combo.blockSignals(True)
        self.deck_combo.clear()
        for deck in self.db.list_decks():
            self.deck_combo.addItem(deck.name, deck.id)
        if current:
            self.deck_combo.setCurrentText(current)
        elif self.deck_combo.count() == 0:
            self.deck_combo.setCurrentText("General")
        self.deck_combo.blockSignals(False)
