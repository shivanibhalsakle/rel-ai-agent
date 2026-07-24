from app.agent.nodes.prepare_calendar_proposal import prepare_calendar_proposal
from app.agent.state import new_agent_state


class _StubRepo:
    def __init__(self, connected: bool):
        self._connected = connected

    def is_connected(self, uid):
        return self._connected


_RECOMMENDATION = {
    "title": "Time outside",
    "start": "2026-07-25T17:00:00+00:00",
    "end": "2026-07-25T18:00:00+00:00",
    "location": "Prospect Park, Brooklyn, NY",
}


def _state(recommendation=None):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "add_to_calendar"
    state["last_weather_recommendation"] = recommendation
    return state


def test_no_recent_weather_recommendation_degrades_with_no_pending_approval():
    update = prepare_calendar_proposal(_state(None), repo=_StubRepo(True))

    assert "pending_approval" not in update
    assert "add me to your calendar" not in update["explanation"]  # sanity: not a garbled message
    assert "ask me for the best time" in update["explanation"]


def test_not_connected_degrades_with_no_pending_approval():
    update = prepare_calendar_proposal(_state(_RECOMMENDATION), repo=_StubRepo(False))

    assert "pending_approval" not in update
    assert "Settings" in update["explanation"]


def test_connected_with_recommendation_builds_pending_approval():
    update = prepare_calendar_proposal(_state(_RECOMMENDATION), repo=_StubRepo(True))

    assert "explanation" not in update
    assert update["pending_approval"] == {
        "kind": "calendar_event",
        "payload": {
            "title": "Time outside",
            "start": "2026-07-25T17:00:00+00:00",
            "end": "2026-07-25T18:00:00+00:00",
            "location": "Prospect Park, Brooklyn, NY",
        },
    }
