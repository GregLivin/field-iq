from __future__ import annotations

import numpy as np
import pandas as pd

PBP_FEATURE_COLUMNS = [
    "off_epa_per_play",
    "def_epa_per_play",
    "success_rate",
    "yards_per_play",
    "third_down_rate",
    "red_zone_success_rate",
    "explosive_play_rate",
    "qb_epa_per_play",
]


def _mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.mean()) if not values.empty else np.nan


def aggregate_team_game_pbp(pbp: pd.DataFrame) -> pd.DataFrame:
    """Aggregate nflverse play-by-play into one pre-model record per team/game.

    The output is joined to weekly team statistics by game_id/team. Only actual
    offensive scrimmage plays are used for rate statistics where possible.
    """
    if pbp.empty or "game_id" not in pbp.columns or "posteam" not in pbp.columns:
        return pd.DataFrame(columns=["game_id", "team", *PBP_FEATURE_COLUMNS])

    frame = pbp.copy()
    for column in [
        "epa", "yards_gained", "down", "ydstogo", "yardline_100", "first_down",
        "touchdown", "pass", "rush", "qb_dropback", "qb_scramble", "sack",
    ]:
        if column not in frame.columns:
            frame[column] = np.nan

    scrimmage = frame[(frame["pass"].fillna(0) == 1) | (frame["rush"].fillna(0) == 1)].copy()
    scrimmage = scrimmage[scrimmage["posteam"].notna()]
    scrimmage["success"] = (pd.to_numeric(scrimmage["epa"], errors="coerce") > 0).astype(float)
    scrimmage["explosive"] = (
        ((scrimmage["pass"].fillna(0) == 1) & (pd.to_numeric(scrimmage["yards_gained"], errors="coerce") >= 20))
        | ((scrimmage["rush"].fillna(0) == 1) & (pd.to_numeric(scrimmage["yards_gained"], errors="coerce") >= 10))
    ).astype(float)
    scrimmage["third_down"] = (pd.to_numeric(scrimmage["down"], errors="coerce") == 3)
    scrimmage["third_down_success"] = (
        scrimmage["third_down"] & (scrimmage["first_down"].fillna(0) == 1)
    ).astype(float)
    scrimmage["red_zone"] = pd.to_numeric(scrimmage["yardline_100"], errors="coerce") <= 20
    scrimmage["red_zone_success"] = (
        scrimmage["red_zone"] & (scrimmage["touchdown"].fillna(0) == 1)
    ).astype(float)
    scrimmage["qb_play"] = (
        (scrimmage["qb_dropback"].fillna(0) == 1) | (scrimmage["qb_scramble"].fillna(0) == 1)
    )

    rows: list[dict[str, object]] = []
    for (game_id, team), group in scrimmage.groupby(["game_id", "posteam"], dropna=True):
        third = group[group["third_down"]]
        red_zone = group[group["red_zone"]]
        qb = group[group["qb_play"]]
        rows.append({
            "game_id": str(game_id),
            "team": str(team),
            "off_epa_per_play": _mean(group["epa"]),
            "success_rate": _mean(group["success"]),
            "yards_per_play": _mean(group["yards_gained"]),
            "third_down_rate": _mean(third["third_down_success"]) if not third.empty else np.nan,
            "red_zone_success_rate": _mean(red_zone["red_zone_success"]) if not red_zone.empty else np.nan,
            "explosive_play_rate": _mean(group["explosive"]),
            "qb_epa_per_play": _mean(qb["epa"]) if not qb.empty else np.nan,
        })

    offense = pd.DataFrame(rows)
    if offense.empty:
        return pd.DataFrame(columns=["game_id", "team", *PBP_FEATURE_COLUMNS])

    # Defensive EPA/play is opponent offensive EPA/play in the same game.
    defense = offense[["game_id", "team", "off_epa_per_play"]].rename(
        columns={"team": "opponent", "off_epa_per_play": "def_epa_per_play"}
    )
    pairs = offense[["game_id", "team"]].merge(
        offense[["game_id", "team"]].rename(columns={"team": "opponent"}), on="game_id"
    )
    pairs = pairs[pairs["team"] != pairs["opponent"]]
    defense = pairs.merge(defense, on=["game_id", "opponent"], how="left")[[
        "game_id", "team", "def_epa_per_play"
    ]]
    return offense.merge(defense, on=["game_id", "team"], how="left")
