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
