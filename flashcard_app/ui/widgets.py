"""Small reusable widgets."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget


class StatTile(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("stat")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self.title = QLabel(title)
        self.title.setObjectName("muted")
        self.value = QLabel("0")
        self.value.setObjectName("statValue")
        layout.addWidget(self.title)
        layout.addWidget(self.value)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class HeatmapWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setSpacing(4)
        self.grid.setContentsMargins(0, 0, 0, 0)

    def set_activity(self, counts: dict[str, int], today: date, colors: dict[str, str]) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        start = today - timedelta(days=today.weekday() + 7 * 11)
        end = today + timedelta(days=(6 - today.weekday()))
        for row, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            label = QLabel(name)
            label.setObjectName("muted")
            label.setFixedWidth(32)
            self.grid.addWidget(label, row, 0)
        cursor = start
        while cursor <= end:
            column = ((cursor - start).days // 7) + 1
            count = counts.get(cursor.isoformat(), 0)
            cell = QLabel()
            cell.setFixedSize(14, 14)
            cell.setToolTip(f"{cursor.isoformat()}: {count} review{'s' if count != 1 else ''}")
            cell.setStyleSheet(
                f"background: {_heat_color(count, colors)}; border-radius: 3px;"
            )
            self.grid.addWidget(cell, cursor.weekday(), column, alignment=Qt.AlignCenter)
            cursor += timedelta(days=1)


def _heat_color(count: int, colors: dict[str, str]) -> str:
    if count <= 0:
        return colors["heat0"]
    if count == 1:
        return colors["heat1"]
    if count <= 3:
        return colors["heat2"]
    if count <= 6:
        return colors["heat3"]
    return colors["heat4"]


def preview(text: str, limit: int = 80) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"
