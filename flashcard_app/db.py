"""SQLite storage for decks, cards, tags, and reviews."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from flashcard_app.duplicates import find_duplicate_groups
from flashcard_app.models import Card, DashboardStats, Deck, ImportedCard, SearchFilters
from flashcard_app.sm2 import MASTERY_THRESHOLD, ScheduleState, apply_sm2, new_schedule
from flashcard_app.stats import current_streak
from flashcard_app.tags import normalize_tag, parse_tags

_CARD_FROM = """
SELECT c.id, c.deck_id, d.name AS deck_name, c.front, c.back, c.source_file,
       c.created_at, c.last_reviewed_at, c.review_count, c.ease_factor,
       c.interval_days, c.repetitions, c.due_date, c.confidence,
       GROUP_CONCAT(t.name, char(31)) AS tag_list
FROM cards c
JOIN decks d ON d.id = c.deck_id
LEFT JOIN card_tags ct ON ct.card_id = c.id
LEFT JOIN tags t ON t.id = ct.tag_id
"""

_SORTS = {
    "recently_added": "c.created_at DESC, c.id DESC",
    "most_reviewed": "c.review_count DESC, c.last_reviewed_at DESC, c.id DESC",
    "least_reviewed": "c.review_count ASC, c.created_at DESC, c.id DESC",
    "hardest": "c.confidence ASC, c.ease_factor ASC, c.review_count DESC, c.id ASC",
    "due_date": "c.due_date ASC, c.id ASC",
    "confidence": "c.confidence DESC, c.id ASC",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _coerce_date(value: str | None, fallback: date) -> str:
    if value:
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            pass
    return fallback.isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS decks (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY,
                deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                source_file TEXT,
                created_at TEXT NOT NULL,
                last_reviewed_at TEXT,
                review_count INTEGER NOT NULL DEFAULT 0,
                ease_factor REAL NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 0,
                repetitions INTEGER NOT NULL DEFAULT 0,
                due_date TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                CHECK (confidence >= 0 AND confidence <= 100),
                CHECK (ease_factor >= 1.3)
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE
            );

            CREATE TABLE IF NOT EXISTS card_tags (
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (card_id, tag_id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY,
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                reviewed_at TEXT NOT NULL,
                rating TEXT NOT NULL,
                ease_factor REAL NOT NULL,
                interval_days INTEGER NOT NULL,
                CHECK (rating IN ('again', 'hard', 'good', 'easy'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards(deck_id);
            CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due_date);
            CREATE INDEX IF NOT EXISTS idx_reviews_card ON reviews(card_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(reviewed_at);
            """
        )
        self.conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts USING fts5(front, back, tags)"
        )
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES ('schema_version', '1') "
            "ON CONFLICT(key) DO NOTHING"
        )
        self.conn.commit()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return row["value"]

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def ensure_deck(self, name: str, description: str = "") -> int:
        name = name.strip()
        if not name:
            raise ValueError("Deck name is required")
        existing = self.conn.execute(
            "SELECT id FROM decks WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO decks(name, description, created_at) VALUES (?, ?, ?)",
                (name, description.strip(), _now()),
            )
            return int(cursor.lastrowid)

    def create_deck(self, name: str, description: str = "") -> int:
        name = name.strip()
        if not name:
            raise ValueError("Deck name is required")
        try:
            with self.conn:
                cursor = self.conn.execute(
                    "INSERT INTO decks(name, description, created_at) VALUES (?, ?, ?)",
                    (name, description.strip(), _now()),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("A deck with that name already exists") from exc

    def list_decks(self, today: date | None = None) -> list[Deck]:
        today = today or date.today()
        rows = self.conn.execute(
            """
            SELECT d.id, d.name, d.description, d.created_at,
                   COUNT(c.id) AS card_count,
                   COALESCE(SUM(CASE WHEN c.id IS NOT NULL AND c.due_date <= ? THEN 1 ELSE 0 END), 0) AS due_count,
                   COALESCE(SUM(CASE WHEN c.id IS NOT NULL AND c.confidence >= ? THEN 1 ELSE 0 END), 0) AS mastered_count
            FROM decks d
            LEFT JOIN cards c ON c.deck_id = d.id
            GROUP BY d.id
            ORDER BY d.name COLLATE NOCASE
            """,
            (today.isoformat(), MASTERY_THRESHOLD),
        ).fetchall()
        return [
            Deck(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                card_count=row["card_count"],
                due_count=row["due_count"],
                mastered_count=row["mastered_count"],
            )
            for row in rows
        ]

    def rename_deck(self, deck_id: int, name: str, description: str | None = None) -> None:
        name = name.strip()
        if not name:
            raise ValueError("Deck name is required")
        try:
            with self.conn:
                if description is None:
                    self.conn.execute("UPDATE decks SET name = ? WHERE id = ?", (name, deck_id))
                else:
                    self.conn.execute(
                        "UPDATE decks SET name = ?, description = ? WHERE id = ?",
                        (name, description.strip(), deck_id),
                    )
        except sqlite3.IntegrityError as exc:
            raise ValueError("A deck with that name already exists") from exc

    def delete_deck(self, deck_id: int) -> None:
        with self.conn:
            ids = self.conn.execute("SELECT id FROM cards WHERE deck_id = ?", (deck_id,)).fetchall()
            for row in ids:
                self.conn.execute("DELETE FROM cards_fts WHERE rowid = ?", (row["id"],))
            self.conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
            self._purge_unused_tags()

    def merge_decks(self, source_ids: list[int], target_id: int) -> int:
        sources = [deck_id for deck_id in source_ids if deck_id != target_id]
        if not sources:
            raise ValueError("Choose a different deck to merge into")
        with self.conn:
            moved = 0
            for source_id in sources:
                cursor = self.conn.execute(
                    "UPDATE cards SET deck_id = ? WHERE deck_id = ?",
                    (target_id, source_id),
                )
                moved += cursor.rowcount
                self.conn.execute("DELETE FROM decks WHERE id = ?", (source_id,))
            return moved

    def create_card(
        self,
        deck_id: int,
        front: str,
        back: str,
        tags: list[str] | None = None,
        source_file: str | None = None,
        *,
        today: date | None = None,
        created_at: str | None = None,
        ease_factor: float | None = None,
        interval_days: int | None = None,
        repetitions: int | None = None,
        due_date: str | None = None,
        confidence: float | None = None,
        review_count: int | None = None,
        last_reviewed_at: str | None = None,
    ) -> Card:
        with self.conn:
            card_id = self._insert_card(
                deck_id,
                front,
                back,
                tags or [],
                source_file,
                today=today,
                created_at=created_at,
                ease_factor=ease_factor,
                interval_days=interval_days,
                repetitions=repetitions,
                due_date=due_date,
                confidence=confidence,
                review_count=review_count,
                last_reviewed_at=last_reviewed_at,
            )
        return self.get_card(card_id)

    def import_cards(self, cards: list[ImportedCard], default_deck: str, today: date | None = None) -> int:
        today = today or date.today()
        saved = 0
        with self.conn:
            for card in cards:
                front = card.front.strip()
                back = card.back.strip()
                if not front or not back:
                    continue
                deck_name = (card.deck or default_deck).strip()
                if not deck_name:
                    raise ValueError("A deck name is required")
                deck_id = self._ensure_deck_in_transaction(deck_name)
                self._insert_card(
                    deck_id,
                    front,
                    back,
                    card.tags,
                    card.source_file,
                    today=today,
                    created_at=card.created_at,
                    ease_factor=card.ease_factor,
                    interval_days=card.interval_days,
                    repetitions=card.repetitions,
                    due_date=card.due_date,
                    confidence=card.confidence,
                    review_count=card.review_count,
                    last_reviewed_at=card.last_reviewed_at,
                )
                saved += 1
        return saved

    def update_card(
        self,
        card_id: int,
        *,
        front: str,
        back: str,
        deck_id: int,
        tags: list[str],
    ) -> Card:
        front = front.strip()
        back = back.strip()
        if not front or not back:
            raise ValueError("A card needs both a front and a back")
        with self.conn:
            self.conn.execute(
                "UPDATE cards SET front = ?, back = ?, deck_id = ? WHERE id = ?",
                (front, back, deck_id, card_id),
            )
            self._set_tags(card_id, tags)
            self._reindex(card_id)
        return self.get_card(card_id)

    def delete_cards(self, card_ids: list[int]) -> None:
        if not card_ids:
            return
        with self.conn:
            for card_id in card_ids:
                self.conn.execute("DELETE FROM cards_fts WHERE rowid = ?", (card_id,))
                self.conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            self._purge_unused_tags()

    def move_cards(self, card_ids: list[int], deck_id: int) -> None:
        if not card_ids:
            return
        with self.conn:
            for card_id in card_ids:
                self.conn.execute("UPDATE cards SET deck_id = ? WHERE id = ?", (deck_id, card_id))

    def add_tag_to_cards(self, card_ids: list[int], tag: str) -> None:
        name = normalize_tag(tag)
        if not card_ids:
            return
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))
            tag_id = self.conn.execute(
                "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchone()["id"]
            for card_id in card_ids:
                self.conn.execute(
                    "INSERT OR IGNORE INTO card_tags(card_id, tag_id) VALUES (?, ?)",
                    (card_id, tag_id),
                )
                self._reindex(card_id)

    def remove_tag_from_cards(self, card_ids: list[int], tag: str) -> None:
        name = normalize_tag(tag)
        if not card_ids:
            return
        with self.conn:
            row = self.conn.execute(
                "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchone()
            if row is None:
                return
            for card_id in card_ids:
                self.conn.execute(
                    "DELETE FROM card_tags WHERE card_id = ? AND tag_id = ?",
                    (card_id, row["id"]),
                )
                self._reindex(card_id)
            self._purge_unused_tags()

    def rename_tag(self, old_name: str, new_name: str) -> None:
        old = normalize_tag(old_name)
        new = normalize_tag(new_name)
        if old == new:
            return
        with self.conn:
            old_row = self.conn.execute(
                "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (old,)
            ).fetchone()
            if old_row is None:
                raise ValueError(f"No tag named {old}")
            new_row = self.conn.execute(
                "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (new,)
            ).fetchone()
            if new_row is None:
                self.conn.execute("UPDATE tags SET name = ? WHERE id = ?", (new, old_row["id"]))
                tag_id = old_row["id"]
            else:
                links = self.conn.execute(
                    "SELECT card_id FROM card_tags WHERE tag_id = ?", (old_row["id"],)
                ).fetchall()
                for link in links:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO card_tags(card_id, tag_id) VALUES (?, ?)",
                        (link["card_id"], new_row["id"]),
                    )
                self.conn.execute("DELETE FROM card_tags WHERE tag_id = ?", (old_row["id"],))
                self.conn.execute("DELETE FROM tags WHERE id = ?", (old_row["id"],))
                tag_id = new_row["id"]
            rows = self.conn.execute(
                "SELECT card_id FROM card_tags WHERE tag_id = ?", (tag_id,)
            ).fetchall()
            for row in rows:
                self._reindex(row["card_id"])

    def list_tags(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM tags ORDER BY name COLLATE NOCASE").fetchall()
        return [row["name"] for row in rows]

    def get_card(self, card_id: int) -> Card:
        row = self.conn.execute(f"{_CARD_FROM} WHERE c.id = ? GROUP BY c.id", (card_id,)).fetchone()
        if row is None:
            raise KeyError(card_id)
        return _row_to_card(row)

    def due_cards(self, deck_id: int | None, today: date | None = None) -> list[Card]:
        today = today or date.today()
        return self.search_cards(
            SearchFilters(deck_id=deck_id, due_to=today.isoformat(), sort="due_date")
        )

    def search_cards(self, filters: SearchFilters) -> list[Card]:
        where = ["1 = 1"]
        params: list[object] = []
        if filters.deck_id is not None:
            where.append("c.deck_id = ?")
            params.append(filters.deck_id)
        if filters.tag:
            where.append(
                """EXISTS (
                    SELECT 1 FROM card_tags ct_filter
                    JOIN tags t_filter ON t_filter.id = ct_filter.tag_id
                    WHERE ct_filter.card_id = c.id AND t_filter.name = ? COLLATE NOCASE
                )"""
            )
            params.append(filters.tag.strip())
        if filters.created_from:
            where.append("date(c.created_at) >= ?")
            params.append(filters.created_from)
        if filters.created_to:
            where.append("date(c.created_at) <= ?")
            params.append(filters.created_to)
        if filters.due_from:
            where.append("c.due_date >= ?")
            params.append(filters.due_from)
        if filters.due_to:
            where.append("c.due_date <= ?")
            params.append(filters.due_to)
        if filters.confidence_min is not None:
            where.append("c.confidence >= ?")
            params.append(filters.confidence_min)
        if filters.confidence_max is not None:
            where.append("c.confidence <= ?")
            params.append(filters.confidence_max)
        query = filters.query.strip()
        if query:
            match = _fts_query(query)
            if match is None:
                where.append("0 = 1")
            else:
                where.append("c.id IN (SELECT rowid FROM cards_fts WHERE cards_fts MATCH ?)")
                params.append(match)
        order = _SORTS.get(filters.sort, _SORTS["recently_added"])
        sql = f"{_CARD_FROM} WHERE {' AND '.join(where)} GROUP BY c.id ORDER BY {order}"
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            if not query:
                raise
            where[-1] = "(c.front LIKE ? ESCAPE '\\' OR c.back LIKE ? ESCAPE '\\')"
            like = f"%{_like_escape(query)}%"
            params = params[:-1] + [like, like]
            sql = f"{_CARD_FROM} WHERE {' AND '.join(where)} GROUP BY c.id ORDER BY {order}"
            rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_card(row) for row in rows]

    def find_duplicate_groups(self) -> list[list[Card]]:
        cards = self.search_cards(SearchFilters(sort="recently_added"))
        groups = find_duplicate_groups([(card, card.front) for card in cards])
        return groups

    def apply_review(self, card_id: int, rating: str, today: date | None = None) -> Card:
        today = today or date.today()
        card = self.get_card(card_id)
        state = ScheduleState(
            ease_factor=card.ease_factor,
            interval_days=card.interval_days,
            repetitions=card.repetitions,
            due_date=date.fromisoformat(card.due_date),
            confidence=card.confidence,
        )
        updated = apply_sm2(state, rating, today)
        reviewed_at = datetime.combine(today, datetime.now().time()).isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute(
                """
                UPDATE cards
                SET ease_factor = ?, interval_days = ?, repetitions = ?, due_date = ?,
                    confidence = ?, review_count = review_count + 1, last_reviewed_at = ?
                WHERE id = ?
                """,
                (
                    updated.ease_factor,
                    updated.interval_days,
                    updated.repetitions,
                    updated.due_date.isoformat(),
                    updated.confidence,
                    reviewed_at,
                    card_id,
                ),
            )
            self.conn.execute(
                """
                INSERT INTO reviews(card_id, reviewed_at, rating, ease_factor, interval_days)
                VALUES (?, ?, ?, ?, ?)
                """,
                (card_id, reviewed_at, rating, updated.ease_factor, updated.interval_days),
            )
        return self.get_card(card_id)

    def dashboard_stats(self, today: date | None = None) -> DashboardStats:
        today = today or date.today()
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN due_date <= ? THEN 1 ELSE 0 END), 0) AS due,
                   COALESCE(SUM(CASE WHEN confidence >= ? THEN 1 ELSE 0 END), 0) AS mastered,
                   COALESCE(SUM(CASE WHEN review_count = 0 THEN 1 ELSE 0 END), 0) AS new_count,
                   COALESCE(AVG(confidence), 0) AS average_confidence
            FROM cards
            """,
            (today.isoformat(), MASTERY_THRESHOLD),
        ).fetchone()
        reviews_today = self.conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE date(reviewed_at) = ?",
            (today.isoformat(),),
        ).fetchone()["n"]
        day_rows = self.conn.execute(
            "SELECT DISTINCT date(reviewed_at) AS day FROM reviews"
        ).fetchall()
        review_days = set()
        for day_row in day_rows:
            try:
                review_days.add(date.fromisoformat(day_row["day"]))
            except (TypeError, ValueError):
                continue
        start = today - timedelta(days=today.weekday() + 7 * 11)
        activity_rows = self.conn.execute(
            """
            SELECT date(reviewed_at) AS day, COUNT(*) AS n
            FROM reviews
            WHERE date(reviewed_at) >= ?
            GROUP BY date(reviewed_at)
            """,
            (start.isoformat(),),
        ).fetchall()
        activity = {item["day"]: item["n"] for item in activity_rows}
        return DashboardStats(
            total_cards=row["total"],
            due_cards=row["due"],
            mastered_cards=row["mastered"],
            new_cards=row["new_count"],
            reviews_today=reviews_today,
            average_confidence=float(row["average_confidence"] or 0),
            streak_days=current_streak(review_days, today),
            activity=activity,
            decks=self.list_decks(today),
            as_of=today,
        )

    def _ensure_deck_in_transaction(self, name: str) -> int:
        existing = self.conn.execute(
            "SELECT id FROM decks WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        cursor = self.conn.execute(
            "INSERT INTO decks(name, description, created_at) VALUES (?, '', ?)",
            (name, _now()),
        )
        return int(cursor.lastrowid)

    def _insert_card(
        self,
        deck_id: int,
        front: str,
        back: str,
        tags: list[str],
        source_file: str | None,
        *,
        today: date | None,
        created_at: str | None,
        ease_factor: float | None,
        interval_days: int | None,
        repetitions: int | None,
        due_date: str | None,
        confidence: float | None,
        review_count: int | None,
        last_reviewed_at: str | None,
    ) -> int:
        front = front.strip()
        back = back.strip()
        if not front or not back:
            raise ValueError("A card needs both a front and a back")
        if len(front) > 20000 or len(back) > 20000:
            raise ValueError("Card text is too long")
        today = today or date.today()
        schedule = new_schedule(today)
        ease = schedule.ease_factor if ease_factor is None else max(1.3, float(ease_factor))
        interval = schedule.interval_days if interval_days is None else max(0, int(interval_days))
        reps = schedule.repetitions if repetitions is None else max(0, int(repetitions))
        due = _coerce_date(due_date, schedule.due_date)
        score = schedule.confidence if confidence is None else min(100.0, max(0.0, float(confidence)))
        reviews = 0 if review_count is None else max(0, int(review_count))
        cursor = self.conn.execute(
            """
            INSERT INTO cards(
                deck_id, front, back, source_file, created_at, last_reviewed_at,
                review_count, ease_factor, interval_days, repetitions, due_date, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                deck_id,
                front,
                back,
                source_file,
                created_at or _now(),
                last_reviewed_at,
                reviews,
                ease,
                interval,
                reps,
                due,
                score,
            ),
        )
        card_id = int(cursor.lastrowid)
        self._set_tags(card_id, tags)
        self._reindex(card_id)
        return card_id

    def _set_tags(self, card_id: int, tags: list[str]) -> None:
        self.conn.execute("DELETE FROM card_tags WHERE card_id = ?", (card_id,))
        for name in parse_tags(tags):
            self.conn.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))
            tag_id = self.conn.execute(
                "SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchone()["id"]
            self.conn.execute(
                "INSERT OR IGNORE INTO card_tags(card_id, tag_id) VALUES (?, ?)",
                (card_id, tag_id),
            )
        self._purge_unused_tags()

    def _purge_unused_tags(self) -> None:
        self.conn.execute("DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM card_tags)")

    def _reindex(self, card_id: int) -> None:
        row = self.conn.execute("SELECT front, back FROM cards WHERE id = ?", (card_id,)).fetchone()
        self.conn.execute("DELETE FROM cards_fts WHERE rowid = ?", (card_id,))
        if row is None:
            return
        tag_rows = self.conn.execute(
            """
            SELECT t.name FROM tags t
            JOIN card_tags ct ON ct.tag_id = t.id
            WHERE ct.card_id = ?
            ORDER BY t.name
            """,
            (card_id,),
        ).fetchall()
        self.conn.execute(
            "INSERT INTO cards_fts(rowid, front, back, tags) VALUES (?, ?, ?, ?)",
            (card_id, row["front"], row["back"], " ".join(tag["name"] for tag in tag_rows)),
        )


def _row_to_card(row: sqlite3.Row) -> Card:
    raw_tags = row["tag_list"]
    tags = [] if not raw_tags else [tag for tag in raw_tags.split("\x1f") if tag]
    return Card(
        id=row["id"],
        deck_id=row["deck_id"],
        deck_name=row["deck_name"],
        front=row["front"],
        back=row["back"],
        tags=tags,
        source_file=row["source_file"],
        created_at=row["created_at"],
        last_reviewed_at=row["last_reviewed_at"],
        review_count=row["review_count"],
        ease_factor=row["ease_factor"],
        interval_days=row["interval_days"],
        repetitions=row["repetitions"],
        due_date=row["due_date"],
        confidence=row["confidence"],
    )


def _fts_query(text: str) -> str | None:
    import re

    tokens = re.findall(r"[\w]+", text, flags=re.UNICODE)
    if not tokens:
        return None
    return " AND ".join(f'"{token}"*' for token in tokens)


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
