from datetime import date

from flashcard_app.db import Database
from flashcard_app.exchange import export_anki, export_csv, export_json, load_exchange_file
from flashcard_app.models import SearchFilters


def _populated(tmp_path):
    db = Database(tmp_path / "cards.db")
    deck = db.create_deck("Biology")
    card = db.create_card(deck, "Line one\nLine two", "Answer", ["cell biology"], today=date(2026, 2, 1))
    reviewed = db.apply_review(card.id, "good", today=date(2026, 2, 1))
    return db, reviewed


def test_json_and_csv_roundtrip(tmp_path):
    db, original = _populated(tmp_path)
    cards = db.search_cards(SearchFilters())
    export_json(cards, tmp_path / "cards.json")
    export_csv(cards, tmp_path / "cards.csv")
    db.close()

    restored = Database(tmp_path / "restored.db")
    for path in (tmp_path / "cards.json", tmp_path / "cards.csv"):
        records = load_exchange_file(path)
        restored.import_cards(records, "Fallback")
    loaded = restored.search_cards(SearchFilters(sort="recently_added"))
    assert len(loaded) == 2
    assert {card.front for card in loaded} == {"Line one\nLine two"}
    assert loaded[0].tags == ["cell-biology"]
    assert loaded[0].ease_factor == original.ease_factor
    assert loaded[0].interval_days == original.interval_days
    assert loaded[0].deck_name == "Biology"
    restored.close()


def test_anki_plain_text_roundtrip(tmp_path):
    db, _original = _populated(tmp_path)
    export_anki(db.search_cards(SearchFilters()), tmp_path / "anki.txt")
    records = load_exchange_file(tmp_path / "anki.txt")
    assert records[0].front == "Line one\nLine two"
    assert records[0].deck == "Biology"
    assert records[0].tags == ["cell-biology"]
    db.close()


def test_generic_anki_file_without_deck_column(tmp_path):
    path = tmp_path / "basic.txt"
    path.write_text("#separator:Tab\n#html:false\nFront\tBack\tcell energy\n", encoding="utf-8")
    records = load_exchange_file(path)
    assert records[0].front == "Front"
    assert records[0].back == "Back"
    assert records[0].tags == ["cell", "energy"]
