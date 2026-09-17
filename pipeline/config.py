from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = ROOT / "models"


def current_nfl_season(today: date | None = None) -> int:
    """Return the NFL season year (the new season begins in late summer)."""
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


TRAINING_START_SEASON = 2019
ROLLING_WINDOW = 5
RANDOM_STATE = 42


def ensure_directories() -> None:
    for directory in (RAW_DIR, PROCESSED_DIR, MODEL_DIR):
        directory.mkdir(parents=True, exist_ok=True)

