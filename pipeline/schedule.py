from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


TEAM_NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}


def team_name(abbreviation: str) -> str:
    return TEAM_NAMES.get(abbreviation, abbreviation)


def matchup_key(team_one: str, team_two: str) -> str:
    return "__".join(sorted((team_one.upper(), team_two.upper())))


def _optional_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value)


def _score(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _meeting(row: pd.Series) -> dict[str, Any]:
    away_score = _score(row.get("away_score"))
    home_score = _score(row.get("home_score"))
    winner = None
    winner_abbreviation = None
    if away_score is not None and home_score is not None:
        if home_score > away_score:
            winner_abbreviation = str(row["home_team"])
        elif away_score > home_score:
            winner_abbreviation = str(row["away_team"])
        winner = team_name(winner_abbreviation) if winner_abbreviation else "Tie"

    date = pd.Timestamp(row["gameday"]).date().isoformat()
    return {
        "id": str(row["game_id"]),
        "date": date,
        "season": int(row["season"]),
        "week": int(row["week"]),
        "gameType": str(row.get("game_type") or "REG"),
        "awayTeam": team_name(str(row["away_team"])),
        "awayAbbreviation": str(row["away_team"]),
        "awayScore": away_score,
        "homeTeam": team_name(str(row["home_team"])),
        "homeAbbreviation": str(row["home_team"]),
        "homeScore": home_score,
        "winner": winner,
        "winnerAbbreviation": winner_abbreviation,
    }


def build_schedule_payloads(
    games: pd.DataFrame,
    season: int,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a complete season schedule and reusable head-to-head history."""
    frame = games.copy()
    frame["gameday"] = pd.to_datetime(frame["gameday"], errors="coerce")
    frame = frame.dropna(subset=["gameday", "away_team", "home_team"])
    frame = frame.sort_values(["gameday", "gametime", "game_id"])
    generated_at = generated_at or datetime.now(UTC).isoformat()

    completed = frame[
        frame["away_score"].notna()
        & frame["home_score"].notna()
        & frame.get("game_type", pd.Series("REG", index=frame.index)).isin(["REG", "POST"])
    ].copy()

    histories: dict[str, list[dict[str, Any]]] = {}
    for _, row in completed.sort_values("gameday", ascending=False).iterrows():
        key = matchup_key(str(row["away_team"]), str(row["home_team"]))
        histories.setdefault(key, []).append(_meeting(row))

    season_games: list[dict[str, Any]] = []
    current = frame[frame["season"] == season]
    for _, row in current.iterrows():
        away = str(row["away_team"])
        home = str(row["home_team"])
        away_score = _score(row.get("away_score"))
        home_score = _score(row.get("home_score"))
        key = matchup_key(away, home)
        game_date = pd.Timestamp(row["gameday"]).date().isoformat()
        prior_meetings = [meeting for meeting in histories.get(key, []) if meeting["date"] < game_date]
        meeting = _meeting(row)
        season_games.append(
            {
                **meeting,
                "time": _optional_text(row.get("gametime")),
                "status": "final" if away_score is not None and home_score is not None else "upcoming",
                "stadium": _optional_text(row.get("stadium")),
                "roof": _optional_text(row.get("roof")),
                "surface": _optional_text(row.get("surface")),
                "lastMeeting": prior_meetings[0] if prior_meetings else None,
            }
        )

    weeks = sorted({int(game["week"]) for game in season_games})
    teams = sorted(
        {
            game[team]
            for game in season_games
            for team in ("awayAbbreviation", "homeAbbreviation")
        }
    )
    schedule_payload = {
        "season": season,
        "asOf": generated_at,
        "provider": "nflverse",
        "weeks": weeks,
        "teams": teams,
        "games": season_games,
    }
    history_payload = {
        "asOf": generated_at,
        "provider": "nflverse",
        "matchups": histories,
    }
    return schedule_payload, history_payload


def write_schedule_payloads(
    games: pd.DataFrame,
    season: int,
    output_dir: Path,
    generated_at: str,
) -> tuple[Path, Path]:
    schedule, histories = build_schedule_payloads(games, season, generated_at)
    schedule_path = output_dir / "schedule.json"
    history_path = output_dir / "matchup_history.json"
    schedule_path.write_text(json.dumps(schedule, indent=2) + "\n")
    history_path.write_text(json.dumps(histories, indent=2) + "\n")
    return schedule_path, history_path
