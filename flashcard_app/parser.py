"""Turn notes and cheat sheets into question/answer pairs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from flashcard_app.duplicates import normalize_front

NOTE_SUFFIXES = {".txt", ".md", ".markdown", ".pdf"}


@dataclass(frozen=True)
class ParsedCard:
    front: str
    back: str
    kind: str


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        parts = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(parts)
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Unsupported notes file: {suffix or path.name}")


def parse_file(path: Path) -> list[ParsedCard]:
    return parse_notes(extract_text(path))


def parse_delimited_lines(text: str, separator: str = "|") -> list[ParsedCard]:
    cards: list[ParsedCard] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if separator not in line:
            continue
        front, back = line.split(separator, 1)
        front, back = clean_inline(front), back.strip()
        if front and back:
            cards.append(ParsedCard(front, back, "manual"))
    return _dedupe(cards)


def parse_notes(text: str) -> list[ParsedCard]:
    text = text.replace("\u00a0", " ").replace("\t", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    cards: list[ParsedCard] = []
    index = 0
    in_code = False
    pending_header: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal pending_header, body
        if pending_header is None:
            body = []
            return
        prose_lines: list[str] = []
        for line in body:
            table_card = parse_table_line(line)
            if table_card is not None:
                cards.append(table_card)
                continue
            definition = parse_definition_line(line)
            if definition is not None:
                cards.append(definition)
                continue
            prose_lines.append(line)
        prose = re.sub(r"\n{3,}", "\n\n", "\n".join(prose_lines)).strip()
        if prose:
            cards.append(ParsedCard(clean_inline(pending_header), prose, "heading"))
        pending_header = None
        body = []

    while index < len(lines):
        line = lines[index]
        if line.strip().startswith("```"):
            in_code = not in_code
            index += 1
            continue
        if in_code:
            index += 1
            continue
        if re.match(r"(?i)^Q:\s*\S", line.strip()):
            flush()
            question = clean_inline(re.sub(r"(?i)^Q:\s*", "", line.strip()))
            index += 1
            answer_lines: list[str] = []
            if index < len(lines) and re.match(r"(?i)^A:\s*", lines[index].strip()):
                answer_lines.append(re.sub(r"(?i)^A:\s*", "", lines[index].strip()).strip())
                index += 1
                while index < len(lines) and not _ends_answer(lines[index]):
                    answer_lines.append(lines[index])
                    index += 1
            answer = "\n".join(answer_lines).strip()
            if question and answer:
                cards.append(ParsedCard(question, answer, "qa"))
            continue
        header = re.match(r"^(#{1,3})\s+(.+?)\s*#*$", line)
        if header:
            flush()
            pending_header = header.group(2).strip()
            index += 1
            continue
        if pending_header is None:
            table_card = parse_table_line(line)
            if table_card is not None:
                cards.append(table_card)
            else:
                definition = parse_definition_line(line)
                if definition is not None:
                    cards.append(definition)
            index += 1
            continue
        body.append(line)
        index += 1
    flush()
    return _dedupe(cards)


def parse_definition_line(line: str) -> ParsedCard | None:
    raw = line.strip()
    if not raw or raw.startswith("```") or raw.startswith("|"):
        return None
    if re.fullmatch(r"[-*_]{3,}", raw):
        return None
    raw = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", raw)
    raw = raw.replace("**", "").replace("__", "")
    left = right = ""
    for separator in (" :: ", " — ", " – ", " - ", ": "):
        if separator in raw:
            left, right = raw.split(separator, 1)
            break
    else:
        match = re.match(r"^([^:]{1,120}):\s*(\S.+)$", raw)
        if not match:
            return None
        left, right = match.group(1), match.group(2)
    left = clean_inline(left).strip(" *-")
    right = right.strip()
    if not left or not right:
        return None
    if len(left) > 120 or len(left.split()) > 14:
        return None
    if not re.search(r"[A-Za-z]", left):
        return None
    if left.lower().startswith("http"):
        return None
    return ParsedCard(left, right, "definition")


def parse_table_line(line: str) -> ParsedCard | None:
    stripped = line.strip()
    if not stripped.startswith("|") or "|" not in stripped[1:]:
        return None
    cells = [clean_inline(cell) for cell in stripped.strip("|").split("|")]
    cells = [cell.strip() for cell in cells]
    if len(cells) < 2 or not cells[0] or not cells[1]:
        return None
    if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
        return None
    if cells[0].lower() in {"term", "front", "question"} and cells[1].lower() in {
        "definition",
        "back",
        "answer",
    }:
        return None
    if re.fullmatch(r"[-–—: ]+", cells[0]):
        return None
    return ParsedCard(cells[0], cells[1], "table")


def clean_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _ends_answer(line: str) -> bool:
    stripped = line.strip()
    if stripped == "":
        return True
    if stripped.startswith("|") or stripped.startswith("```"):
        return True
    return bool(re.match(r"(?i)^Q:\s*\S", stripped) or re.match(r"^#{1,3}\s+\S", stripped))


def _dedupe(cards: list[ParsedCard]) -> list[ParsedCard]:
    seen: set[str] = set()
    unique: list[ParsedCard] = []
    for card in cards:
        key = normalize_front(card.front)
        if not key or not card.back.strip() or key in seen:
            continue
        seen.add(key)
        unique.append(card)
    return unique
