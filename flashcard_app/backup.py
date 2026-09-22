"""Scheduled copies of the SQLite database."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flashcard_app.db import Database

BACKUP_KEEP = 10


def backup_database(db: Database, keep: int = BACKUP_KEEP) -> Path:
    backup_dir = db.path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = backup_dir / f"flashcards-{stamp}.db"
    target = sqlite3.connect(dest)
    try:
        db.conn.backup(target)
    finally:
        target.close()
    prune_backups(backup_dir, keep)
    return dest


def prune_backups(backup_dir: Path, keep: int = BACKUP_KEEP) -> None:
    files = sorted(backup_dir.glob("flashcards-*.db"), key=lambda path: path.name)
    extra = max(0, len(files) - keep)
    for path in files[:extra]:
        path.unlink(missing_ok=True)


def maybe_auto_backup(db: Database) -> Path | None:
    try:
        hours = float(db.get_setting("backup_interval_hours", "24"))
    except ValueError:
        hours = 24
    if hours <= 0:
        return None
    last = db.get_setting("last_backup_at")
    if last:
        try:
            previous = datetime.fromisoformat(last)
        except ValueError:
            previous = None
        if previous is not None and datetime.now() - previous < timedelta(hours=hours):
            return None
    path = backup_database(db)
    db.set_setting("last_backup_at", datetime.now().isoformat(timespec="seconds"))
    return path
