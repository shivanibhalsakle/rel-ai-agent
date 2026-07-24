"""
Tests POST /v1/recommendations/{recommendationId}/feedback in isolation
from Firestore -- app.api.feedback's feedback_repository.save_feedback is
patched to a recording stub, same monkeypatch-the-imported-name pattern
M4.10's test_chat_routes.py and M4.11's test_agent_conversations.py use
(patch the name in the module that imported it, not the origin module).
"""
from fastapi.testclient import TestClient

from app.api import feedback as feedback_module
from app.auth.dependencies import get_current_user
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


class _RecordingRepo:
    def __init__(self):
        self.calls = []

    def save_feedback(self, uid, record):
        self.calls.append((uid, record))
        return record


def test_feedback_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    response = client.post(
        "/v1/recommendations/p1/feedback",
        json={"sessionId": "s1", "intent": "fitness", "action": "accepted"},
    )
    assert response.status_code == 401


def test_submit_feedback_saves_a_record_with_the_url_id_and_current_user(client, monkeypatch):
    repo = _RecordingRepo()
    monkeypatch.setattr(feedback_module.feedback_repository, "save_feedback", repo.save_feedback)

    response = client.post(
        "/v1/recommendations/p1/feedback",
        json={
            "sessionId": "s1",
            "intent": "fitness",
            "action": "rejected",
            "reason": "too far",
            "scoreBreakdown": {"rating": 0.9, "affordability": 0.2},
        },
    )

    assert response.status_code == 201
    assert response.json() == {"status": "saved"}
    assert len(repo.calls) == 1
    uid, record = repo.calls[0]
    assert uid == "test-user"
    assert record.related_recommendation_id == "p1"
    assert record.related_session_id == "s1"
    assert record.intent == "fitness"
    assert record.action == "rejected"
    assert record.reason == "too far"
    assert record.score_breakdown == {"rating": 0.9, "affordability": 0.2}


def test_submit_feedback_reason_and_score_breakdown_are_optional(client, monkeypatch):
    repo = _RecordingRepo()
    monkeypatch.setattr(feedback_module.feedback_repository, "save_feedback", repo.save_feedback)

    response = client.post(
        "/v1/recommendations/route-0/feedback",
        json={"sessionId": "s1", "intent": "route", "action": "accepted"},
    )

    assert response.status_code == 201
    _uid, record = repo.calls[0]
    assert record.reason is None
    assert record.score_breakdown == {}


def test_invalid_action_is_rejected(client):
    response = client.post(
        "/v1/recommendations/p1/feedback",
        json={"sessionId": "s1", "intent": "fitness", "action": "maybe"},
    )

    assert response.status_code == 422
