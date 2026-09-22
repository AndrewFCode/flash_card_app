"""Browse, edit, and organize cards."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashcard_app.db import Database
from flashcard_app.exchange import export_anki, export_csv, export_json
from flashcard_app.models import SORT_LABELS, SearchFilters
from flashcard_app.ui.dialogs import (
    CardDialog,
    DeckDialog,
    DuplicatesDialog,
    MergeDialog,
    RenameTagDialog,
    confirm,
    report_error,
)
from flashcard_app.ui.widgets import preview


class LibraryPage(QWidget):
    changed = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        title = QLabel("Library")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        filters = QHBoxLayout()
        self.deck_combo = QComboBox()
        self.sort_combo = QComboBox()
        for key, label in SORT_LABELS.items():
            self.sort_combo.addItem(label, key)
        self.deck_combo.currentIndexChanged.connect(self.reload)
        self.sort_combo.currentIndexChanged.connect(self.reload)
        filters.addWidget(QLabel("Deck"))
        filters.addWidget(self.deck_combo, 1)
        filters.addWidget(QLabel("Sort"))
        filters.addWidget(self.sort_combo, 1)
        layout.addLayout(filters)

        actions = QHBoxLayout()
        new_card = QPushButton("New card")
        new_card.setObjectName("primary")
        new_card.clicked.connect(self.new_card)
        new_deck = QPushButton("New deck")
        new_deck.clicked.connect(self.new_deck)
        edit = QPushButton("Edit")
        edit.clicked.connect(self.edit_current)
        delete = QPushButton("Delete")
        delete.setObjectName("danger")
        delete.clicked.connect(self.delete_selected)
        export = QPushButton("Export")
        menu = QMenu(export)
        menu.addAction("JSON", lambda: self.export_cards("json"))
        menu.addAction("CSV", lambda: self.export_cards("csv"))
        menu.addAction("Anki", lambda: self.export_cards("anki"))
        export.setMenu(menu)
        for button in (new_card, new_deck, edit, delete, export):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        bulk = QHBoxLayout()
        self.move_combo = QComboBox()
        move = QPushButton("Move")
        move.clicked.connect(self.move_selected)
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText("tag")
        add_tag = QPushButton("Add tag")
        add_tag.clicked.connect(self.add_tag)
        remove_tag = QPushButton("Remove tag")
        remove_tag.clicked.connect(self.remove_tag)
        bulk.addWidget(QLabel("Move to"))
        bulk.addWidget(self.move_combo)
        bulk.addWidget(move)
        bulk.addWidget(self.tag_edit)
        bulk.addWidget(add_tag)
        bulk.addWidget(remove_tag)
        bulk.addStretch(1)
        layout.addLayout(bulk)

        tools = QHBoxLayout()
        merge = QPushButton("Merge decks")
        merge.clicked.connect(self.merge_decks)
        rename = QPushButton("Rename tag")
        rename.clicked.connect(self.rename_tag)
        dupes = QPushButton("Find duplicates")
        dupes.clicked.connect(self.find_duplicates)
        select_all = QPushButton("Select all")
        select_all.clicked.connect(lambda: self._set_all_checks(Qt.Checked))
        select_none = QPushButton("Select none")
        select_none.clicked.connect(lambda: self._set_all_checks(Qt.Unchecked))
        for button in (merge, rename, dupes, select_all, select_none):
            tools.addWidget(button)
        tools.addStretch(1)
        layout.addLayout(tools)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["", "Front", "Deck", "Tags", "Due", "Confidence", "Reviews"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda _index: self.edit_current())
        layout.addWidget(self.table)
        self.count_label = QLabel("")
        self.count_label.setObjectName("muted")
        layout.addWidget(self.count_label)
        self._reload_filters()

    def refresh(self) -> None:
        self._reload_filters()
        self.reload()

    def set_deck(self, deck_id: int) -> None:
        self._reload_filters()
        index = self.deck_combo.findData(deck_id)
        self.deck_combo.blockSignals(True)
        self.deck_combo.setCurrentIndex(max(0, index))
        self.deck_combo.blockSignals(False)
        self.reload()

    def selected_deck_id(self) -> int | None:
        value = self.deck_combo.currentData()
        if value in (None, -1):
            return None
        return int(value)

    def new_card(self) -> None:
        dialog = CardDialog(self.db, deck_id=self.selected_deck_id(), parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.changed.emit()

    def new_deck(self) -> None:
        dialog = DeckDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.db.create_deck(dialog.name.text(), dialog.description.text())
        except ValueError as exc:
            report_error(self, exc)
            return
        self.changed.emit()

    def edit_current(self) -> None:
        card_id = self._current_card_id()
        if card_id is None:
            return
        dialog = CardDialog(self.db, card=self.db.get_card(card_id), parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.changed.emit()

    def delete_selected(self) -> None:
        ids = self.selected_ids() or ([self._current_card_id()] if self._current_card_id() else [])
        ids = [card_id for card_id in ids if card_id is not None]
        if not ids:
            return
        if not confirm(self, "Delete cards", f"Delete {len(ids)} card{'s' if len(ids) != 1 else ''}?"):
            return
        self.db.delete_cards(ids)
        self.changed.emit()

    def move_selected(self) -> None:
        ids = self.selected_ids()
        deck_id = self.move_combo.currentData()
        if not ids or deck_id in (None, -1):
            return
        self.db.move_cards(ids, int(deck_id))
        self.changed.emit()

    def add_tag(self) -> None:
        self._retag(add=True)

    def remove_tag(self) -> None:
        self._retag(add=False)

    def merge_decks(self) -> None:
        if len(self.db.list_decks()) < 2:
            QMessageBox.information(self, "Merge decks", "Create another deck first.")
            return
        dialog = MergeDialog(self.db, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.db.merge_decks(dialog.selected_sources(), dialog.target_id())
        except ValueError as exc:
            report_error(self, exc)
            return
        self.changed.emit()

    def rename_tag(self) -> None:
        if not self.db.list_tags():
            QMessageBox.information(self, "Rename tag", "There are no tags yet.")
            return
        dialog = RenameTagDialog(self.db, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.db.rename_tag(dialog.tag.currentText(), dialog.new_name.text())
        except ValueError as exc:
            report_error(self, exc)
            return
        self.changed.emit()

    def find_duplicates(self) -> None:
        groups = self.db.find_duplicate_groups()
        if not groups:
            QMessageBox.information(self, "Duplicates", "No duplicate fronts found.")
            return
        dialog = DuplicatesDialog(groups, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.db.delete_cards(dialog.selected_ids())
        self.changed.emit()

    def export_cards(self, kind: str) -> None:
        filters = {
            "json": ("JSON (*.json)", "flashcards.json"),
            "csv": ("CSV (*.csv)", "flashcards.csv"),
            "anki": ("Anki text (*.txt)", "flashcards-anki.txt"),
        }
        pattern, suggested = filters[kind]
        path, _selected = QFileDialog.getSaveFileName(self, "Export cards", suggested, pattern)
        if not path:
            return
        cards = self.db.search_cards(SearchFilters())
        from pathlib import Path

        target = Path(path)
        if kind == "json":
            export_json(cards, target)
        elif kind == "csv":
            export_csv(cards, target)
        else:
            export_anki(cards, target)
        QMessageBox.information(self, "Export", f"Exported {len(cards)} cards.")

    def reload(self) -> None:
        cards = self.db.search_cards(self._filters())
        self.table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            check.setCheckState(Qt.Unchecked)
            check.setData(Qt.UserRole, card.id)
            self.table.setItem(row, 0, check)
            values = [
                preview(card.front),
                card.deck_name,
                ", ".join(card.tags),
                card.due_date,
                str(round(card.confidence)),
                str(card.review_count),
            ]
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setToolTip(card.front if column == 1 else value)
                self.table.setItem(row, column, item)
        self.count_label.setText(f"{len(cards)} card{'s' if len(cards) != 1 else ''}")

    def selected_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                ids.append(int(item.data(Qt.UserRole)))
        return ids

    def _filters(self) -> SearchFilters:
        return SearchFilters(deck_id=self.selected_deck_id(), sort=self.sort_combo.currentData() or "recently_added")

    def _reload_filters(self) -> None:
        deck_id = self.selected_deck_id()
        move_id = self.move_combo.currentData()
        self.deck_combo.blockSignals(True)
        self.move_combo.blockSignals(True)
        self.deck_combo.clear()
        self.move_combo.clear()
        self.deck_combo.addItem("All decks", -1)
        for deck in self.db.list_decks():
            self.deck_combo.addItem(deck.name, deck.id)
            self.move_combo.addItem(deck.name, deck.id)
        deck_index = self.deck_combo.findData(deck_id if deck_id is not None else -1)
        self.deck_combo.setCurrentIndex(max(0, deck_index))
        move_index = self.move_combo.findData(move_id)
        if move_index >= 0:
            self.move_combo.setCurrentIndex(move_index)
        self.deck_combo.blockSignals(False)
        self.move_combo.blockSignals(False)

    def _current_card_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return int(item.data(Qt.UserRole))

    def _set_all_checks(self, state: Qt.CheckState) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def _retag(self, add: bool) -> None:
        ids = self.selected_ids()
        if not ids or not self.tag_edit.text().strip():
            return
        try:
            if add:
                self.db.add_tag_to_cards(ids, self.tag_edit.text())
            else:
                self.db.remove_tag_from_cards(ids, self.tag_edit.text())
        except ValueError as exc:
            report_error(self, exc)
            return
        self.changed.emit()
