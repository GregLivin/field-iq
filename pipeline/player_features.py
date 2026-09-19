from __future__ import annotations

import numpy as np
import pandas as pd

PLAYER_FEATURE_COLUMNS = [
    "qb_pass_yards_5", "qb_pass_tds_5", "qb_interceptions_5", "qb_completion_pct_5",
    "rush_yards_5", "rush_tds_5", "receiving_yards_5", "receiving_tds_5", "targets_5",
]


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def build_team_player_week_features(player_weekly: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Build leakage-safe team/player form features.

    Each season/week row contains only player production from earlier weeks.
    Player IDs remain in the raw dataset for identity/auditing; models receive
    team aggregates derived from those players.
    """
    if player_weekly.empty:
        return pd.DataFrame(columns=["season", "week", "team", *PLAYER_FEATURE_COLUMNS])

    p = player_weekly.copy()
    required = {"season", "week", "team"}
    if not required.issubset(p.columns):
        return pd.DataFrame(columns=["season", "week", "team", *PLAYER_FEATURE_COLUMNS])

    p["season"] = pd.to_numeric(p["season"], errors="coerce")
    p["week"] = pd.to_numeric(p["week"], errors="coerce")
    p = p.dropna(subset=["season", "week", "team"])
    p["season"] = p["season"].astype(int); p["week"] = p["week"].astype(int)

    pos = p.get("position", pd.Series("", index=p.index)).fillna("").astype(str).str.upper()
    p["_pass_yards"] = _num(p, "passing_yards")
    p["_pass_tds"] = _num(p, "passing_tds")
    p["_ints"] = _num(p, "passing_interceptions")
    p["_completions"] = _num(p, "completions")
    p["_attempts"] = _num(p, "attempts")
    p["_rush_yards"] = _num(p, "rushing_yards")
    p["_rush_tds"] = _num(p, "rushing_tds")
    p["_rec_yards"] = _num(p, "receiving_yards")
    p["_rec_tds"] = _num(p, "receiving_tds")
    p["_targets"] = _num(p, "targets")
    p["_qb"] = pos.eq("QB")

    rows = []
    for (season, team), group in p.groupby(["season", "team"], sort=False):
        weekly = group.groupby("week", as_index=False).agg(
            qb_pass_yards=("_pass_yards", lambda s: float(s[group.loc[s.index, "_qb"]].sum())),
            qb_pass_tds=("_pass_tds", lambda s: float(s[group.loc[s.index, "_qb"]].sum())),
            qb_interceptions=("_ints", lambda s: float(s[group.loc[s.index, "_qb"]].sum())),
            qb_completions=("_completions", lambda s: float(s[group.loc[s.index, "_qb"]].sum())),
            qb_attempts=("_attempts", lambda s: float(s[group.loc[s.index, "_qb"]].sum())),
            rush_yards=("_rush_yards", "sum"), rush_tds=("_rush_tds", "sum"),
            receiving_yards=("_rec_yards", "sum"), receiving_tds=("_rec_tds", "sum"), targets=("_targets", "sum"),
        ).sort_values("week")
        for week in range(1, 23):
            prior = weekly[weekly["week"] < week].tail(window)
            if prior.empty:
                values = {c: np.nan for c in PLAYER_FEATURE_COLUMNS}
            else:
                attempts = prior["qb_attempts"].sum()
                values = {
                    "qb_pass_yards_5": prior["qb_pass_yards"].mean(),
                    "qb_pass_tds_5": prior["qb_pass_tds"].mean(),
                    "qb_interceptions_5": prior["qb_interceptions"].mean(),
                    "qb_completion_pct_5": (prior["qb_completions"].sum() / attempts) if attempts else np.nan,
                    "rush_yards_5": prior["rush_yards"].mean(), "rush_tds_5": prior["rush_tds"].mean(),
                    "receiving_yards_5": prior["receiving_yards"].mean(), "receiving_tds_5": prior["receiving_tds"].mean(),
                    "targets_5": prior["targets"].mean(),
                }
            rows.append({"season": int(season), "week": week, "team": str(team), **values})
    return pd.DataFrame(rows)


def attach_player_form(training: pd.DataFrame, upcoming: pd.DataFrame, player_weekly: pd.DataFrame):
    form = build_team_player_week_features(player_weekly)
    def add(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty: return frame
        result = frame.copy()
        for side in ("home", "away"):
            lookup = form.rename(columns={"team": f"{side}_team", **{c: f"{side}_{c}" for c in PLAYER_FEATURE_COLUMNS}})
            result = result.merge(lookup, on=["season", "week", f"{side}_team"], how="left")
        for c in PLAYER_FEATURE_COLUMNS:
            result[f"player_{c}_diff"] = result[f"home_{c}"] - result[f"away_{c}"]
        return result
    return add(training), add(upcoming), form
