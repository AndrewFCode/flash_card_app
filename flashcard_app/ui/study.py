"""Flip cards and rate them with SM-2."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flashcard_app.db import Database
from flashcard_app.sm2 import RATINGS, ScheduleState, apply_sm2, format_interval
from flashcard_app.study_session import StudySession, start_session

RATING_LABELS = {
    "again": "Again (1)",
    "hard": "Hard (2)",
    "good": "Good (3)",
    "easy": "Easy (4)",
}


class CardFace(QFrame):
    clicked = Signal()
    reveal_requested = Signal()
    rate_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("flashcard")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        self.side = QLabel("Question")
        self.side.setObjectName("side")
        self.face = QLabel("Start a session to review.")
        self.face.setObjectName("cardFace")
        self.face.setWordWrap(True)
        self.face.setAlignment(Qt.AlignCenter)
        self.face.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.side, alignment=Qt.AlignHCenter)
        layout.addStretch(1)
        layout.addWidget(self.face)
        layout.addStretch(1)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key_Space:
            self.reveal_requested.emit()
            event.accept()
            return
        mapping = {
            Qt.Key_1: "again",
            Qt.Key_2: "hard",
            Qt.Key_3: "good",
            Qt.Key_4: "easy",
        }
        rating = mapping.get(event.key())
        if rating is not None:
            self.rate_requested.emit(rating)
            event.accept()
            return
        super().keyPressEvent(event)


class StudyPage(QWidget):
    changed = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db
        self.session: StudySession | None = None
        self._started = False
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        title = QLabel("Study")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.deck_combo = QComboBox()
        self.due_box = QCheckBox("Due cards only")
        self.due_box.setChecked(True)
        self.shuffle_box = QCheckBox("Shuffle")
        start = QPushButton("Start")
        start.setObjectName("primary")
        start.clicked.connect(self.start)
        stop = QPushButton("End session")
        stop.clicked.connect(self.end)
        controls.addWidget(QLabel("Deck"))
        controls.addWidget(self.deck_combo, 1)
        controls.addWidget(self.due_box)
        controls.addWidget(self.shuffle_box)
        controls.addWidget(start)
        controls.addWidget(stop)
        layout.addLayout(controls)

        self.progress = QLabel("Choose a deck and start.")
        self.progress.setObjectName("muted")
        layout.addWidget(self.progress)

        row = QHBoxLayout()
        row.addStretch(1)
        self.card_face = CardFace()
        self.card_face.clicked.connect(self.flip)
        self.card_face.reveal_requested.connect(self.flip)
        self.card_face.rate_requested.connect(self.rate)
        row.addWidget(self.card_face, 8)
        row.addStretch(1)
        layout.addLayout(row, 1)

        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        self.meta.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.meta)

        self.show_button = QPushButton("Show answer")
        self.show_button.setObjectName("primary")
        self.show_button.clicked.connect(self.flip)
        self.show_button.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.show_button)

        ratings = QHBoxLayout()
        self.rate_buttons: dict[str, QPushButton] = {}
        for rating in RATINGS:
            button = QPushButton(RATING_LABELS[rating])
            button.setObjectName(rating)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _checked=False, value=rating: self.rate(value))
            button.hide()
            self.rate_buttons[rating] = button
            ratings.addWidget(button)
        layout.addLayout(ratings)
        hint = QLabel("Space shows the answer. Then press 1 Again, 2 Hard, 3 Good, or 4 Easy.")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)
        self._reload_decks()
        self._show_welcome()

    def refresh(self) -> None:
        self._reload_decks()

    def begin(self, deck_id: int | None, due_only: bool, shuffle: bool) -> None:
        self._reload_decks()
        index = self.deck_combo.findData(-1 if deck_id is None else deck_id)
        if index >= 0:
            self.deck_combo.setCurrentIndex(index)
        self.due_box.setChecked(due_only)
        self.shuffle_box.setChecked(shuffle)
        self.start()

    def start(self) -> None:
        self._started = True
        self.session = start_session(
            self.db,
            deck_id=self._deck_id(),
            due_only=self.due_box.isChecked(),
            shuffle=self.shuffle_box.isChecked(),
        )
        self._render()
        self.card_face.setFocus()

    def end(self) -> None:
        if self.session is None:
            return
        self.session.end()
        self._render()

    def flip(self) -> None:
        if self.session is None or self.session.finished or self.session.revealed:
            return
        self.session.reveal()
        self._render()
        self.card_face.setFocus()

    def rate(self, rating: str) -> None:
        if self.session is None or self.session.finished or not self.session.revealed:
            return
        try:
            self.session.rate(rating)
        except KeyError:
            self.session.index += 1
            self.session.revealed = False
        else:
            self.changed.emit()
        self._render()
        self.card_face.setFocus()

    def _render(self) -> None:
        session = self.session
        if session is None or (session.finished and not session.queue):
            if self._started:
                self._show_idle()
            else:
                self._show_welcome()
            return
        card = session.current
        if card is None:
            counts = session.counts
            self.progress.setText("Session complete")
            self.card_face.side.setText("Done")
            self.card_face.face.setText("Nothing left in this session.")
            self.meta.setText(
                f"Again {counts['again']} · Hard {counts['hard']} · "
                f"Good {counts['good']} · Easy {counts['easy']}"
            )
            self.show_button.hide()
            for button in self.rate_buttons.values():
                button.hide()
            return
        current, total = session.position
        self.progress.setText(f"Card {current} of {total}")
        tags = ", ".join(card.tags) if card.tags else "No tags"
        self.meta.setText(
            f"{card.deck_name} · {tags} · Due {card.due_date} · Confidence {round(card.confidence)}"
        )
        if session.revealed:
            self.card_face.side.setText("Answer")
            self.card_face.face.setText(card.back)
            self.show_button.hide()
            state = ScheduleState(
                ease_factor=card.ease_factor,
                interval_days=card.interval_days,
                repetitions=card.repetitions,
                due_date=session.today,
                confidence=card.confidence,
            )
            for rating, button in self.rate_buttons.items():
                upcoming = apply_sm2(state, rating, session.today)
                button.setText(f"{RATING_LABELS[rating]} · {format_interval(upcoming.interval_days)}")
                button.show()
        else:
            self.card_face.side.setText("Question")
            self.card_face.face.setText(card.front)
            self.show_button.show()
            for button in self.rate_buttons.values():
                button.hide()

    def _show_welcome(self) -> None:
        self.progress.setText("Choose a deck and start.")
        self.card_face.side.setText("Study")
        self.card_face.face.setText("Due cards appear here. Space reveals the answer.")
        self.meta.setText("")
        self.show_button.hide()
        for button in self.rate_buttons.values():
            button.hide()

    def _show_idle(self) -> None:
        due_only = self.due_box.isChecked()
        self.progress.setText("No cards to study." if due_only else "This deck has no cards.")
        self.card_face.side.setText("Study")
        self.card_face.face.setText(
            "No cards are waiting." if due_only else "Add a card, then start a session."
        )
        self.meta.setText("")
        self.show_button.hide()
        for button in self.rate_buttons.values():
            button.hide()

    def _deck_id(self) -> int | None:
        value = self.deck_combo.currentData()
        if value in (None, -1):
            return None
        return int(value)

    def _reload_decks(self) -> None:
        current = self._deck_id()
        self.deck_combo.blockSignals(True)
        self.deck_combo.clear()
        self.deck_combo.addItem("All decks", -1)
        for deck in self.db.list_decks():
            self.deck_combo.addItem(deck.name, deck.id)
        index = self.deck_combo.findData(-1 if current is None else current)
        self.deck_combo.setCurrentIndex(max(0, index))
        self.deck_combo.blockSignals(False)
