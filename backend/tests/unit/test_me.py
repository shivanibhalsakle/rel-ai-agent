from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_me_requires_authorization_header():
    response = client.get("/v1/me")
    assert response.status_code == 401


def test_me_rejects_garbage_token():
    response = client.get("/v1/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
