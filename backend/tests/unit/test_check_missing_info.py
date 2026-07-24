from app.agent.nodes.check_missing_info import check_missing_info
from app.agent.state import new_agent_state
from app.schemas.preferences import UserPreferences


def _state(intent: str, preferences: UserPreferences | None = None):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = intent
    state["saved_preferences"] = preferences or UserPreferences()
    return state


def test_unclear_intent_reports_intent_itself_as_missing():
    state = _state("unclear")

    update = check_missing_info(state)

    assert update["missing_fields"] == ["intent"]


def test_fitness_missing_activities():
    state = _state("fitness", UserPreferences(activities=[]))
    state["location_query"] = "Union Square"  # isolate the activities check from the location check

    update = check_missing_info(state)

    assert update["missing_fields"] == ["activities"]


def test_fitness_with_activities_has_nothing_missing():
    state = _state("fitness", UserPreferences(activities=["gym"]))
    state["location_query"] = "Union Square"

    update = check_missing_info(state)

    assert update["missing_fields"] == []


def test_workspace_never_reports_missing_fields():
    state = _state("workspace", UserPreferences())
    state["location_query"] = "Brooklyn"

    update = check_missing_info(state)

    assert update["missing_fields"] == []


def test_missing_location_is_reported_after_missing_activities():
    state = _state("fitness", UserPreferences(activities=[]))
    # no location_query, no resolved_location set

    update = check_missing_info(state)

    assert update["missing_fields"] == ["activities", "location"]


def test_location_query_present_satisfies_the_location_check():
    state = _state("fitness", UserPreferences(activities=["gym"]))
    state["location_query"] = "Union Square"

    update = check_missing_info(state)

    assert update["missing_fields"] == []


def test_resolved_location_also_satisfies_the_location_check():
    state = _state("workspace", UserPreferences())
    state["resolved_location"] = {"lat": 40.7, "lng": -73.9, "formatted_address": "NYC"}

    update = check_missing_info(state)

    assert update["missing_fields"] == []
