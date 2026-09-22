from datetime import datetime, timedelta

from flashcard_app.backup import backup_database, maybe_auto_backup, prune_backups
from flashcard_app.db import Database
from flashcard_app.models import SearchFilters


def test_backup_copies_cards_and_prunes(tmp_path):
    db = Database(tmp_path / "cards.db")
    deck = db.create_deck("Biology")
    db.create_card(deck, "ATP", "Energy")
    folder = tmp_path / "backups"
    folder.mkdir()
    for name in ("flashcards-1.db", "flashcards-2.db"):
        (folder / name).write_bytes(b"old")
    first = backup_database(db, keep=2)
    second = backup_database(db, keep=2)
    names = sorted(path.name for path in folder.glob("flashcards-*.db"))
    assert names == sorted([first.name, second.name])
    copy = Database(second)
    assert copy.search_cards(SearchFilters())[0].front == "ATP"
    copy.close()
    db.close()


def test_prune_keeps_newest_names(tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    for name in ("flashcards-1.db", "flashcards-2.db", "flashcards-3.db"):
        (folder / name).write_text("x", encoding="utf-8")
    prune_backups(folder, keep=2)
    assert sorted(path.name for path in folder.glob("flashcards-*.db")) == [
        "flashcards-2.db",
        "flashcards-3.db",
    ]


def test_auto_backup_respects_interval(tmp_path):
    db = Database(tmp_path / "cards.db")
    db.set_setting("backup_interval_hours", "0")
    assert maybe_auto_backup(db) is None
    db.set_setting("backup_interval_hours", "24")
    path = maybe_auto_backup(db)
    assert path is not None and path.exists()
    assert maybe_auto_backup(db) is None
    db.set_setting("last_backup_at", (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds"))
    assert maybe_auto_backup(db) is not None
    db.close()
