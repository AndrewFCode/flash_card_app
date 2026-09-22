# Flashcards

Offline desktop app for turning notes into flashcards and reviewing them with spaced repetition.

Download and run it from Windows PowerShell. [Python 3.11+](https://www.python.org/downloads/windows/) needs to be installed first; on the installer, enable **Add python.exe to PATH**.

```powershell
git clone https://github.com/AndrewFCode/flash_card_app.git
Set-Location flash_card_app
py -m pip install -r requirements.txt
py -m flashcard_app
```

Cards, decks, and review history live in `$env:USERPROFILE\.flashcard_app\flashcards.db`. To store that folder somewhere else:

```powershell
$env:FLASHCARD_DATA_DIR = "$env:USERPROFILE\Documents\Flashcards"
py -m flashcard_app
```

The app keeps the ten newest database backups in the `backups` folder and writes a new one at most once a day (and whenever you choose **Back up now**).

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

From PowerShell, in the project folder:

```powershell
py -m pip install -r requirements-dev.txt
py -m pytest
```

## Desktop build

PyInstaller can package a local executable. From PowerShell, in the project folder:

```powershell
py -m pip install pyinstaller
py -m PyInstaller --name Flashcards --windowed -m flashcard_app
```
