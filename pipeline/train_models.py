from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.config import MODEL_DIR, PROCESSED_DIR, RANDOM_STATE, RAW_DIR, ensure_directories
from pipeline.features import FEATURE_COLUMNS, build_features


def _apply_kickoff_weather(games: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Replace missing upcoming weather with the nearest official NWS hourly forecast."""
    if weather.empty:
        return games
    games = games.copy()
    weather = weather.copy()
    weather["forecast_start"] = pd.to_datetime(weather["forecast_start"], utc=True, errors="coerce")

    for index, game in games[games["home_score"].isna()].iterrows():
        candidates = weather[weather["team"] == game["home_team"]].dropna(subset=["forecast_start"])
        if candidates.empty:
            continue
        timezone = str(candidates.iloc[0]["timezone"])
        kickoff = pd.Timestamp(f"{game['gameday']} {game['gametime']}", tz=timezone).tz_convert("UTC")
        closest_index = (candidates["forecast_start"] - kickoff).abs().idxmin()
        forecast = candidates.loc[closest_index]
        forecast_time = forecast["forecast_start"].to_pydatetime()
        kickoff_time = kickoff.to_pydatetime()
        if abs((forecast_time - kickoff_time).total_seconds()) > 12 * 60 * 60:
            continue
        games.at[index, "temp"] = forecast["temperature_f"]
        speed = re.search(r"\d+", str(forecast["wind_speed"]))
        games.at[index, "wind"] = float(speed.group()) if speed else 0.0
    return games


def _models() -> dict[str, Pipeline]:
    return {
        "logistic": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=350,
                        min_samples_leaf=8,
                        max_features="sqrt",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "gradient_boosting": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        max_iter=180,
                        learning_rate=0.05,
                        max_leaf_nodes=15,
                        l2_regularization=1.0,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def _injury_penalties(injuries: pd.DataFrame) -> dict[str, float]:
    if injuries.empty:
        return {}
    position_weight = {"QB": 2.5, "OT": 1.1, "WR": 0.8, "CB": 0.8, "EDGE": 0.8}
    status_weight = {"Out": 1.0, "Doubtful": 0.7, "Questionable": 0.25}
    penalties: dict[str, float] = {}
    for row in injuries.to_dict(orient="records"):
        status = str(row.get("report_status") or "")
        if status not in status_weight:
            continue
        team = str(row.get("team") or "")
        position = str(row.get("position") or "")
        penalties[team] = penalties.get(team, 0.0) + status_weight[status] * position_weight.get(position, 0.35)
    return penalties


def _confidence(probability: float) -> str:
    edge = abs(probability - 0.5)
    if edge >= 0.18:
        return "High"
    if edge >= 0.07:
        return "Medium"
    return "Low"


def _team_name(abbreviation: str) -> str:
    names = {
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
    return names.get(abbreviation, abbreviation)


def _top_factors(row: pd.Series) -> list[str]:
    candidates = [
        (abs(row["elo_diff"]) / 100, "Elo team strength"),
        (abs(row["point_margin_5_diff"]) / 7, "Recent scoring margin"),
        (abs(row["total_epa_5_diff"]) / 5, "Offensive EPA trend"),
        (abs(row["turnovers_5_diff"]), "Turnover trend"),
        (abs(row["def_sacks_5_diff"]), "Defensive pressure"),
        (abs(row["rest_diff"]) / 3, "Rest advantage"),
        (row["wind_mph"] / 15 if row["outdoors"] else 0, "Weather conditions"),
    ]
    return [label for _, label in sorted(candidates, reverse=True)[:3]]


def train_and_predict() -> dict[str, Any]:
    ensure_directories()
    games = pl.read_parquet(RAW_DIR / "games.parquet").to_pandas()
    team_stats = pl.read_parquet(RAW_DIR / "team_weekly.parquet").to_pandas()
    injury_path = RAW_DIR / "injuries.parquet"
    injuries = pl.read_parquet(injury_path).to_pandas() if injury_path.exists() else pd.DataFrame()
    weather_path = RAW_DIR / "weather_daily.parquet"
    weather = pl.read_parquet(weather_path).to_pandas() if weather_path.exists() else pd.DataFrame()
    games = _apply_kickoff_weather(games, weather)
    training, upcoming, _ = build_features(games, team_stats)
    training = training.sort_values(["gameday", "gametime", "game_id"])

    if len(training) < 200:
        raise RuntimeError(f"Need at least 200 completed games; found {len(training)}")

    latest_completed_season = int(training["season"].max())
    test_mask = training["season"] == latest_completed_season
    validation_method = f"season-{latest_completed_season}"
    if test_mask.sum() < 32 or (~test_mask).sum() < 200:
        split = int(len(training) * 0.8)
        test_mask = pd.Series(False, index=training.index)
        test_mask.iloc[split:] = True
        validation_method = "chronological-20-percent"

    X_train = training.loc[~test_mask, FEATURE_COLUMNS]
    y_train = training.loc[~test_mask, "home_win"]
    X_test = training.loc[test_mask, FEATURE_COLUMNS]
    y_test = training.loc[test_mask, "home_win"]

    fitted: dict[str, Pipeline] = {}
    metrics: dict[str, dict[str, float]] = {}
    for name, model in _models().items():
        model.fit(X_train, y_train)
        probabilities = model.predict_proba(X_test)[:, 1]
        metrics[name] = {
            "accuracy": round(float(accuracy_score(y_test, probabilities >= 0.5)), 4),
            "logLoss": round(float(log_loss(y_test, probabilities, labels=[0, 1])), 4),
            "brierScore": round(float(brier_score_loss(y_test, probabilities)), 4),
        }
        joblib.dump(model, MODEL_DIR / f"{name}.joblib", compress=3)
        fitted[name] = model

    if upcoming.empty:
        next_games = upcoming
    else:
        next_date = upcoming["gameday"].dropna().min()
        window = upcoming[upcoming["gameday"] <= next_date + pd.DateOffset(days=7)]
        next_week = int(window.sort_values("gameday").iloc[0]["week"])
        next_season = int(window.sort_values("gameday").iloc[0]["season"])
        next_games = upcoming[(upcoming["season"] == next_season) & (upcoming["week"] == next_week)]

    penalties = _injury_penalties(injuries)
    predictions: list[dict[str, Any]] = []
    if not next_games.empty:
        model_probabilities = np.column_stack(
            [model.predict_proba(next_games[FEATURE_COLUMNS])[:, 1] for model in fitted.values()]
        )
        ensemble = model_probabilities.mean(axis=1)
        for offset, (_, row) in enumerate(next_games.iterrows()):
            injury_adjustment = (penalties.get(row["away_team"], 0) - penalties.get(row["home_team"], 0)) / 100
            home_probability = float(np.clip(ensemble[offset] + injury_adjustment, 0.08, 0.92))
            home_name = _team_name(row["home_team"])
            away_name = _team_name(row["away_team"])
            predictions.append(
                {
                    "id": row["game_id"],
                    "awayTeam": away_name,
                    "awayAbbreviation": row["away_team"],
                    "homeTeam": home_name,
                    "homeAbbreviation": row["home_team"],
                    "kickoff": f"{row['gameday'].date().isoformat()} {row['gametime']}",
                    "predictedWinner": home_name if home_probability >= 0.5 else away_name,
                    "homeWinProbability": round(home_probability * 100),
                    "awayWinProbability": round((1 - home_probability) * 100),
                    "confidence": _confidence(home_probability),
                    "factors": _top_factors(row),
                }
            )

    season = int(next_games.iloc[0]["season"]) if not next_games.empty else latest_completed_season
    week = int(next_games.iloc[0]["week"]) if not next_games.empty else int(training.iloc[-1]["week"])
    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "season": season,
        "week": week,
        "asOf": generated_at,
        "provider": "nflverse + NOAA/NWS",
        "model": "fieldiq-ensemble-v1",
        "predictions": predictions,
    }
    (PROCESSED_DIR / "predictions.json").write_text(json.dumps(payload, indent=2) + "\n")
    metrics_payload = {
        "generatedAt": generated_at,
        "trainingGames": int(len(X_train)),
        "validationGames": int(len(X_test)),
        "validationMethod": validation_method,
        "features": FEATURE_COLUMNS,
        "models": metrics,
    }
    (PROCESSED_DIR / "model_metrics.json").write_text(json.dumps(metrics_payload, indent=2) + "\n")
    training.to_parquet(PROCESSED_DIR / "game_features.parquet", index=False)
    return {"predictionCount": len(predictions), **metrics_payload}


if __name__ == "__main__":
    print(json.dumps(train_and_predict(), indent=2))
