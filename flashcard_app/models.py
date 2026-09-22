"""Data objects passed between storage and the interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Card:
    id: int
    deck_id: int
    deck_name: str
    front: str
    back: str
    tags: list[str]
    source_file: str | None
    created_at: str
    last_reviewed_at: str | None
    review_count: int
    ease_factor: float
    interval_days: int
    repetitions: int
    due_date: str
    confidence: float


@dataclass
class Deck:
    id: int
    name: str
    description: str
    created_at: str
    card_count: int = 0
    due_count: int = 0
    mastered_count: int = 0


@dataclass
class DashboardStats:
    total_cards: int
    due_cards: int
    mastered_cards: int
    new_cards: int
    reviews_today: int
    average_confidence: float
    streak_days: int
    activity: dict[str, int]
    decks: list[Deck]
    as_of: date


@dataclass
class SearchFilters:
    query: str = ""
    deck_id: int | None = None
    tag: str | None = None
    created_from: str | None = None
    created_to: str | None = None
    due_from: str | None = None
    due_to: str | None = None
    confidence_min: float | None = None
    confidence_max: float | None = None
    sort: str = "recently_added"


@dataclass
class ImportedCard:
    front: str
    back: str
    deck: str | None = None
    tags: list[str] = field(default_factory=list)
    source_file: str | None = None
    ease_factor: float | None = None
    interval_days: int | None = None
    repetitions: int | None = None
    due_date: str | None = None
    confidence: float | None = None
    review_count: int | None = None
    created_at: str | None = None
    last_reviewed_at: str | None = None


SORT_LABELS = {
    "recently_added": "Recently added",
    "most_reviewed": "Most reviewed",
    "least_reviewed": "Least reviewed",
    "hardest": "Hardest",
    "due_date": "Due date",
    "confidence": "Confidence",
}
