"""
Behavior test for GET /v1/preferences/inferred (M7.6) -- the rest of the
preferences endpoints only have auth-requirement coverage
(test_preferences_routes_auth.py) since they're straightforward CRUD
verified manually in M1.6. This one gets its own real behavior test
because the "no feedback yet" case matters: unlike GET /preferences,
it must NOT 404.
"""
from fastapi.testclient import TestClient

from app.api import preferences as preferences_module
from app.auth.dependencies import get_current_user
from app.main import app
from app.scoring.preference_adjustment import InferredAdjustment

import pytest


def _fake_user():
    return {"uid": "test-user"}


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_no_feedback_yet_returns_an_empty_adjustment_not_a_404(client, monkeypatch):
    monkeypatch.setattr(
        preferences_module.preference_repository, "get_inferred_adjustment", lambda uid: InferredAdjustment()
    )

    response = client.get("/v1/preferences/inferred")

    assert response.status_code == 200
    assert response.json() == {"importanceDelta": {}, "reasons": []}


def test_returns_the_stored_adjustment_and_reasons(client, monkeypatch):
    stored = InferredAdjustment(
        importance_delta={"affordability": 1},
        reasons=["You've rejected 3 recent options that scored low on affordability — weighting it more heavily."],
    )
    monkeypatch.setattr(preferences_module.preference_repository, "get_inferred_adjustment", lambda uid: stored)

    response = client.get("/v1/preferences/inferred")

    body = response.json()
    assert body["importanceDelta"] == {"affordability": 1}
    assert len(body["reasons"]) == 1
