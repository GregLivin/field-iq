import math
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FieldIQ NFL API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this before production.
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

SPORTSDATAIO_BASE_URL = "https://api.sportsdata.io/v3/nfl/scores/json"


def probability_from_spread(home_spread: float | None) -> float:
    """Transparent MVP baseline; replace with the trained FieldIQ model."""
    if home_spread is None:
        return 0.55
    return max(0.1, min(0.9, 1 / (1 + math.exp(home_spread / 6.5))))


def confidence_label(probability: float) -> str:
    edge = abs(probability - 0.5)
    if edge >= 0.2:
        return "High"
    if edge >= 0.08:
        return "Medium"
    return "Low"


def format_game(game: dict[str, Any]) -> dict[str, Any]:
    home_probability = probability_from_spread(game.get("PointSpread"))
    away_probability = 1 - home_probability
    home_name = game.get("HomeTeamName") or game.get("HomeTeam", "Home")
    away_name = game.get("AwayTeamName") or game.get("AwayTeam", "Away")
    winner = home_name if home_probability >= 0.5 else away_name
    kickoff = game.get("DateTime") or game.get("Date") or "TBD"

    return {
        "id": str(game.get("GameKey") or game.get("GlobalGameID") or kickoff),
        "awayTeam": away_name,
        "awayAbbreviation": game.get("AwayTeam", "AWAY"),
        "homeTeam": home_name,
        "homeAbbreviation": game.get("HomeTeam", "HOME"),
        "kickoff": kickoff,
        "predictedWinner": winner,
        "homeWinProbability": round(home_probability * 100),
        "awayWinProbability": round(away_probability * 100),
        "confidence": confidence_label(home_probability),
        "factors": ["Market spread baseline", "Home field", "Matchup context"],
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/predictions")
async def predictions(
    season: int = Query(2026, ge=2000, le=2100),
    week: int = Query(1, ge=1, le=22),
) -> dict[str, Any]:
    api_key = os.getenv("SPORTSDATAIO_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="SPORTSDATAIO_API_KEY is not configured on the server.",
        )

    url = f"{SPORTSDATAIO_BASE_URL}/ScoresByWeek/{season}/{week}"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params={"key": api_key})

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"NFL provider returned status {response.status_code}.",
        )

    games = response.json()
    return {
        "season": season,
        "week": week,
        "provider": "SportsDataIO",
        "model": "spread-baseline-v0",
        "predictions": [format_game(game) for game in games],
    }
