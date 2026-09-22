"""Light and dark styles for the desktop window."""

from __future__ import annotations

LIGHT = {
    "bg": "#f3f5f8",
    "panel": "#ffffff",
    "sidebar": "#e7ebf3",
    "text": "#1c1f27",
    "muted": "#5d6678",
    "line": "#d5dbe6",
    "input": "#ffffff",
    "button": "#e4e9f2",
    "button_hover": "#d5dce8",
    "accent": "#2f6fed",
    "accent_text": "#ffffff",
    "again": "#c4514a",
    "hard": "#b86a1d",
    "good": "#2c8a57",
    "easy": "#2f6fed",
    "card_border": "#dfe4ee",
    "warn": "#fff4dc",
    "alt": "#f7f8fb",
    "select": "#d9e6ff",
    "danger": "#c4514a",
    "heat0": "#e6ebf2",
    "heat1": "#c5dafb",
    "heat2": "#7eabf5",
    "heat3": "#3d78e4",
    "heat4": "#1d4eaf",
}

DARK = {
    "bg": "#16181e",
    "panel": "#232833",
    "sidebar": "#1c2028",
    "text": "#e8ebf2",
    "muted": "#a3acbd",
    "line": "#353b49",
    "input": "#191d25",
    "button": "#2d3340",
    "button_hover": "#3c4454",
    "accent": "#7aa6ff",
    "accent_text": "#10141c",
    "again": "#e07a74",
    "hard": "#e0a15c",
    "good": "#63c48f",
    "easy": "#7aa6ff",
    "card_border": "#3a4150",
    "warn": "#3d3422",
    "alt": "#1b1f28",
    "select": "#31466f",
    "danger": "#e07a74",
    "heat0": "#2a303c",
    "heat1": "#1d3d6b",
    "heat2": "#2e5da8",
    "heat3": "#4d86db",
    "heat4": "#9dc0ff",
}


def theme_colors(mode: str) -> dict[str, str]:
    return DARK if mode == "dark" else LIGHT


def stylesheet(mode: str) -> str:
    colors = theme_colors(mode)
    return """
    QMainWindow, QDialog, QWidget#page, QWidget#sidebar, QWidget#dialogBody {
        background: %(bg)s;
        color: %(text)s;
    }
    QWidget { color: %(text)s; font-size: 13px; }
    QLabel { background: transparent; color: %(text)s; }
    QLabel#muted, QLabel#side { color: %(muted)s; }
    QLabel#pageTitle, QLabel#appTitle { font-size: 22px; font-weight: 700; }
    QLabel#statValue { font-size: 28px; font-weight: 700; }
    QLabel#cardFace { font-size: 22px; }
    QWidget#sidebar { background: %(sidebar)s; }
    QFrame#stat, QFrame#flashcard, QFrame#toolbar {
        background: %(panel)s;
        border: 1px solid %(card_border)s;
        border-radius: 12px;
    }
    QFrame#flashcard { border-radius: 18px; }
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit {
        background: %(input)s;
        color: %(text)s;
        border: 1px solid %(line)s;
        border-radius: 8px;
        padding: 6px 8px;
        selection-background-color: %(select)s;
    }
    QComboBox QAbstractItemView {
        background: %(panel)s;
        color: %(text)s;
        selection-background-color: %(select)s;
    }
    QPushButton {
        background: %(button)s;
        color: %(text)s;
        border: 1px solid %(line)s;
        border-radius: 8px;
        padding: 7px 12px;
    }
    QPushButton:hover { background: %(button_hover)s; }
    QPushButton:disabled { color: %(muted)s; }
    QPushButton#primary {
        background: %(accent)s;
        color: %(accent_text)s;
        border: none;
        font-weight: 600;
    }
    QPushButton#nav {
        text-align: left;
        padding: 10px 12px;
        border: none;
        background: transparent;
    }
    QPushButton#nav:checked {
        background: %(accent)s;
        color: %(accent_text)s;
        font-weight: 600;
    }
    QPushButton#again { background: %(again)s; color: white; border: none; font-weight: 600; }
    QPushButton#hard { background: %(hard)s; color: white; border: none; font-weight: 600; }
    QPushButton#good { background: %(good)s; color: white; border: none; font-weight: 600; }
    QPushButton#easy { background: %(easy)s; color: %(accent_text)s; border: none; font-weight: 600; }
    QPushButton#danger { color: %(danger)s; }
    QTableWidget {
        background: %(panel)s;
        alternate-background-color: %(alt)s;
        color: %(text)s;
        gridline-color: %(line)s;
        selection-background-color: %(select)s;
        selection-color: %(text)s;
        border: 1px solid %(line)s;
        border-radius: 8px;
    }
    QHeaderView::section {
        background: %(panel)s;
        color: %(muted)s;
        border: none;
        border-bottom: 1px solid %(line)s;
        padding: 6px;
    }
    QCheckBox { background: transparent; spacing: 6px; }
    QScrollArea { border: none; background: transparent; }
    QMenu { background: %(panel)s; color: %(text)s; border: 1px solid %(line)s; }
    QMenu::item:selected { background: %(select)s; }
    QStatusBar { background: %(sidebar)s; color: %(muted)s; }
    QTabWidget::pane { border: none; }
    QTabBar::tab {
        background: %(button)s;
        color: %(text)s;
        padding: 8px 14px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 4px;
    }
    QTabBar::tab:selected { background: %(accent)s; color: %(accent_text)s; }
    """ % colors


def apply_theme(app, mode: str) -> None:
    app.setStyleSheet(stylesheet(mode))
