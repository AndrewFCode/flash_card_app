"""SM-2 spaced repetition.

Interval steps follow the classic SuperMemo SM-2 rules. Ease is updated after
the interval is chosen, using the previous ease factor. Again / Hard / Good /
Easy map onto SM-2 quality scores 1 / 3 / 4 / 5. Confidence is a separate
0–100 score so the dashboard can show mastery without overloading the ease
factor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MASTERY_THRESHOLD = 80

RATING_QUALITY = {
    "again": 1,
    "hard": 3,
    "good": 4,
    "easy": 5,
}

CONFIDENCE_DELTA = {
    "again": -25,
    "hard": -5,
    "good": 15,
    "easy": 25,
}

RATINGS = ("again", "hard", "good", "easy")


@dataclass(frozen=True)
class ScheduleState:
    ease_factor: float
    interval_days: int
    repetitions: int
    due_date: date
    confidence: float


def new_schedule(today: date) -> ScheduleState:
    return ScheduleState(
        ease_factor=2.5,
        interval_days=0,
        repetitions=0,
        due_date=today,
        confidence=0.0,
    )


def apply_sm2(state: ScheduleState, rating: str, today: date) -> ScheduleState:
    if rating not in RATING_QUALITY:
        raise ValueError(f"Unknown rating: {rating}")
    quality = RATING_QUALITY[rating]
    ease = state.ease_factor
    reps = state.repetitions
    interval = state.interval_days

    if quality < 3:
        reps = 0
        interval = 1
    else:
        if reps <= 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        reps += 1

    ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease < 1.3:
        ease = 1.3
    ease = round(ease, 4)

    confidence = min(100.0, max(0.0, state.confidence + CONFIDENCE_DELTA[rating]))
    due = today + timedelta(days=interval)
    return ScheduleState(ease, interval, reps, due, confidence)


def format_interval(days: int) -> str:
    if days <= 0:
        return "today"
    if days == 1:
        return "1 day"
    if days < 30:
        return f"{days} days"
    if days < 365:
        months = max(1, round(days / 30))
        return "1 month" if months == 1 else f"{months} months"
    years = round(days / 365, 1)
    text = f"{years}".rstrip("0").rstrip(".")
    return f"{text} years" if years != 1 else "1 year"
