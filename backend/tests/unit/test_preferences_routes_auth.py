from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_onboarding_requires_auth():
    response = client.post("/v1/onboarding", json={"activities": ["gym"]})
    assert response.status_code == 401


def test_get_preferences_requires_auth():
    response = client.get("/v1/preferences")
    assert response.status_code == 401


def test_put_preferences_requires_auth():
    response = client.put("/v1/preferences", json={})
    assert response.status_code == 401
