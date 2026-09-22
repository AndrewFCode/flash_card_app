"""Progress calculations that do not need the database."""

from __future__ import annotations

from datetime import date, timedelta


def current_streak(review_days: set[date], today: date) -> int:
    """Consecutive study days ending today, or yesterday if today is still open."""
    if today in review_days:
        cursor = today
    elif (today - timedelta(days=1)) in review_days:
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in review_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
