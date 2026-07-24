"""
Tests the /v1/chat and /v1/chat/{sessionId}/resume endpoints in isolation
from the real graph -- app.api.chat.get_graph is patched to return a
FakeGraph test double instead. This is the same constraint M4.9's
test_graph.py documented: LangGraph invokes nodes as node(state) with no
injection point, so anything that actually ran the compiled graph would
need real API keys. What we CAN verify without those keys: that the route
layer picks the right graph_input (fresh state / Command(resume=...) /
turn-reset dict) for each of the four session situations, and that it
turns a raw graph result dict back into the right ChatResponse shape.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.api import chat as chat_module
from app.auth.dependencies import get_current_user
from app.main import app
from app.scoring.base import ScoreComponent, to_scored_result
from app.providers.places_provider import PlaceCandidate


class FakeGraph:
    """Records the config/input it was invoked with and returns a
    preprogrammed result. get_state_values/get_state_next control what
    graph.get_state(config) reports back (empty values == unknown thread,
    non-empty next == currently paused on an interrupt)."""

    def __init__(self, result=None, state_values=None, state_next=()):
        self.result = result if result is not None else {}
        self.state_values = state_values if state_values is not None else {}
        self.state_next = state_next
        self.ainvoke = AsyncMock(return_value=self.result)
        self.invoke_calls = []

    def get_state(self, config):
        return SimpleNamespace(values=self.state_values, next=self.state_next)


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


def _place(place_id="p1", name="Test Gym"):
    return PlaceCandidate(place_id=place_id, name=name, lat=1.0, lng=1.0)


def _scored(place_id="p1", name="Test Gym", score=0.9):
    component = ScoreComponent(factor="rating", score=score, weight=2.0, detail="Rated 4.5")
    return to_scored_result(item=_place(place_id, name), components=[component])


# ---- auth ----


def test_chat_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    response = client.post("/v1/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_resume_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    response = client.post("/v1/chat/s1/resume", json={"answer": "yes"})
    assert response.status_code == 401


# ---- /v1/chat: routing to the right graph input ----


def test_new_session_invokes_with_fresh_state(client, monkeypatch):
    fake = FakeGraph(result={"intent": "general", "explanation": "Hi there!"})
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat", json={"message": "hello"})

    assert response.status_code == 200
    graph_input, config = fake.ainvoke.call_args.args
    assert isinstance(graph_input, dict)
    assert graph_input["user_id"] == "test-user"
    assert graph_input["messages"][0].content == "hello"
    assert config["configurable"]["thread_id"]  # a session id was generated


def test_existing_paused_session_resumes_with_message(client, monkeypatch):
    fake = FakeGraph(
        result={"intent": "fitness", "explanation": "Done"},
        state_values={"user_id": "test-user"},
        state_next=("ask_user",),
    )
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat", json={"sessionId": "s1", "message": "yoga"})

    assert response.status_code == 200
    graph_input, config = fake.ainvoke.call_args.args
    assert isinstance(graph_input, Command)
    assert graph_input.resume == "yoga"
    assert config["configurable"]["thread_id"] == "s1"


def test_existing_unpaused_session_gets_turn_reset(client, monkeypatch):
    fake = FakeGraph(
        result={"intent": "general", "explanation": "ok"},
        state_values={"user_id": "test-user"},
        state_next=(),
    )
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat", json={"sessionId": "s1", "message": "what about parks"})

    assert response.status_code == 200
    graph_input, _config = fake.ainvoke.call_args.args
    assert isinstance(graph_input, dict)
    # identity fields must NOT be in the reset dict -- they should keep
    # whatever the checkpointer already has, not get clobbered
    assert "user_id" not in graph_input
    assert "session_id" not in graph_input
    assert "tool_call_budget" not in graph_input
    # volatile per-turn fields ARE reset to their fresh-state defaults
    assert graph_input["scored_results"] == []
    assert graph_input["errors"] == []
    assert graph_input["messages"][0].content == "what about parks"


def test_unknown_session_id_treated_as_new(client, monkeypatch):
    # Client sent a sessionId, but the checkpointer has never seen it
    # (empty snapshot.values) -- should NOT crash trying to turn-reset a
    # nonexistent session; should behave like a fresh start instead.
    fake = FakeGraph(result={"intent": "general", "explanation": "hi"}, state_values={}, state_next=())
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat", json={"sessionId": "ghost", "message": "hello"})

    assert response.status_code == 200
    graph_input, config = fake.ainvoke.call_args.args
    assert graph_input["user_id"] == "test-user"
    assert config["configurable"]["thread_id"] == "ghost"


# ---- /v1/chat response shape ----


def test_awaiting_input_response_includes_question(client, monkeypatch):
    fake = FakeGraph(result={"__interrupt__": (SimpleNamespace(value="Which neighborhood?"),)})
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat", json={"message": "find me a gym"})

    body = response.json()
    assert body["status"] == "awaiting_input"
    assert body["question"] == "Which neighborhood?"


def test_completed_response_includes_ranked_recommendations(client, monkeypatch):
    fake = FakeGraph(
        result={
            "intent": "fitness",
            "scored_results": [_scored("p1", "Gym A", 0.9), _scored("p2", "Gym B", 0.7)],
            "explanations": {"p1": "Great rating", "p2": "Decent option"},
        }
    )
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat", json={"message": "find me a gym"})

    body = response.json()
    assert body["status"] == "completed"
    assert len(body["recommendations"]) == 2
    assert body["recommendations"][0]["rank"] == 1
    assert body["recommendations"][0]["placeId"] == "p1"
    assert body["recommendations"][0]["explanation"] == "Great rating"
    assert body["recommendations"][0]["scoreBreakdown"] == {"rating": 0.9}


# ---- /v1/chat/{sessionId}/resume ----


def test_resume_404_for_unknown_session(client, monkeypatch):
    fake = FakeGraph(state_values={}, state_next=())
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat/ghost/resume", json={"answer": "yes"})

    assert response.status_code == 404


def test_resume_409_when_not_paused(client, monkeypatch):
    fake = FakeGraph(state_values={"user_id": "test-user"}, state_next=())
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat/s1/resume", json={"answer": "yes"})

    assert response.status_code == 409


def test_resume_success_sends_command_with_answer(client, monkeypatch):
    fake = FakeGraph(
        result={"intent": "fitness", "explanation": "done"},
        state_values={"user_id": "test-user"},
        state_next=("ask_user",),
    )
    monkeypatch.setattr(chat_module, "get_graph", lambda: fake)

    response = client.post("/v1/chat/s1/resume", json={"answer": "downtown"})

    assert response.status_code == 200
    graph_input, config = fake.ainvoke.call_args.args
    assert isinstance(graph_input, Command)
    assert graph_input.resume == "downtown"
    assert config["configurable"]["thread_id"] == "s1"


# ---- _turn_reset_input helper, directly ----


def test_turn_reset_input_wraps_message_as_human_message():
    reset = chat_module._turn_reset_input("new question")

    assert isinstance(reset["messages"][0], HumanMessage)
    assert reset["messages"][0].content == "new question"
    assert reset["missing_fields"] == []
    assert reset["explanations"] == {}
