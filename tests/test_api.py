from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_predictions_artifact_is_served() -> None:
    response = client.get("/api/predictions")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["model"], str)
    assert payload["model"].startswith("fieldiq-ensemble-v")
    assert payload["predictions"]


def test_model_metrics_are_served() -> None:
    response = client.get("/api/model")
    assert response.status_code == 200
    assert response.json()["validationGames"] > 0


def test_file_based_vercel_routes_import_the_same_app() -> None:
    from api.health import app as health_app
    from api.matchups import app as matchups_app
    from api.model import app as model_app
    from api.predictions import app as predictions_app
    from api.schedule import app as schedule_app

    assert health_app is app
    assert model_app is app
    assert predictions_app is app
    assert schedule_app is app
    assert matchups_app is app


def test_schedule_can_filter_by_week_and_team() -> None:
    response = client.get("/api/schedule?week=2&team=BUF")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["games"][0]["week"] == 2
    assert "BUF" in (
        payload["games"][0]["awayAbbreviation"],
        payload["games"][0]["homeAbbreviation"],
    )


def test_matchup_history_returns_recent_meetings() -> None:
    response = client.get("/api/matchups?team1=BUF&team2=DET&limit=3")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] <= 3
    assert payload["teams"] == ["BUF", "DET"]
    assert set(payload["recentForm"]) == {"BUF", "DET"}
