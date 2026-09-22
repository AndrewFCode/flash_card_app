"""Locations for the local database and backups."""

from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    override = os.environ.get("FLASHCARD_DATA_DIR")
    path = Path(override) if override else Path.home() / ".flashcard_app"
    path.mkdir(parents=True, exist_ok=True)
    (path / "backups").mkdir(exist_ok=True)
    return path


def database_path() -> Path:
    return app_data_dir() / "flashcards.db"
