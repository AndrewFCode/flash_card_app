"""Progress overview."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashcard_app.db import Database
from flashcard_app.ui.theme import theme_colors
from flashcard_app.ui.widgets import HeatmapWidget, StatTile


class DashboardPage(QWidget):
    study_due = Signal(int)
    browse_deck = Signal(int)

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.summary = QLabel("No cards yet. Create one in the library or import notes.")
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        tiles = QHBoxLayout()
        self.due_tile = StatTile("Due")
        self.mastered_tile = StatTile("Mastered")
        self.streak_tile = StatTile("Streak")
        self.today_tile = StatTile("Reviews today")
        for tile in (self.due_tile, self.mastered_tile, self.streak_tile, self.today_tile):
            tiles.addWidget(tile)
        layout.addLayout(tiles)

        heat_title = QLabel("Last 12 weeks")
        heat_title.setObjectName("muted")
        layout.addWidget(heat_title)
        self.heatmap = HeatmapWidget()
        layout.addWidget(self.heatmap)

        self.backup_label = QLabel("")
        self.backup_label.setObjectName("muted")
        layout.addWidget(self.backup_label)

        layout.addWidget(QLabel("Decks"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Deck", "Cards", "Due", "Mastered"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        study = QPushButton("Study due in selected deck")
        study.setObjectName("primary")
        study.clicked.connect(self._study_selected)
        browse = QPushButton("Browse selected deck")
        browse.clicked.connect(self._browse_selected)
        all_due = QPushButton("Study all due")
        all_due.clicked.connect(lambda: self.study_due.emit(-1))
        actions.addWidget(study)
        actions.addWidget(browse)
        actions.addWidget(all_due)
        actions.addStretch(1)
        layout.addLayout(actions)

    def refresh(self) -> None:
        stats = self.db.dashboard_stats()
        self.due_tile.set_value(str(stats.due_cards))
        self.mastered_tile.set_value(str(stats.mastered_cards))
        self.streak_tile.set_value(f"{stats.streak_days} day{'s' if stats.streak_days != 1 else ''}")
        self.today_tile.set_value(str(stats.reviews_today))
        if stats.total_cards == 0:
            self.summary.setText("No cards yet. Create one in the library or import notes.")
        else:
            self.summary.setText(
                f"{stats.total_cards} cards · {stats.new_cards} new · "
                f"average confidence {round(stats.average_confidence)}"
            )
        mode = self.db.get_setting("theme", "light") or "light"
        self.heatmap.set_activity(stats.activity, stats.as_of, theme_colors(mode))
        last_backup = self.db.get_setting("last_backup_at")
        self.backup_label.setText(
            f"Last backup: {last_backup}" if last_backup else "No backup yet. One is created on a schedule."
        )
        self.table.setRowCount(len(stats.decks))
        for row, deck in enumerate(stats.decks):
            values = [deck.name, str(deck.card_count), str(deck.due_count), str(deck.mastered_count)]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, deck.id)
                self.table.setItem(row, column, item)

    def _selected_deck_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return int(item.data(Qt.UserRole))

    def _study_selected(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is not None:
            self.study_due.emit(deck_id)

    def _browse_selected(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is not None:
            self.browse_deck.emit(deck_id)
