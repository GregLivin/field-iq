from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from pipeline.config import RAW_DIR, PROCESSED_DIR, ensure_directories


def _ids(frame: pl.DataFrame, column: str = "game_id") -> set[str]:
    if column not in frame.columns:
        return set()
    return set(frame.select(pl.col(column).cast(pl.Utf8).drop_nulls()).to_series().to_list())


def build_data_health() -> dict[str, object]:
    """Audit completed games against FieldIQ's statistical inputs."""
    ensure_directories()
    games = pl.read_parquet(RAW_DIR / "games.parquet")
    team = pl.read_parquet(RAW_DIR / "team_weekly.parquet")
    pbp_path = RAW_DIR / "pbp.parquet"
    pbp = pl.read_parquet(pbp_path) if pbp_path.exists() else pl.DataFrame()

    completed = games.filter(pl.col("home_score").is_not_null() & pl.col("away_score").is_not_null())
    completed_ids = _ids(completed)
    team_ids = _ids(team)
    pbp_ids = _ids(pbp)

    missing_team = sorted(completed_ids - team_ids)
    missing_pbp = sorted(completed_ids - pbp_ids)

    checks = {
        "completedGames": len(completed_ids),
        "gamesWithTeamStats": len(completed_ids & team_ids),
        "gamesWithPlayByPlay": len(completed_ids & pbp_ids),
        "missingTeamStats": missing_team,
        "missingPlayByPlay": missing_pbp,
    }
    expected = max(len(completed_ids) * 2, 1)
    present = checks["gamesWithTeamStats"] + checks["gamesWithPlayByPlay"]
    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "status": "healthy" if not missing_team and not missing_pbp else "incomplete",
        "completenessPct": round(100 * present / expected, 2),
        **checks,
    }

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (PROCESSED_DIR / "data_health.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_data_health(), indent=2))
