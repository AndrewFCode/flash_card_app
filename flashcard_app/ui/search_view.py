"""Search and filter cards."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashcard_app.db import Database
from flashcard_app.models import SORT_LABELS, SearchFilters
from flashcard_app.ui.dialogs import CardDialog
from flashcard_app.ui.widgets import preview


class SearchPage(QWidget):
    changed = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self._has_searched = False
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        title = QLabel("Search")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        query_row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search fronts, backs, and tags")
        self.query.returnPressed.connect(self.run_search)
        search = QPushButton("Search")
        search.setObjectName("primary")
        search.clicked.connect(self.run_search)
        query_row.addWidget(self.query, 1)
        query_row.addWidget(search)
        layout.addLayout(query_row)

        filters = QHBoxLayout()
        self.deck_combo = QComboBox()
        self.tag_combo = QComboBox()
        self.sort_combo = QComboBox()
        for key, label in SORT_LABELS.items():
            self.sort_combo.addItem(label, key)
        filters.addWidget(QLabel("Deck"))
        filters.addWidget(self.deck_combo)
        filters.addWidget(QLabel("Tag"))
        filters.addWidget(self.tag_combo)
        filters.addWidget(QLabel("Sort"))
        filters.addWidget(self.sort_combo)
        layout.addLayout(filters)

        dates = QHBoxLayout()
        self.created_from_on = QCheckBox("Added from")
        self.created_from = self._date_edit()
        self.created_to_on = QCheckBox("Added to")
        self.created_to = self._date_edit()
        self.due_from_on = QCheckBox("Due from")
        self.due_from = self._date_edit()
        self.due_to_on = QCheckBox("Due to")
        self.due_to = self._date_edit()
        for box, widget in (
            (self.created_from_on, self.created_from),
            (self.created_to_on, self.created_to),
            (self.due_from_on, self.due_from),
            (self.due_to_on, self.due_to),
        ):
            widget.setEnabled(False)
            box.toggled.connect(widget.setEnabled)
            dates.addWidget(box)
            dates.addWidget(widget)
        layout.addLayout(dates)

        scores = QHBoxLayout()
        self.confidence_min = QSpinBox()
        self.confidence_max = QSpinBox()
        for box in (self.confidence_min, self.confidence_max):
            box.setRange(0, 100)
        self.confidence_max.setValue(100)
        scores.addWidget(QLabel("Confidence"))
        scores.addWidget(self.confidence_min)
        scores.addWidget(QLabel("to"))
        scores.addWidget(self.confidence_max)
        scores.addStretch(1)
        layout.addLayout(scores)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Front", "Back", "Deck", "Tags", "Due", "Confidence"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table, 1)
        self.count_label = QLabel("Search across every card.")
        self.count_label.setObjectName("muted")
        layout.addWidget(self.count_label)
        self._reload_filters()

    def refresh(self) -> None:
        self._reload_filters()
        if self._has_searched:
            self.run_search()

    def focus_query(self) -> None:
        self.query.setFocus()
        self.query.selectAll()

    def run_search(self) -> None:
        self._has_searched = True
        cards = self.db.search_cards(self._filters())
        self.table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            values = [
                preview(card.front),
                preview(card.back),
                card.deck_name,
                ", ".join(card.tags),
                card.due_date,
                str(round(card.confidence)),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(card.front if column == 0 else card.back if column == 1 else value)
                if column == 0:
                    item.setData(Qt.UserRole, card.id)
                self.table.setItem(row, column, item)
        self.count_label.setText(f"{len(cards)} result{'s' if len(cards) != 1 else ''}")

    def _edit(self, index) -> None:
        item = self.table.item(index.row(), 0)
        if item is None:
            return
        card = self.db.get_card(int(item.data(Qt.UserRole)))
        dialog = CardDialog(self.db, card=card, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.changed.emit()

    def _filters(self) -> SearchFilters:
        deck_id = self.deck_combo.currentData()
        tag = self.tag_combo.currentData()
        minimum = self.confidence_min.value()
        maximum = self.confidence_max.value()
        return SearchFilters(
            query=self.query.text(),
            deck_id=None if deck_id in (None, -1) else int(deck_id),
            tag=tag or None,
            created_from=self._date_value(self.created_from_on, self.created_from),
            created_to=self._date_value(self.created_to_on, self.created_to),
            due_from=self._date_value(self.due_from_on, self.due_from),
            due_to=self._date_value(self.due_to_on, self.due_to),
            confidence_min=None if minimum <= 0 else minimum,
            confidence_max=None if maximum >= 100 else maximum,
            sort=self.sort_combo.currentData() or "recently_added",
        )

    def _reload_filters(self) -> None:
        deck_id = self.deck_combo.currentData()
        tag = self.tag_combo.currentData()
        self.deck_combo.blockSignals(True)
        self.tag_combo.blockSignals(True)
        self.deck_combo.clear()
        self.tag_combo.clear()
        self.deck_combo.addItem("Any deck", -1)
        self.tag_combo.addItem("Any tag", "")
        for deck in self.db.list_decks():
            self.deck_combo.addItem(deck.name, deck.id)
        for name in self.db.list_tags():
            self.tag_combo.addItem(name, name)
        deck_index = self.deck_combo.findData(deck_id if deck_id not in (None, "") else -1)
        self.deck_combo.setCurrentIndex(max(0, deck_index))
        tag_index = self.tag_combo.findData(tag or "")
        self.tag_combo.setCurrentIndex(max(0, tag_index))
        self.deck_combo.blockSignals(False)
        self.tag_combo.blockSignals(False)

    def _date_edit(self) -> QDateEdit:
        widget = QDateEdit(QDate.currentDate())
        widget.setCalendarPopup(True)
        widget.setDisplayFormat("yyyy-MM-dd")
        return widget

    @staticmethod
    def _date_value(toggle: QCheckBox, widget: QDateEdit) -> str | None:
        if not toggle.isChecked():
            return None
        return widget.date().toString("yyyy-MM-dd")
