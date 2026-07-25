import time

import pytest

from app.agent.nodes.create_calendar_event import ApprovalNotConfirmedError, calendar_rejected, create_calendar_event
from app.agent.state import new_agent_state
from app.providers.calendar_provider import CalendarTokens

_PAYLOAD = {
    "title": "Time outside",
    "start": "2026-07-25T17:00:00+00:00",
    "end": "2026-07-25T18:00:00+00:00",
    "location": "Prospect Park, Brooklyn, NY",
}


class _StubActions:
    def __init__(self):
        self.confirmed: list[tuple] = []
        self.created: list[tuple] = []
        self.failed: list[tuple] = []
        self._next_id = "action-1"

    def record_confirmed(self, uid, payload):
        self.confirmed.append((uid, payload))
        return self._next_id

    def mark_created(self, uid, action_id, event_id):
        self.created.append((uid, action_id, event_id))

    def mark_failed(self, uid, action_id, reason):
        self.failed.append((uid, action_id, reason))


class _StubRepo:
    def __init__(self, tokens: CalendarTokens | None):
        self._tokens = tokens
        self.saved: list[tuple] = []

    def get_tokens(self, uid):
        return self._tokens

    def save_tokens(self, uid, tokens):
        self.saved.append((uid, tokens))
        self._tokens = tokens


class _StubProvider:
    def __init__(self, event_id="gcal-event-1", raises=None, refreshed=None):
        self._event_id = event_id
        self._raises = raises
        self._refreshed = refreshed
        self.create_called_with = None
        self.refresh_called = False

    async def refresh(self, refresh_token):
        self.refresh_called = True
        return self._refreshed

    async def create_event(self, access_token, title, start, end, location=None, calendar_id="primary"):
        self.create_called_with = (access_token, title, start, end, location)
        if self._raises:
            raise self._raises
        return self._event_id


def _state():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["pending_approval"] = {"kind": "calendar_event", "payload": _PAYLOAD}
    # Realistic precondition for every test below except the guard test
    # itself -- create_calendar_event is never reached with this unset
    # (see M8.8's ApprovalNotConfirmedError guard).
    state["approval_decision"] = True
    return state


def _valid_tokens():
    return CalendarTokens(access_token="access-1", refresh_token="refresh-1", expires_at=time.time() + 3600)


def test_calendar_rejected_sets_a_declined_message():
    update = calendar_rejected(new_agent_state(user_id="u1", session_id="s1"))

    assert "won't add" in update["explanation"]


# ---- M8.8: the write is impossible without a confirmed approval_decision,
# ---- enforced by the node itself, not only by how the graph happens to
# ---- be wired (see create_calendar_event.py's module docstring). ----


async def test_refuses_to_create_without_a_confirmed_approval_decision():
    actions = _StubActions()
    repo = _StubRepo(_valid_tokens())
    provider = _StubProvider()

    state = _state()
    state["approval_decision"] = False  # the one precondition every other test in this file sets to True

    with pytest.raises(ApprovalNotConfirmedError):
        await create_calendar_event(state, provider=provider, repo=repo, actions=actions)

    # Nothing happened -- no Firestore audit record, no provider call.
    # This is the concrete "no code path" proof: even handed a fully
    # valid pending_approval payload, the function will not act on it
    # without approval_decision also being True.
    assert actions.confirmed == []
    assert provider.create_called_with is None


async def test_refuses_to_create_when_approval_decision_was_never_set():
    # A state that never went through request_user_approval at all --
    # approval_decision defaults to None (new_agent_state), not False.
    # Both are "not confirmed" and both must refuse.
    actions = _StubActions()
    repo = _StubRepo(_valid_tokens())
    provider = _StubProvider()

    state = new_agent_state(user_id="u1", session_id="s1")
    state["pending_approval"] = {"kind": "calendar_event", "payload": _PAYLOAD}
    assert state["approval_decision"] is None

    with pytest.raises(ApprovalNotConfirmedError):
        await create_calendar_event(state, provider=provider, repo=repo, actions=actions)

    assert actions.confirmed == []
    assert provider.create_called_with is None


async def test_creates_the_event_and_marks_the_action_created():
    actions = _StubActions()
    repo = _StubRepo(_valid_tokens())
    provider = _StubProvider(event_id="gcal-event-1")

    update = await create_calendar_event(_state(), provider=provider, repo=repo, actions=actions)

    assert actions.confirmed == [("u1", _PAYLOAD)]
    assert actions.created == [("u1", "action-1", "gcal-event-1")]
    assert actions.failed == []
    assert provider.create_called_with == (
        "access-1",
        "Time outside",
        "2026-07-25T17:00:00+00:00",
        "2026-07-25T18:00:00+00:00",
        "Prospect Park, Brooklyn, NY",
    )
    assert "Added to your calendar" in update["explanation"]


async def test_disconnected_calendar_marks_failed_without_calling_the_provider():
    actions = _StubActions()
    repo = _StubRepo(None)
    provider = _StubProvider()

    update = await create_calendar_event(_state(), provider=provider, repo=repo, actions=actions)

    assert provider.create_called_with is None
    assert actions.created == []
    assert len(actions.failed) == 1
    assert "disconnected" in update["explanation"]


async def test_expired_token_is_refreshed_before_creating_the_event():
    expired = CalendarTokens(access_token="old", refresh_token="refresh-1", expires_at=time.time() - 10)
    refreshed = CalendarTokens(access_token="new-access", refresh_token="refresh-1", expires_at=time.time() + 3600)
    repo = _StubRepo(expired)
    actions = _StubActions()
    provider = _StubProvider(refreshed=refreshed)

    await create_calendar_event(_state(), provider=provider, repo=repo, actions=actions)

    assert provider.refresh_called
    assert repo.saved == [("u1", refreshed)]
    assert provider.create_called_with[0] == "new-access"


async def test_provider_error_marks_failed_and_reports_honestly():
    actions = _StubActions()
    repo = _StubRepo(_valid_tokens())
    provider = _StubProvider(raises=RuntimeError("Calendar API unavailable"))

    update = await create_calendar_event(_state(), provider=provider, repo=repo, actions=actions)

    assert actions.created == []
    assert actions.failed == [("u1", "action-1", "Calendar API unavailable")]
    assert "couldn't add" in update["explanation"]
