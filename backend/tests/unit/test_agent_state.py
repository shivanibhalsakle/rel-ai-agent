from app.agent.state import DEFAULT_TOOL_CALL_BUDGET, new_agent_state


def test_new_agent_state_sets_expected_defaults():
    state = new_agent_state(user_id="user-1", session_id="sess-1")

    assert state["user_id"] == "user-1"
    assert state["session_id"] == "sess-1"
    assert state["intent"] == "unclear"
    assert state["messages"] == []
    assert state["missing_fields"] == []
    assert state["places_results"] == []
    assert state["location_query"] is None
    assert state["workspace_amenities"] == {}
    assert state["route_candidates"] == []
    assert state["weather_data"] == []
    assert state["scored_results"] == []
    assert state["errors"] == []
    assert state["retry_counts"] == {}
    assert state["resolved_location"] is None
    assert state["saved_preferences"] is None
    assert state["pending_approval"] is None
    assert state["explanation"] is None
    assert state["tool_call_count"] == 0
    assert state["tool_call_budget"] == DEFAULT_TOOL_CALL_BUDGET


def test_new_agent_state_accepts_custom_tool_call_budget():
    state = new_agent_state(user_id="user-1", session_id="sess-1", tool_call_budget=3)

    assert state["tool_call_budget"] == 3
