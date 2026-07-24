"""
Tests app.api.calendar in isolation from real Google/Firestore calls --
same monkeypatch-the-imported-name pattern as test_feedback_routes.py:
patch CalendarProvider / calendar_repository / oauth_state functions on
the *calendar* module's namespace (where they were imported into), not
their origin modules.
"""
from fastapi.testclient import TestClient

from app.api import calendar as calendar_module
from app.auth.dependencies import get_current_user
from app.core.oauth_state import InvalidOAuthState
from app.main import app

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


class _StubProvider:
    """Records what it was called with; no real network access."""

    def __init__(self, *args, **kwargs):
        self.exchanged_code = None

    def authorization_url(self, state):
        return f"https://accounts.google.com/o/oauth2/v2/auth?state={state}"

    async def exchange_code(self, code):
        self.exchanged_code = code
        from app.providers.calendar_provider import CalendarTokens

        return CalendarTokens(access_token="new-access", refresh_token="new-refresh", expires_at=1_000_000.0)


def test_connect_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    response = TestClient(app).post("/v1/calendar/connect")
    assert response.status_code == 401


def test_connect_returns_an_authorization_url(client, monkeypatch):
    monkeypatch.setattr(calendar_module, "CalendarProvider", _StubProvider)
    monkeypatch.setattr(calendar_module, "make_state", lambda uid: f"state-for-{uid}")

    response = client.post("/v1/calendar/connect")

    assert response.status_code == 200
    body = response.json()
    assert body["authorizationUrl"] == "https://accounts.google.com/o/oauth2/v2/auth?state=state-for-test-user"


def test_disconnect_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    response = TestClient(app).post("/v1/calendar/disconnect")
    assert response.status_code == 401


def test_disconnect_deletes_the_stored_token_and_returns_disconnected(client, monkeypatch):
    calls = []
    monkeypatch.setattr(calendar_module.calendar_repository, "delete_tokens", lambda uid: calls.append(uid))

    response = client.post("/v1/calendar/disconnect")

    assert response.status_code == 200
    assert response.json() == {"status": "disconnected"}
    assert calls == ["test-user"]


def test_status_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    response = TestClient(app).get("/v1/calendar/status")
    assert response.status_code == 401


@pytest.mark.parametrize("connected", [True, False])
def test_status_reflects_whether_tokens_exist(client, monkeypatch, connected):
    monkeypatch.setattr(calendar_module.calendar_repository, "is_connected", lambda uid: connected)

    response = client.get("/v1/calendar/status")

    assert response.status_code == 200
    assert response.json() == {"connected": connected}


def test_callback_with_no_code_redirects_to_settings_cancelled(client):
    response = client.get("/v1/calendar/oauth/callback", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "http://localhost:3000/settings?calendar=cancelled"


def test_callback_with_google_error_redirects_to_settings_cancelled(client):
    response = client.get(
        "/v1/calendar/oauth/callback",
        params={"error": "access_denied"},
        follow_redirects=False,
    )

    assert response.headers["location"] == "http://localhost:3000/settings?calendar=cancelled"


def test_callback_with_invalid_state_returns_400(client, monkeypatch):
    def _raise(_state):
        raise InvalidOAuthState("bad state")

    monkeypatch.setattr(calendar_module, "verify_state", _raise)

    response = client.get(
        "/v1/calendar/oauth/callback",
        params={"code": "abc", "state": "forged"},
        follow_redirects=False,
    )

    assert response.status_code == 400


def test_callback_with_valid_code_and_state_saves_tokens_and_redirects_connected(client, monkeypatch):
    monkeypatch.setattr(calendar_module, "verify_state", lambda state: "test-user")
    monkeypatch.setattr(calendar_module, "CalendarProvider", _StubProvider)

    saved = []
    monkeypatch.setattr(
        calendar_module.calendar_repository, "save_tokens", lambda uid, tokens: saved.append((uid, tokens))
    )

    response = client.get(
        "/v1/calendar/oauth/callback",
        params={"code": "auth-code-123", "state": "state-for-test-user"},
        follow_redirects=False,
    )

    assert response.headers["location"] == "http://localhost:3000/settings?calendar=connected"
    assert len(saved) == 1
    uid, tokens = saved[0]
    assert uid == "test-user"
    assert tokens.access_token == "new-access"
