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


def _compact_meeting(meeting: dict[str, Any]) -> list[Any]:
    """Keep the production history artifact small enough for fast cold starts."""
    return [
        meeting["id"], meeting["date"], meeting["season"], meeting["week"],
        meeting["gameType"], meeting["awayAbbreviation"], meeting["awayScore"],
        meeting["homeAbbreviation"], meeting["homeScore"], meeting["winnerAbbreviation"],
    ]


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 2)


def _recent_team_game(
    row: pd.Series,
    team: str,
    stats: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    is_home = str(row["home_team"]) == team
    opponent = str(row["away_team"] if is_home else row["home_team"])
    team_score = _score(row["home_score"] if is_home else row["away_score"])
    opponent_score = _score(row["away_score"] if is_home else row["home_score"])
    team_stats = stats.get((str(row["game_id"]), team), {})
    passing_yards = _number(team_stats.get("passing_yards"))
    rushing_yards = _number(team_stats.get("rushing_yards"))
    passing_epa = _number(team_stats.get("passing_epa"))
    rushing_epa = _number(team_stats.get("rushing_epa"))
    interceptions = _number(team_stats.get("passing_interceptions")) or 0
    fumbles_lost = _number(team_stats.get("fumbles_lost_total")) or 0

    result = "T"
    if team_score is not None and opponent_score is not None:
        result = "W" if team_score > opponent_score else "L" if team_score < opponent_score else "T"

    return {
        "id": str(row["game_id"]),
        "date": pd.Timestamp(row["gameday"]).date().isoformat(),
        "season": int(row["season"]),
        "week": int(row["week"]),
        "gameType": str(row.get("game_type") or "REG"),
        "teamAbbreviation": team,
        "opponent": team_name(opponent),
        "opponentAbbreviation": opponent,
        "homeAway": "Home" if is_home else "Away",
        "teamScore": team_score,
        "opponentScore": opponent_score,
        "result": result,
        "passingYards": passing_yards,
        "rushingYards": rushing_yards,
        "totalYards": (
            round(passing_yards + rushing_yards, 2)
            if passing_yards is not None and rushing_yards is not None
            else None
        ),
        "totalEpa": (
            round(passing_epa + rushing_epa, 2)
            if passing_epa is not None and rushing_epa is not None
            else None
        ),
        "turnovers": round(interceptions + fumbles_lost, 2),
        "defensiveSacks": _number(team_stats.get("def_sacks")),
    }


def _compact_recent_game(game: dict[str, Any]) -> list[Any]:
    return [
        game["id"], game["date"], game["season"], game["week"], game["gameType"],
        game["teamAbbreviation"], game["opponentAbbreviation"], game["homeAway"],
        game["teamScore"], game["opponentScore"], game["result"], game["passingYards"],
        game["rushingYards"], game["totalYards"], game["totalEpa"], game["turnovers"],
        game["defensiveSacks"],
    ]



def _season_summary(frame, team, season):
    rows=frame[(frame["season"]==season)&((frame["home_team"].astype(str)==team)|(frame["away_team"].astype(str)==team))]
    w=l=t=pf=pa=0
    for _,r in rows.iterrows():
        home=str(r["home_team"])==team; a=_score(r["home_score"] if home else r["away_score"]); b=_score(r["away_score"] if home else r["home_score"])
        if a is None or b is None: continue
        pf+=a; pa+=b
        if a>b: w+=1
        elif a<b: l+=1
        else: t+=1
    n=w+l+t
    return {"season":season,"wins":w,"losses":l,"ties":t,"gamesPlayed":n,"winPct":round((w+.5*t)/n,3) if n else None,"pointsFor":pf,"pointsAgainst":pa,"pointDifferential":pf-pa}


def build_schedule_payloads(
    games: pd.DataFrame,
    season: int,
    generated_at: str | None = None,
    team_stats: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a complete season schedule and reusable head-to-head history."""
    frame = games.copy()
    frame["gameday"] = pd.to_datetime(frame["gameday"], errors="coerce")
    frame = frame.dropna(subset=["gameday", "away_team", "home_team"])
    frame = frame.sort_values(["gameday", "gametime", "game_id"])
    generated_at = generated_at or datetime.now(UTC).isoformat()

    current = frame[frame["season"] == season]
    # Build history for every NFL pairing present in the dataset, not only pairings\n    # on the current schedule. This lets every matchup query resolve its latest meetings.\n    all_matchups = {\n        matchup_key(str(row["away_team"]), str(row["home_team"]))\n        for _, row in frame.iterrows()\n    }
    completed = frame[
        frame["away_score"].notna()
        & frame["home_score"].notna()
        & frame.get("game_type", pd.Series("REG", index=frame.index)).isin(["REG", "POST"])
    ].copy()

    stats: dict[tuple[str, str], dict[str, Any]] = {}
    if team_stats is not None and not team_stats.empty:
        stats = {
            (str(row.get("game_id")), str(row.get("team"))): row
            for row in team_stats.to_dict(orient="records")
        }

    histories: dict[str, list[dict[str, Any]]] = {}
    for _, row in completed.sort_values("gameday", ascending=False).iterrows():
        key = matchup_key(str(row["away_team"]), str(row["home_team"]))
        if key in all_matchups and len(histories.get(key, [])) < 5:
            histories.setdefault(key, []).append(_meeting(row))

    recent_form: dict[str, list[dict[str, Any]]] = {}
    recent_seasons = {season - 1, season}
    for _, row in completed[completed["season"].isin(recent_seasons)].sort_values(
        "gameday", ascending=False
    ).iterrows():
        for team in (str(row["away_team"]), str(row["home_team"])):
            if len(recent_form.get(team, [])) < 5:
                recent_form.setdefault(team, []).append(_recent_team_game(row, team, stats))

    season_games: list[dict[str, Any]] = []
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
        "provider": "nflverse automated coverage; NFL.com official matchup reference",
        "officialReference": "https://www.nfl.com/schedules",
        "fields": ["id", "date", "season", "week", "gameType", "away", "awayScore", "home", "homeScore", "winner"],
        "matchups": {
            key: [_compact_meeting(meeting) for meeting in meetings]
            for key, meetings in histories.items()
        },
        "recentFields": [
            "id", "date", "season", "week", "gameType", "team", "opponent",
            "homeAway", "teamScore", "opponentScore", "result", "passingYards",
            "rushingYards", "totalYards", "totalEpa", "turnovers", "defensiveSacks",
        ],
        "seasonSummaries": {team: {"current": _season_summary(completed, team, season), "previous": _season_summary(completed, team, season-1)} for team in teams},
        "recentForm": {
            team: [_compact_recent_game(game) for game in team_games]
            for team, team_games in recent_form.items()
        },
    }
    return schedule_payload, history_payload

def _expand_compact_meeting(v):
    return {"id":v[0],"date":v[1],"season":v[2],"week":v[3],"gameType":v[4],"awayAbbreviation":v[5],"awayScore":v[6],"homeAbbreviation":v[7],"homeScore":v[8],"winnerAbbreviation":v[9]}

def _expand_compact_recent(v):
    keys=["id","date","season","week","gameType","teamAbbreviation","opponentAbbreviation","homeAway","teamScore","opponentScore","result","passingYards","rushingYards","totalYards","totalEpa","turnovers","defensiveSacks"]
    return dict(zip(keys,v))

def build_matchup_intelligence(schedule, history, predictions=None):
    prediction_map={str(p.get("id")):p for p in (predictions or {}).get("predictions",[])}
    records={}
    for game in schedule.get("games",[]):
        away,home=game["awayAbbreviation"],game["homeAbbreviation"]; key=matchup_key(away,home)
        records[str(game["id"])]={
          "game":game,"teams":[away,home],
          "seasonSummaries":{t:history.get("seasonSummaries",{}).get(t,{}) for t in (away,home)},
          "recentForm":{t:[_expand_compact_recent(x) for x in history.get("recentForm",{}).get(t,[])] for t in (away,home)},
          "headToHead":[_expand_compact_meeting(x) for x in history.get("matchups",{}).get(key,[])],
          "prediction":prediction_map.get(str(game["id"]))
        }
    return {"season":schedule.get("season"),"asOf":schedule.get("asOf"),"provider":schedule.get("provider"),"games":records}


def write_schedule_payloads(
    games: pd.DataFrame,
    season: int,
    output_dir: Path,
    generated_at: str,
    team_stats: pd.DataFrame | None = None,
    predictions: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    schedule, histories = build_schedule_payloads(games, season, generated_at, team_stats)
    schedule_path = output_dir / "schedule.json"
    history_path = output_dir / "matchup_history.json"
    matchup_path = output_dir / "matchups.json"
    schedule_path.write_text(json.dumps(schedule, indent=2) + "\n")
    history_path.write_text(json.dumps(histories, indent=2) + "\n")
    matchup_path.write_text(json.dumps(build_matchup_intelligence(schedule, histories, predictions), indent=2) + "\n")
    return schedule_path, history_path, matchup_path
