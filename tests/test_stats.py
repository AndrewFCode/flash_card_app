from datetime import date

from flashcard_app.stats import current_streak


def test_streak_includes_today_and_holds_through_yesterday():
    today = date(2026, 3, 10)
    days = {date(2026, 3, 10), date(2026, 3, 9), date(2026, 3, 8), date(2026, 3, 5)}
    assert current_streak(days, today) == 3
    assert current_streak(days - {today}, today) == 2
    assert current_streak({date(2026, 3, 8)}, today) == 0
