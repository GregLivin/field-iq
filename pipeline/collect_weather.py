from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from pipeline.config import RAW_DIR, ROOT, ensure_directories

NWS_BASE_URL = "https://api.weather.gov"
STADIUMS_PATH = ROOT / "data" / "reference" / "stadiums.csv"


def _headers() -> dict[str, str]:
    contact = os.getenv("FIELDIQ_CONTACT_EMAIL", "fieldiq@example.com")
    return {
        "User-Agent": f"FieldIQ/0.2 ({contact})",
        "Accept": "application/geo+json",
    }


def _forecast_for_point(client: httpx.Client, latitude: float, longitude: float) -> list[dict[str, Any]]:
    point = client.get(f"{NWS_BASE_URL}/points/{latitude},{longitude}")
    point.raise_for_status()
    hourly_url = point.json()["properties"]["forecastHourly"]
    forecast = client.get(hourly_url)
    forecast.raise_for_status()
    return forecast.json()["properties"]["periods"]


def collect_weather() -> dict[str, object]:
    """Collect the latest official NWS snapshot for every outdoor NFL venue."""
    ensure_directories()
    stadiums = pl.read_csv(STADIUMS_PATH).drop_nulls(["stadium", "latitude", "longitude"])
    snapshots: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    with httpx.Client(headers=_headers(), timeout=20, follow_redirects=True) as client:
        for stadium in stadiums.iter_rows(named=True):
            if stadium["roof"] == "dome":
                continue
            try:
                forecasts = _forecast_for_point(
                    client,
                    float(stadium["latitude"]),
                    float(stadium["longitude"]),
                )
                for forecast in forecasts:
                    snapshots.append(
                        {
                            "stadium": stadium["stadium"],
                            "team": stadium["team"],
                            "timezone": stadium["timezone"],
                            "latitude": stadium["latitude"],
                            "longitude": stadium["longitude"],
                            "forecast_start": forecast.get("startTime"),
                            "temperature_f": forecast.get("temperature"),
                            "wind_speed": forecast.get("windSpeed"),
                            "wind_direction": forecast.get("windDirection"),
                            "short_forecast": forecast.get("shortForecast"),
                            "precipitation_probability": (
                                forecast.get("probabilityOfPrecipitation") or {}
                            ).get("value"),
                            "collected_at": datetime.now(UTC).isoformat(),
                        }
                    )
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                errors.append({"stadium": str(stadium["stadium"]), "error": str(exc)})

    frame = pl.DataFrame(snapshots) if snapshots else pl.DataFrame()
    output = RAW_DIR / "weather_daily.parquet"
    if frame.height:
        frame.write_parquet(output, compression="zstd")

    status = {
        "provider": "NOAA/National Weather Service",
        "collectedAt": datetime.now(UTC).isoformat(),
        "stadiumsCollected": int(frame["stadium"].n_unique()) if frame.height else 0,
        "forecastRows": frame.height,
        "errors": errors,
    }
    (RAW_DIR / "weather_status.json").write_text(json.dumps(status, indent=2) + "\n")
    return status


if __name__ == "__main__":
    print(json.dumps(collect_weather(), indent=2))
