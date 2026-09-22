from pathlib import Path

import pytest

from flashcard_app.parser import extract_text, parse_delimited_lines, parse_file, parse_notes

ROOT = Path(__file__).resolve().parents[1]


def fronts(cards):
    return [card.front for card in cards]


def test_biology_cheat_sheet_detects_patterns():
    cards = parse_file(ROOT / "examples" / "biology.md")
    assert fronts(cards) == [
        "Mitosis",
        "Osmosis",
        "ATP",
        "DNA",
        "What is a ribosome?",
        "Enzyme",
    ]
    mitosis = cards[0]
    assert "two identical daughter cells" in mitosis.back
    assert cards[4].back == "The structure that builds proteins."
    assert cards[5].kind == "table"


def test_qa_answer_keeps_following_lines_until_blank():
    text = "Q: What is ATP?\nA: The energy currency of the cell.\nIt is made in respiration.\n\nQ: Next?\nA: Later."
    cards = parse_notes(text)
    assert cards[0].front == "What is ATP?"
    assert "respiration" in cards[0].back
    assert cards[1].front == "Next?"


def test_ignores_code_fences_and_urls():
    text = "```\nATP: not a card\n```\nhttps://example.com: not a card\nReal term: a real definition\n"
    cards = parse_notes(text)
    assert fronts(cards) == ["Real term"]


def test_delimited_lines_and_dedupe():
    cards = parse_delimited_lines("ATP | energy\natp | duplicate\nOsmosis | water\nno separator")
    assert fronts(cards) == ["ATP", "Osmosis"]


def test_plain_text_definitions():
    cards = parse_notes("Mitosis: Cell division\nOsmosis - Movement of water\n")
    assert fronts(cards) == ["Mitosis", "Osmosis"]
    assert cards[1].back == "Movement of water"


def test_pdf_notes_become_cards(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import QApplication

    _application = QApplication.instance() or QApplication([])
    pdf_path = tmp_path / "notes.pdf"
    writer = QPdfWriter(str(pdf_path))
    writer.setPageSize(QPageSize(QPageSize.A4))
    document = QTextDocument()
    document.setPlainText("Mitosis: Cell division that produces two daughter cells\n")
    document.print_(writer)
    del writer
    cards = parse_file(pdf_path)
    assert cards[0].front == "Mitosis"
    assert "two daughter cells" in cards[0].back
    assert "\t" not in cards[0].back


def test_extract_text_rejects_unknown_types():
    with pytest.raises(ValueError):
        extract_text(Path("notes.docx"))
