from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pipeline.config import ROLLING_WINDOW

STAT_COLUMNS = [
    "passing_epa",
    "rushing_epa",
    "passing_yards",
    "rushing_yards",
    "passing_interceptions",
    "fumbles_lost_total",
    "def_sacks",
]

FEATURE_COLUMNS = [
    "elo_diff",
    "rest_diff",
    "win_rate_5_diff",
    "point_margin_5_diff",
    "total_epa_5_diff",
    "yards_5_diff",
    "turnovers_5_diff",
    "def_sacks_5_diff",
    "temperature_f",
    "wind_mph",
    "outdoors",
]


@dataclass
class TeamState:
    elo: float = 1500.0
    games: deque[dict[str, float]] = field(
        default_factory=lambda: deque(maxlen=ROLLING_WINDOW)
    )

    def average(self, key: str, default: float = 0.0) -> float:
        values = [game[key] for game in self.games if not np.isnan(game.get(key, np.nan))]
        return float(np.mean(values)) if values else default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _team_game(stats: dict[tuple[str, str], dict[str, Any]], game_id: str, team: str) -> dict[str, Any]:
    return stats.get((game_id, team), {})


def _feature_row(
    game: Any,
    home: TeamState,
    away: TeamState,
) -> dict[str, float]:
    temperature = _number(getattr(game, "temp", np.nan), 65.0)
    wind = _number(getattr(game, "wind", np.nan), 0.0)
    roof = str(getattr(game, "roof", "") or "").lower()
    return {
        "elo_diff": home.elo - away.elo,
        "rest_diff": _number(getattr(game, "home_rest", 7), 7) - _number(getattr(game, "away_rest", 7), 7),
        "win_rate_5_diff": home.average("win", 0.5) - away.average("win", 0.5),
        "point_margin_5_diff": home.average("point_margin") - away.average("point_margin"),
        "total_epa_5_diff": home.average("total_epa") - away.average("total_epa"),
        "yards_5_diff": home.average("yards") - away.average("yards"),
        "turnovers_5_diff": home.average("turnovers") - away.average("turnovers"),
        "def_sacks_5_diff": home.average("def_sacks") - away.average("def_sacks"),
        "temperature_f": temperature,
        "wind_mph": wind,
        "outdoors": 1.0 if roof in {"outdoors", "open"} else 0.0,
    }


def _observed_game(stats: dict[str, Any], points_for: float, points_against: float) -> dict[str, float]:
    return {
        "win": 1.0 if points_for > points_against else 0.0,
        "point_margin": points_for - points_against,
        "total_epa": _number(stats.get("passing_epa")) + _number(stats.get("rushing_epa")),
        "yards": _number(stats.get("passing_yards")) + _number(stats.get("rushing_yards")),
        "turnovers": _number(stats.get("passing_interceptions")) + _number(stats.get("fumbles_lost_total")),
        "def_sacks": _number(stats.get("def_sacks")),
    }


def _update_elo(home: TeamState, away: TeamState, home_won: float, k: float = 20.0) -> None:
    expected_home = 1 / (1 + 10 ** (-(home.elo + 55 - away.elo) / 400))
    delta = k * (home_won - expected_home)
    home.elo += delta
    away.elo -= delta


def build_features(
    games: pd.DataFrame,
    team_stats: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, TeamState]]:
    """Create chronological, leakage-safe training and upcoming-game features."""
    games = games.copy()
    games["gameday"] = pd.to_datetime(games["gameday"], errors="coerce")
    games = games.sort_values(["gameday", "gametime", "game_id"])

    keep = [column for column in ["game_id", "team", *STAT_COLUMNS] if column in team_stats.columns]
    stats_lookup = {
        (str(row["game_id"]), str(row["team"])): row
        for row in team_stats[keep].to_dict(orient="records")
    }
    states: dict[str, TeamState] = defaultdict(TeamState)
    training_rows: list[dict[str, Any]] = []
    upcoming_rows: list[dict[str, Any]] = []

    for game in games.itertuples(index=False):
        home_team = str(game.home_team)
        away_team = str(game.away_team)
        home_state = states[home_team]
        away_state = states[away_team]
        features = _feature_row(game, home_state, away_state)
        identity = {
            "game_id": str(game.game_id),
            "season": int(game.season),
            "week": int(game.week),
            "gameday": game.gameday,
            "gametime": str(game.gametime),
            "home_team": home_team,
            "away_team": away_team,
            "stadium": str(getattr(game, "stadium", "") or ""),
            "roof": str(getattr(game, "roof", "") or ""),
        }
        home_score = getattr(game, "home_score", np.nan)
        away_score = getattr(game, "away_score", np.nan)
        completed = not pd.isna(home_score) and not pd.isna(away_score)

        if completed:
            home_score = float(home_score)
            away_score = float(away_score)
            training_rows.append({**identity, **features, "home_win": int(home_score > away_score)})
            home_stats = _team_game(stats_lookup, str(game.game_id), home_team)
            away_stats = _team_game(stats_lookup, str(game.game_id), away_team)
            home_state.games.append(_observed_game(home_stats, home_score, away_score))
            away_state.games.append(_observed_game(away_stats, away_score, home_score))
            if home_score != away_score:
                _update_elo(home_state, away_state, float(home_score > away_score))
        else:
            upcoming_rows.append({**identity, **features})

    return pd.DataFrame(training_rows), pd.DataFrame(upcoming_rows), states

