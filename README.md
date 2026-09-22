# Flashcards

Offline desktop app for turning notes into flashcards and reviewing them with spaced repetition.

```bash
pip install -r requirements.txt
python -m flashcard_app
```

Cards, decks, and review history live in `~/.flashcard_app/flashcards.db`. Set `FLASHCARD_DATA_DIR` to store that folder somewhere else. The app keeps the ten newest database backups in the `backups` folder and writes a new one at most once a day (and whenever you choose **Back up now**).

## What it does

- Create and edit cards by hand, or import plain text, Markdown, and PDF notes. The importer looks for `Term: Definition` lines, `Q:` / `A:` pairs, Markdown headings, bullet definitions, and two-column tables. Paste mode can also split lines on `|`.
- Preview every generated card, edit it, and skip near-duplicate fronts before saving.
- Study with a flip card. Space reveals the answer; 1–4 rate it Again, Hard, Good, or Easy. Scheduling is SM-2. Choose all cards or only cards that are due, and optionally shuffle.
- Search fronts, backs, and tags. Filter by deck, tag, date added, due date, and confidence, and sort by review count, difficulty, or date added.
- Organize cards with multiple tags, deck merge, tag rename, bulk move, and duplicate cleanup.
- Export and import JSON, CSV, or Anki plain text (tab-separated, with deck and tag columns).
- Dashboard for due cards, mastered cards (confidence 80 or higher), the current streak, and a 12-week review heatmap.
- Light and dark themes. Keyboard shortcuts are listed under Help.

Everything stays on this computer. There is no account and no network call.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Desktop build

PyInstaller can package a local executable:

```bash
pyinstaller --name Flashcards --windowed -m flashcard_app
```
