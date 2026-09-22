"""CSV, JSON, and Anki plain-text import and export."""

from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime
from pathlib import Path

from flashcard_app.models import Card, ImportedCard
from flashcard_app.tags import parse_tags

CSV_FIELDS = [
    "front",
    "back",
    "deck",
    "tags",
    "source_file",
    "created_at",
    "last_reviewed_at",
    "review_count",
    "ease_factor",
    "interval_days",
    "repetitions",
    "due_date",
    "confidence",
]


def export_json(cards: list[Card], path: Path) -> None:
    decks: dict[str, dict] = {}
    for card in cards:
        deck = decks.setdefault(card.deck_name, {"name": card.deck_name, "cards": []})
        deck["cards"].append(_card_dict(card))
    payload = {
        "version": 1,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "decks": list(decks.values()),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_csv(cards: list[Card], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for card in cards:
            writer.writerow(_card_dict(card))


def export_anki(cards: list[Card], path: Path) -> None:
    lines = [
        "#separator:Tab",
        "#html:true",
        "#deck column:3",
        "#tags column:4",
    ]
    for card in cards:
        fields = [
            _anki_field(card.front),
            _anki_field(card.back),
            _anki_field(card.deck_name),
            " ".join(card.tags),
        ]
        lines.append("\t".join(fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_exchange_file(path: Path) -> list[ImportedCard]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".csv":
        return _load_csv(path)
    if suffix == ".txt":
        return _load_anki(path)
    raise ValueError(f"Unsupported deck file: {suffix or path.name}")


def _card_dict(card: Card) -> dict:
    return {
        "front": card.front,
        "back": card.back,
        "deck": card.deck_name,
        "tags": "|".join(card.tags),
        "source_file": card.source_file,
        "created_at": card.created_at,
        "last_reviewed_at": card.last_reviewed_at,
        "review_count": card.review_count,
        "ease_factor": card.ease_factor,
        "interval_days": card.interval_days,
        "repetitions": card.repetitions,
        "due_date": card.due_date,
        "confidence": card.confidence,
    }


def _anki_field(text: str) -> str:
    return html.escape(text).replace("\t", " ").replace("\n", "<br>")


def _load_json(path: Path) -> list[ImportedCard]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: list[ImportedCard] = []
    if isinstance(payload, list):
        records.extend(_card_from_mapping(item, None) for item in payload)
        return [record for record in records if record is not None]
    if not isinstance(payload, dict):
        raise ValueError("JSON file must be a list of cards or an object with decks")
    if "decks" in payload:
        for deck in payload["decks"]:
            deck_name = deck.get("name") if isinstance(deck, dict) else None
            for item in deck.get("cards", []) if isinstance(deck, dict) else []:
                record = _card_from_mapping(item, deck_name)
                if record is not None:
                    records.append(record)
        return records
    for item in payload.get("cards", []):
        record = _card_from_mapping(item, payload.get("deck"))
        if record is not None:
            records.append(record)
    return records


def _load_csv(path: Path) -> list[ImportedCard]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return []
        fields = [name.strip().lower() for name in reader.fieldnames]
        if "front" not in fields or "back" not in fields:
            raise ValueError("CSV needs front and back columns")
        records: list[ImportedCard] = []
        for row in reader:
            lowered = {key.strip().lower(): value for key, value in row.items() if key}
            record = _card_from_mapping(lowered, None)
            if record is not None:
                records.append(record)
        return records


def _load_anki(path: Path) -> list[ImportedCard]:
    separator = "\t"
    html_mode = False
    deck_column = None
    tags_column = None
    records: list[ImportedCard] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip("\n")
        if not line.strip() or line.startswith("#"):
            directive = line.strip().lower()
            if directive.startswith("#separator:"):
                kind = directive.split(":", 1)[1].strip()
                separator = {"tab": "\t", "comma": ",", "semicolon": ";", "pipe": "|"}.get(kind, "\t")
            elif directive.startswith("#html:"):
                html_mode = directive.split(":", 1)[1].strip() == "true"
            elif directive.startswith("#deck column:"):
                deck_column = _column_index(directive)
            elif directive.startswith("#tags column:"):
                tags_column = _column_index(directive)
            continue
        parts = line.split(separator)
        if len(parts) < 2:
            continue
        front = _clean_anki(parts[0], html_mode)
        back = _clean_anki(parts[1], html_mode)
        deck = None
        tags: list[str] = []
        if deck_column and len(parts) >= deck_column:
            deck = _clean_anki(parts[deck_column - 1], html_mode) or None
        if tags_column and len(parts) >= tags_column:
            tags = parse_tags(parts[tags_column - 1].replace(" ", ","))
        elif len(parts) >= 3 and deck_column is None:
            tags = parse_tags(parts[2].replace(" ", ","))
        if front and back:
            records.append(ImportedCard(front=front, back=back, deck=deck, tags=tags))
    return records


def _column_index(directive: str) -> int | None:
    match = re.search(r"(\d+)", directive)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _clean_anki(text: str, html_mode: bool) -> str:
    if html_mode:
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
    return text.strip()


def _card_from_mapping(item: object, deck_name: str | None) -> ImportedCard | None:
    if not isinstance(item, dict):
        return None
    front = str(item.get("front") or item.get("question") or "").strip()
    back = str(item.get("back") or item.get("answer") or "").strip()
    if not front or not back:
        return None
    tags_value = item.get("tags", "")
    if isinstance(tags_value, list):
        tags = parse_tags(tags_value)
    else:
        tags = parse_tags(str(tags_value))
    deck = item.get("deck") or item.get("deck_name") or deck_name
    return ImportedCard(
        front=front,
        back=back,
        deck=str(deck).strip() if deck else None,
        tags=tags,
        source_file=_optional_str(item.get("source_file")),
        ease_factor=_optional_float(item.get("ease_factor")),
        interval_days=_optional_int(item.get("interval_days")),
        repetitions=_optional_int(item.get("repetitions")),
        due_date=_optional_str(item.get("due_date")),
        confidence=_optional_float(item.get("confidence")),
        review_count=_optional_int(item.get("review_count")),
        created_at=_optional_str(item.get("created_at")),
        last_reviewed_at=_optional_str(item.get("last_reviewed_at")),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
