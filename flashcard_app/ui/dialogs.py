"""Editors for cards, decks, tags, and duplicates."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flashcard_app.db import Database
from flashcard_app.models import Card
from flashcard_app.tags import parse_tags
from flashcard_app.ui.widgets import preview


def report_error(parent: QWidget, exc: Exception) -> None:
    QMessageBox.warning(parent, "Flashcards", str(exc))


class CardDialog(QDialog):
    def __init__(
        self,
        db: Database,
        card: Card | None = None,
        deck_id: int | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db
        self.card = card
        self.setWindowTitle("Edit card" if card else "New card")
        self.resize(520, 460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.deck = QComboBox()
        self.deck.setEditable(True)
        for item in db.list_decks():
            self.deck.addItem(item.name, item.id)
        if self.deck.lineEdit() is not None:
            self.deck.lineEdit().setPlaceholderText("Deck name")
        if card is not None:
            self.deck.setCurrentText(card.deck_name)
        elif deck_id is not None:
            index = self.deck.findData(deck_id)
            if index >= 0:
                self.deck.setCurrentIndex(index)
        self.front = QPlainTextEdit()
        self.back = QPlainTextEdit()
        self.front.setPlaceholderText("Question or term")
        self.back.setPlaceholderText("Answer or definition")
        self.front.setMinimumHeight(80)
        self.back.setMinimumHeight(120)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("comma-separated tags")
        if card is not None:
            self.front.setPlainText(card.front)
            self.back.setPlainText(card.back)
            self.tags.setText(", ".join(card.tags))
        form.addRow("Deck", self.deck)
        form.addRow("Front", self.front)
        form.addRow("Back", self.back)
        form.addRow("Tags", self.tags)
        layout.addLayout(form)
        if card is not None and card.source_file:
            source = QLabel(f"Source: {card.source_file}")
            source.setObjectName("muted")
            layout.addWidget(source)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        front = self.front.toPlainText().strip()
        back = self.back.toPlainText().strip()
        deck_name = self.deck.currentText().strip()
        if not deck_name:
            QMessageBox.warning(self, "Missing deck", "Enter a deck name.")
            return
        if not front or not back:
            QMessageBox.warning(self, "Missing text", "A card needs both a front and a back.")
            return
        try:
            deck_id = self.db.ensure_deck(deck_name)
            tags = parse_tags(self.tags.text())
            if self.card is None:
                self.db.create_card(deck_id, front, back, tags)
            else:
                self.db.update_card(self.card.id, front=front, back=back, deck_id=deck_id, tags=tags)
        except ValueError as exc:
            report_error(self, exc)
            return
        self.accept()


class DeckDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, name: str = "", description: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Deck")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(name)
        self.description = QLineEdit(description)
        form.addRow("Name", self.name)
        form.addRow("Description", self.description)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Missing name", "Enter a deck name.")
            return
        self.accept()


class MergeDialog(QDialog):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Merge decks")
        self.resize(420, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Move every card from the checked decks into the target deck."))
        self.target = QComboBox()
        self.boxes: list[QCheckBox] = []
        for deck in db.list_decks():
            self.target.addItem(f"{deck.name} ({deck.card_count})", deck.id)
            box = QCheckBox(deck.name)
            box.setProperty("deck_id", deck.id)
            self.boxes.append(box)
        layout.addWidget(self.target)
        for box in self.boxes:
            layout.addWidget(box)
        self.target.currentIndexChanged.connect(self._sync)
        self._sync()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync(self) -> None:
        target_id = self.target.currentData()
        for box in self.boxes:
            is_target = box.property("deck_id") == target_id
            if is_target:
                box.setChecked(False)
            box.setEnabled(not is_target)

    def _save(self) -> None:
        if not self.selected_sources():
            QMessageBox.warning(self, "Merge decks", "Check at least one deck to merge.")
            return
        self.accept()

    def target_id(self) -> int:
        return int(self.target.currentData())

    def selected_sources(self) -> list[int]:
        target_id = self.target_id()
        return [
            int(box.property("deck_id"))
            for box in self.boxes
            if box.isChecked() and box.property("deck_id") != target_id
        ]


class RenameTagDialog(QDialog):
    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Rename tag")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.tag = QComboBox()
        for name in db.list_tags():
            self.tag.addItem(name)
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("New tag name")
        form.addRow("Tag", self.tag)
        form.addRow("New name", self.new_name)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        if self.tag.count() == 0:
            QMessageBox.warning(self, "Rename tag", "There are no tags yet.")
            return
        if not self.new_name.text().strip():
            QMessageBox.warning(self, "Rename tag", "Enter a new name.")
            return
        self.accept()


class DuplicatesDialog(QDialog):
    def __init__(self, groups: list[list[Card]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Duplicate cards")
        self.resize(640, 480)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Checked cards will be deleted. The oldest card in each group is kept.")
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("dialogBody")
        inner = QVBoxLayout(body)
        self.boxes: list[QCheckBox] = []
        for group in groups:
            ordered = sorted(group, key=lambda card: (card.created_at, card.id))
            title = QLabel(preview(ordered[0].front, 100))
            title.setWordWrap(True)
            inner.addWidget(title)
            for index, card in enumerate(ordered):
                box = QCheckBox(
                    f"{preview(card.front, 70)}   ·   {card.deck_name}   ·   {card.created_at[:10]}"
                )
                box.setChecked(index != 0)
                box.setProperty("card_id", card.id)
                self.boxes.append(box)
                inner.addWidget(box)
        inner.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Delete checked")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        if not self.selected_ids():
            QMessageBox.warning(self, "Duplicates", "Check the cards you want to delete.")
            return
        self.accept()

    def selected_ids(self) -> list[int]:
        return [int(box.property("card_id")) for box in self.boxes if box.isChecked()]


def confirm(parent: QWidget, title: str, message: str) -> bool:
    answer = QMessageBox.question(parent, title, message, QMessageBox.Yes | QMessageBox.No)
    return answer == QMessageBox.Yes


def shortcut_help() -> str:
    return (
        "Study\n"
        "  Space          Show the answer\n"
        "  1 / 2 / 3 / 4  Again, Hard, Good, Easy\n"
        "\n"
        "Navigation\n"
        "  Ctrl+1         Dashboard\n"
        "  Ctrl+2         Library\n"
        "  Ctrl+3         Study\n"
        "  Ctrl+4         Import\n"
        "  Ctrl+5         Search\n"
        "  Ctrl+F         Search\n"
        "  Ctrl+N         New card\n"
        "  Ctrl+D         Toggle dark / light theme\n"
        "  Ctrl+B         Back up the database\n"
        "  Ctrl+I         Import\n"
        "  Ctrl+Q         Quit\n"
    )
