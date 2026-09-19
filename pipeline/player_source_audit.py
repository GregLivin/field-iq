from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from pipeline.config import RAW_DIR, current_nfl_season

MANUAL_DIR = RAW_DIR.parent / "manual"


def build_player_source_audit(season: int | None = None) -> dict[str, object]:
    """Describe automated player coverage while preserving official manual references.

    Official NFL PDFs/CSVs supplied by the user are reference evidence. They are not
    overwritten or silently merged into nflverse rows because many are full-season
    leaderboard slices rather than game-level records.
    """
    season = season or current_nfl_season()\n    weekly_path = RAW_DIR / "player_weekly.parquet"
    season_path = RAW_DIR / "player_season.parquet"
    players_path = RAW_DIR / "players.parquet"

    report: dict[str, object] = {
        "season": season,
        "automatedProvider": "nflverse",
        "officialReferenceProvider": "NFL official user-provided exports/screenshots",
        "officialReferencePolicy": "retain separately; compare only like-for-like season/category fields",
        "files": {},
    }

    for label, path in (("player_weekly", weekly_path), ("player_season", season_path), ("players", players_path)):
        if path.exists():
            frame = pl.read_parquet(path)
            season_rows = frame.filter(pl.col("season") == season).height if "season" in frame.columns else frame.height
            report["files"][label] = {"path": str(path.relative_to(RAW_DIR.parent.parent)), "rows": frame.height, "seasonRows": season_rows}
        else:
            report["files"][label] = {"path": str(path.relative_to(RAW_DIR.parent.parent)), "missing": True}

    official = sorted(p.name for p in MANUAL_DIR.glob(f"{season}*player*.csv")) if MANUAL_DIR.exists() else []
    # Keep all existing official/manual files visible too, even when older names do not contain "player".
    report["officialReferenceFiles"] = official
    report["status"] = "ready" if season_path.exists() and weekly_path.exists() else "collect_required"
    return report


def write_player_source_audit(season: int | None = None) -> dict[str, object]:
    report = build_player_source_audit(season)
    path = RAW_DIR.parent / "processed" / f"{season}_player_source_audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(write_player_source_audit(), indent=2))
