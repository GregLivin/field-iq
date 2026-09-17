from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import nflreadpy as nfl
import polars as pl

from pipeline.config import RAW_DIR, TRAINING_START_SEASON, current_nfl_season, ensure_directories


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path, compression="zstd")


def collect_nflverse(
    season: int | None = None,
    training_start: int = TRAINING_START_SEASON,
) -> dict[str, object]:
    """Download independent nflverse sources used by FieldIQ.

    Historical schedules and team stats train the model. Current player stats,
    rosters, and injuries are retained as separate daily inputs for auditing and
    future player-availability features.
    """
    ensure_directories()
    season = season or current_nfl_season()
    seasons = list(range(training_start, season + 1))

    datasets: dict[str, pl.DataFrame] = {
        "games": nfl.load_schedules(seasons),
        "team_weekly": nfl.load_team_stats(seasons, summary_level="week"),
        "player_weekly": nfl.load_player_stats(season, summary_level="week"),
        "rosters": nfl.load_rosters(season),
        "injuries": nfl.load_injuries(season),
    }

    row_counts: dict[str, int] = {}
    for name, frame in datasets.items():
        _write_parquet(frame, RAW_DIR / f"{name}.parquet")
        row_counts[name] = frame.height

    manifest = {
        "provider": "nflverse",
        "license": "CC BY 4.0; verify each upstream dataset before commercial use",
        "collectedAt": datetime.now(UTC).isoformat(),
        "season": season,
        "trainingSeasons": seasons,
        "rows": row_counts,
    }
    (RAW_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect FieldIQ nflverse datasets")
    parser.add_argument("--season", type=int)
    parser.add_argument("--training-start", type=int, default=TRAINING_START_SEASON)
    args = parser.parse_args()
    print(json.dumps(collect_nflverse(args.season, args.training_start), indent=2))


if __name__ == "__main__":
    main()

