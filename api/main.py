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

app = FastAPI(title="FieldIQ NFL API", version="0.2.0")
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


@app.get("/health")
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


@app.get("/api/model")
async def model_metrics() -> dict[str, Any]:
    return _load_json(METRICS_PATH)


@app.get("/api/data-status")
async def data_status() -> dict[str, Any]:
    return {
        "nflverse": _load_json(MANIFEST_PATH),
        "weather": _load_json(WEATHER_STATUS_PATH),
        "officialNFLFeed": False,
        "notice": "nflverse is community-maintained and is not an official NFL feed.",
    }
