from datetime import date, timedelta

from flashcard_app.db import Database
from flashcard_app.models import ImportedCard, SearchFilters


def make_db(tmp_path):
    return Database(tmp_path / "cards.db")


def test_crud_tags_search_and_review(tmp_path):
    db = make_db(tmp_path)
    today = date(2026, 4, 1)
    biology = db.create_deck("Biology", "Cells")
    history = db.create_deck("History")
    cell = db.create_card(
        biology,
        "What is mitosis?",
        "Cell division that produces two identical daughter cells",
        ["biology", "cells"],
        "notes.md",
        today=today,
    )
    db.create_card(history, "Who was Cleopatra?", "A Ptolemaic queen of Egypt", ["history"], today=today)

    assert cell.tags == ["biology", "cells"]
    assert cell.due_date == today.isoformat()
    assert [deck.name for deck in db.list_decks(today)] == ["Biology", "History"]

    found = db.search_cards(SearchFilters(query="daughter"))
    assert [card.id for card in found] == [cell.id]
    assert db.search_cards(SearchFilters(query="biology", tag="cells"))[0].id == cell.id
    assert db.search_cards(SearchFilters(deck_id=history, sort="hardest"))[0].deck_name == "History"

    updated = db.apply_review(cell.id, "good", today=today)
    assert updated.review_count == 1
    assert updated.interval_days == 1
    assert updated.due_date == (today + timedelta(days=1)).isoformat()
    assert db.due_cards(biology, today) == []
    assert [card.id for card in db.due_cards(biology, today + timedelta(days=1))] == [cell.id]

    db.update_card(cell.id, front="Define mitosis", back=updated.back, deck_id=biology, tags=["biology"])
    assert db.search_cards(SearchFilters(query="What is mitosis")) == []
    assert db.get_card(cell.id).tags == ["biology"]

    stats = db.dashboard_stats(today)
    assert stats.total_cards == 2
    assert stats.reviews_today == 1
    assert stats.streak_days == 1
    assert stats.activity[today.isoformat()] == 1
    db.close()


def test_bulk_edits_and_duplicates(tmp_path):
    db = make_db(tmp_path)
    alpha = db.create_deck("Alpha")
    beta = db.create_deck("Beta")
    first = db.create_card(alpha, "Mitochondria are the powerhouse of the cell", "Organelle")
    second = db.create_card(beta, "Mitochondria are the powerhouse of a cell", "Same idea", ["old"])
    third = db.create_card(alpha, "Independent fact", "Kept", ["old"])
    groups = db.find_duplicate_groups()
    assert len(groups) == 1
    assert {card.id for card in groups[0]} == {first.id, second.id}

    db.add_tag_to_cards([first.id, third.id], "shared")
    db.rename_tag("old", "shared")
    assert db.get_card(second.id).tags == ["shared"]
    assert db.get_card(third.id).tags == ["shared"]

    moved = db.merge_decks([beta], alpha)
    assert moved == 1
    assert db.get_card(second.id).deck_name == "Alpha"
    assert [deck.name for deck in db.list_decks()] == ["Alpha"]

    db.delete_cards([second.id])
    db.remove_tag_from_cards([third.id], "shared")
    assert db.get_card(third.id).tags == []
    db.delete_deck(alpha)
    assert db.search_cards(SearchFilters()) == []
    db.close()


def test_import_restores_schedule(tmp_path):
    db = make_db(tmp_path)
    saved = db.import_cards(
        [
            ImportedCard(
                front="Term",
                back="Definition",
                deck="Imported",
                tags=["one"],
                ease_factor=2.1,
                interval_days=12,
                repetitions=4,
                due_date="2026-05-01",
                confidence=80,
                review_count=4,
            )
        ],
        "Fallback",
    )
    assert saved == 1
    card = db.search_cards(SearchFilters())[0]
    assert card.deck_name == "Imported"
    assert card.ease_factor == 2.1
    assert card.interval_days == 12
    assert card.confidence == 80
    assert card.repetitions == 4
    stats = db.dashboard_stats(date(2026, 5, 2))
    assert stats.mastered_cards == 1
    assert stats.due_cards == 1
    db.close()


def test_filters_and_sorts(tmp_path):
    db = make_db(tmp_path)
    deck = db.create_deck("Mix")
    easy = db.create_card(
        deck, "Easy card", "Known", today=date(2026, 1, 1), created_at="2026-01-01T10:00:00"
    )
    hard = db.create_card(
        deck, "Hard card", "Unknown", today=date(2026, 1, 2), created_at="2026-01-02T10:00:00"
    )
    db.apply_review(easy.id, "easy", today=date(2026, 1, 1))
    db.apply_review(easy.id, "easy", today=date(2026, 1, 2))
    ranked = db.search_cards(SearchFilters(sort="most_reviewed"))
    assert [card.id for card in ranked] == [easy.id, hard.id]
    hardest = db.search_cards(SearchFilters(sort="hardest"))
    assert hardest[0].id == hard.id
    created = db.search_cards(SearchFilters(created_from="2026-01-02", created_to="2026-01-02"))
    assert [card.id for card in created] == [hard.id]
    confident = db.search_cards(SearchFilters(confidence_min=40))
    assert [card.id for card in confident] == [easy.id]
    db.close()
