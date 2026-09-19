from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from pipeline.config import ROLLING_WINDOW
from pipeline.pbp_features import PBP_FEATURE_COLUMNS

STAT_COLUMNS = [
    "passing_epa", "rushing_epa", "passing_yards", "rushing_yards",
    "passing_interceptions", "fumbles_lost_total", "def_sacks", *PBP_FEATURE_COLUMNS,
]

FEATURE_COLUMNS = [
    "elo_diff", "rest_diff", "win_rate_5_diff", "point_margin_5_diff",
    "total_epa_5_diff", "yards_5_diff", "turnovers_5_diff", "def_sacks_5_diff",
    "off_epa_per_play_5_diff", "def_epa_per_play_5_diff", "success_rate_5_diff",
    "yards_per_play_5_diff", "third_down_rate_5_diff", "red_zone_success_rate_5_diff",
    "explosive_play_rate_5_diff", "qb_epa_per_play_5_diff",
    "temperature_f", "wind_mph", "outdoors",
]


@dataclass
class TeamState:
    elo: float = 1500.0
    games: deque[dict[str, float]] = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW))

    def average(self, key: str, default: float = 0.0) -> float:
        values = [game[key] for game in self.games if not np.isnan(game.get(key, np.nan))]
        return float(np.mean(values)) if values else default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value): return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _team_game(stats, game_id, team):
    return stats.get((game_id, team), {})


def _feature_row(game, home: TeamState, away: TeamState) -> dict[str, float]:
    temperature = _number(getattr(game, "temp", np.nan), 65.0)
    wind = _number(getattr(game, "wind", np.nan), 0.0)
    roof = str(getattr(game, "roof", "") or "").lower()
    result = {
        "elo_diff": home.elo - away.elo,
        "rest_diff": _number(getattr(game, "home_rest", 7), 7) - _number(getattr(game, "away_rest", 7), 7),
        "win_rate_5_diff": home.average("win", .5) - away.average("win", .5),
        "point_margin_5_diff": home.average("point_margin") - away.average("point_margin"),
        "total_epa_5_diff": home.average("total_epa") - away.average("total_epa"),
        "yards_5_diff": home.average("yards") - away.average("yards"),
        "turnovers_5_diff": home.average("turnovers") - away.average("turnovers"),
        "def_sacks_5_diff": home.average("def_sacks") - away.average("def_sacks"),
        "temperature_f": temperature, "wind_mph": wind,
        "outdoors": 1.0 if roof in {"outdoors", "open"} else 0.0,
    }
    for key in PBP_FEATURE_COLUMNS:
        result[f"{key}_5_diff"] = home.average(key) - away.average(key)
    return result


def _observed_game(stats, points_for, points_against):
    observed = {
        "win": 1.0 if points_for > points_against else 0.0,
        "point_margin": points_for - points_against,
        "total_epa": _number(stats.get("passing_epa")) + _number(stats.get("rushing_epa")),
        "yards": _number(stats.get("passing_yards")) + _number(stats.get("rushing_yards")),
        "turnovers": _number(stats.get("passing_interceptions")) + _number(stats.get("fumbles_lost_total")),
        "def_sacks": _number(stats.get("def_sacks")),
    }
    for key in PBP_FEATURE_COLUMNS:
        observed[key] = _number(stats.get(key), np.nan)
    return observed


def _update_elo(home, away, home_won, k=20.0):
    expected_home = 1 / (1 + 10 ** (-(home.elo + 55 - away.elo) / 400))
    delta = k * (home_won - expected_home)
    home.elo += delta; away.elo -= delta


def build_features(games: pd.DataFrame, team_stats: pd.DataFrame):
    """Create chronological, leakage-safe training and upcoming-game features."""
    games = games.copy(); games["gameday"] = pd.to_datetime(games["gameday"], errors="coerce")
    games = games.sort_values(["gameday", "gametime", "game_id"])
    keep = [c for c in ["game_id", "team", *STAT_COLUMNS] if c in team_stats.columns]
    stats_lookup = {(str(r["game_id"]), str(r["team"])): r for r in team_stats[keep].to_dict(orient="records")}
    states = defaultdict(TeamState); training_rows=[]; upcoming_rows=[]
    for game in games.itertuples(index=False):
        home_team, away_team = str(game.home_team), str(game.away_team)
        home_state, away_state = states[home_team], states[away_team]
        features = _feature_row(game, home_state, away_state)
        identity = {"game_id":str(game.game_id), "season":int(game.season), "week":int(game.week),
                    "gameday":game.gameday, "gametime":str(game.gametime), "home_team":home_team,
                    "away_team":away_team, "stadium":str(getattr(game,"stadium","") or ""),
                    "roof":str(getattr(game,"roof","") or "")}
        hs, aws = getattr(game,"home_score",np.nan), getattr(game,"away_score",np.nan)
        completed = not pd.isna(hs) and not pd.isna(aws)
        if completed:
            hs, aws = float(hs), float(aws)
            training_rows.append({**identity, **features, "home_win":int(hs>aws), "home_score":hs, "away_score":aws, "home_margin":hs-aws, "game_total":hs+aws})
            hstats=_team_game(stats_lookup,str(game.game_id),home_team); astats=_team_game(stats_lookup,str(game.game_id),away_team)
            home_state.games.append(_observed_game(hstats,hs,aws)); away_state.games.append(_observed_game(astats,aws,hs))
            if hs != aws: _update_elo(home_state,away_state,float(hs>aws))
        else: upcoming_rows.append({**identity, **features})
    return pd.DataFrame(training_rows), pd.DataFrame(upcoming_rows), states
