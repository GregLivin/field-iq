from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_predictions_artifact_is_served() -> None:
    response = client.get("/api/predictions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "fieldiq-ensemble-v1"
    assert payload["predictions"]


def test_model_metrics_are_served() -> None:
    response = client.get("/api/model")
    assert response.status_code == 200
    assert response.json()["validationGames"] > 0


def test_file_based_vercel_routes_import_the_same_app() -> None:
    from api.health import app as health_app
    from api.model import app as model_app
    from api.predictions import app as predictions_app

    assert health_app is app
    assert model_app is app
    assert predictions_app is app
