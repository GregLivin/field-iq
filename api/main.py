import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
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
    allow_methods=["GET", "POST"],
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


class AlertPreferences(BaseModel):
    gameReminders: bool = True
    predictionUpdates: bool = True
    highConfidence: bool = True
    finalResults: bool = True


class TextAlertRequest(BaseModel):
    phone: str
    preferences: AlertPreferences


@app.post("/api/alerts/test")
async def send_test_alert(request: TextAlertRequest) -> dict[str, Any]:
    """Send an opt-in Field IQ test SMS through Twilio."""
    phone = request.phone.strip()
    if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 11:
        raise HTTPException(status_code=400, detail="Enter a phone number in E.164 format, for example +17135551234.")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not all((account_sid, auth_token, from_number)):
        raise HTTPException(status_code=503, detail="Text alerts are not configured on the server yet.")

    enabled = []
    labels = {
        "gameReminders": "game reminders",
        "predictionUpdates": "prediction updates",
        "highConfidence": "high-confidence alerts",
        "finalResults": "final results",
    }
    prefs = request.preferences.model_dump()
    for key, label in labels.items():
        if prefs.get(key):
            enabled.append(label)

    body = "Field IQ alerts are on. " + (", ".join(enabled) if enabled else "No alert categories selected.") + " Reply STOP to opt out."
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            data={"To": phone, "From": from_number, "Body": body},
            auth=(account_sid, auth_token),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="The SMS provider could not send the test alert.")
    return {"ok": True, "message": "Field IQ test alert sent."}



@app.post("/api/market-screenshot")
async def analyze_market_screenshot(file: UploadFile = File(...)) -> dict[str, Any]:
    """Extract sportsbook-style NFL matchup lines from a screenshot using a configured vision endpoint."""
    image = await file.read()
    if not image or len(image) > 8_000_000:
        raise HTTPException(status_code=400, detail="Upload a screenshot smaller than 8 MB.")
    vision_url = os.getenv("FIELDIQ_VISION_URL")
    vision_key = os.getenv("FIELDIQ_VISION_KEY")
    if not vision_url:
        raise HTTPException(status_code=503, detail="Screenshot vision is not configured on the server yet.")
    headers = {"Authorization": f"Bearer {vision_key}"} if vision_key else {}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            vision_url,
            headers=headers,
            files={"file": (file.filename or "screenshot.jpg", image, file.content_type or "image/jpeg")},
            data={"task": "Extract NFL games only. Return JSON games with awayTeam, homeTeam, awaySpread, homeSpread, total, awayMoneyline, homeMoneyline. Use null when unreadable."},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="The vision service could not analyze this screenshot.")
    try:
        payload=response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="The vision service returned invalid data.") from exc
    games=payload.get("games", []) if isinstance(payload, dict) else []
    if not isinstance(games, list):
        raise HTTPException(status_code=502, detail="The vision service returned an invalid games list.")
    return {"games": games, "message": f"Found {len(games)} matchup(s). Review every extracted line before analysis."}

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
