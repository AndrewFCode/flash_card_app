from datetime import date

from flashcard_app.sm2 import apply_sm2, format_interval, new_schedule


def test_good_reviews_follow_sm2_intervals():
    today = date(2026, 1, 1)
    state = new_schedule(today)
    first = apply_sm2(state, "good", today)
    assert (first.repetitions, first.interval_days, first.ease_factor) == (1, 1, 2.5)
    assert first.due_date == date(2026, 1, 2)
    assert first.confidence == 15

    second = apply_sm2(first, "good", first.due_date)
    assert (second.repetitions, second.interval_days, second.ease_factor) == (2, 6, 2.5)
    third = apply_sm2(second, "good", second.due_date)
    assert (third.repetitions, third.interval_days) == (3, 15)
    assert third.confidence == 45


def test_again_resets_and_hard_lowers_ease():
    today = date(2026, 1, 1)
    state = new_schedule(today)
    again = apply_sm2(state, "again", today)
    assert again.repetitions == 0
    assert again.interval_days == 1
    assert again.ease_factor < 2.5
    assert again.confidence == 0

    hard = apply_sm2(state, "hard", today)
    assert hard.repetitions == 1
    assert hard.interval_days == 1
    assert hard.ease_factor == 2.36
    assert hard.confidence == 0

    easy = apply_sm2(state, "easy", today)
    assert easy.ease_factor == 2.6
    assert easy.confidence == 25


def test_ease_never_drops_below_floor():
    today = date(2026, 1, 1)
    state = new_schedule(today)
    for _ in range(20):
        state = apply_sm2(state, "again", today)
    assert state.ease_factor >= 1.3
    assert state.confidence == 0


def test_format_interval():
    assert format_interval(0) == "today"
    assert format_interval(1) == "1 day"
    assert format_interval(6) == "6 days"
    assert format_interval(30) == "1 month"
