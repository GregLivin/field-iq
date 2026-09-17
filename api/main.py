import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_PATH = ROOT / "data" / "processed" / "predictions.json"
METRICS_PATH = ROOT / "data" / "processed" / "model_metrics.json"
MANIFEST_PATH = ROOT / "data" / "raw" / "manifest.json"
WEATHER_STATUS_PATH = ROOT / "data" / "raw" / "weather_status.json"
SCHEDULE_PATH = ROOT / "data" / "processed" / "schedule.json"
MATCHUP_HISTORY_PATH = ROOT / "data" / "processed" / "matchup_history.json"

app = FastAPI(title="Field IQ NFL API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Generated artifact {path.name} is not available yet.",
        ) from exc


def _expand_meeting(values: list[Any]) -> dict[str, Any]:
    return {
        "id": values[0], "date": values[1], "season": values[2], "week": values[3],
        "gameType": values[4], "awayTeam": values[5], "awayAbbreviation": values[5],
        "awayScore": values[6], "homeTeam": values[7], "homeAbbreviation": values[7],
        "homeScore": values[8], "winner": values[9] or "Tie",
        "winnerAbbreviation": values[9],
    }


def _expand_recent_game(values: list[Any]) -> dict[str, Any]:
    return {
        "id": values[0], "date": values[1], "season": values[2], "week": values[3],
        "gameType": values[4], "teamAbbreviation": values[5],
        "opponent": values[6], "opponentAbbreviation": values[6],
        "homeAway": values[7], "teamScore": values[8], "opponentScore": values[9],
        "result": values[10], "passingYards": values[11], "rushingYards": values[12],
        "totalYards": values[13], "totalEpa": values[14], "turnovers": values[15],
        "defensiveSacks": values[16],
    }


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "time": datetime.now(UTC).isoformat(),
        "predictions": "ready" if PREDICTIONS_PATH.exists() else "pending",
    }


@app.get("/api/predictions")
async def predictions(
    season: int | None = Query(None, ge=2000, le=2100),
    week: int | None = Query(None, ge=1, le=22),
) -> dict[str, Any]:
    payload = _load_json(PREDICTIONS_PATH)
    if season is not None and season != payload.get("season"):
        return {**payload, "predictions": []}
    if week is not None and week != payload.get("week"):
        return {**payload, "predictions": []}
    return payload


@app.get("/api/schedule")
async def schedule(
    season: int | None = Query(None, ge=2000, le=2100),
    week: int | None = Query(None, ge=1, le=22),
    team: str | None = Query(None, min_length=2, max_length=3),
    status: str | None = Query(None, pattern="^(upcoming|final)$"),
) -> dict[str, Any]:
    payload = _load_json(SCHEDULE_PATH)
    games = payload.get("games", [])
    if season is not None and season != payload.get("season"):
        games = []
    if week is not None:
        games = [game for game in games if game.get("week") == week]
    if team is not None:
        abbreviation = team.upper()
        games = [
            game
            for game in games
            if abbreviation in (game.get("awayAbbreviation"), game.get("homeAbbreviation"))
        ]
    if status is not None:
        games = [game for game in games if game.get("status") == status]
    return {**payload, "games": games, "count": len(games)}


@app.get("/api/matchups")
async def matchup_history(
    team1: str = Query(..., min_length=2, max_length=3),
    team2: str = Query(..., min_length=2, max_length=3),
    limit: int = Query(5, ge=1, le=25),
) -> dict[str, Any]:
    payload = _load_json(MATCHUP_HISTORY_PATH)
    teams = sorted((team1.upper(), team2.upper()))
    key = "__".join(teams)
    meetings = [
        _expand_meeting(meeting)
        for meeting in payload.get("matchups", {}).get(key, [])[:limit]
    ]
    recent_form = {
        team: [
            _expand_recent_game(game)
            for game in payload.get("recentForm", {}).get(team, [])[:limit]
        ]
        for team in teams
    }
    return {
        "asOf": payload.get("asOf"),
        "provider": payload.get("provider"),
        "teams": teams,
        "meetings": meetings,
        "recentForm": recent_form,
        "count": len(meetings),
    }


@app.get("/api/model")
async def model_metrics() -> dict[str, Any]:
    return _load_json(METRICS_PATH)


@app.get("/api/data-status")
@app.get("/api/data_status")
async def data_status() -> dict[str, Any]:
    return {
        "nflverse": _load_json(MANIFEST_PATH),
        "weather": _load_json(WEATHER_STATUS_PATH),
        "officialNFLFeed": False,
        "notice": "nflverse is community-maintained and is not an official NFL feed.",
    }
