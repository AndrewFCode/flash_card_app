"""One pass through a queue of cards."""

from __future__ import annotations

import random
from datetime import date

from flashcard_app.db import Database
from flashcard_app.models import Card, SearchFilters
from flashcard_app.sm2 import RATINGS


class StudySession:
    def __init__(self, db: Database, cards: list[Card], today: date):
        self.db = db
        self.queue = list(cards)
        self.today = today
        self.index = 0
        self.revealed = False
        self.counts = {rating: 0 for rating in RATINGS}

    @property
    def current(self) -> Card | None:
        if self.index >= len(self.queue):
            return None
        return self.queue[self.index]

    @property
    def finished(self) -> bool:
        return self.current is None

    @property
    def position(self) -> tuple[int, int]:
        total = len(self.queue)
        current = min(self.index + 1, total)
        return current, total

    def reveal(self) -> None:
        if self.current is not None:
            self.revealed = True

    def rate(self, rating: str) -> Card:
        card = self.current
        if card is None:
            raise RuntimeError("No card to rate")
        if not self.revealed:
            raise RuntimeError("Reveal the answer before rating")
        updated = self.db.apply_review(card.id, rating, today=self.today)
        self.counts[rating] += 1
        self.index += 1
        self.revealed = False
        return updated

    def end(self) -> None:
        self.index = len(self.queue)
        self.revealed = False


def start_session(
    db: Database,
    *,
    deck_id: int | None,
    due_only: bool,
    shuffle: bool,
    today: date | None = None,
    rng: random.Random | None = None,
) -> StudySession:
    today = today or date.today()
    if due_only:
        cards = db.due_cards(deck_id, today)
    else:
        cards = db.search_cards(SearchFilters(deck_id=deck_id, sort="recently_added"))
    if shuffle:
        (rng or random).shuffle(cards)
    return StudySession(db, cards, today)
