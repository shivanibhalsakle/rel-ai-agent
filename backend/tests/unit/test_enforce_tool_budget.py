from app.agent.nodes.enforce_tool_budget import check_tool_budget, is_within_budget
from app.agent.state import new_agent_state


def test_check_tool_budget_increments_count():
    state = new_agent_state(user_id="u1", session_id="s1", tool_call_budget=5)

    update = check_tool_budget(state)

    assert update["tool_call_count"] == 1


def test_is_within_budget_true_below_limit():
    state = new_agent_state(user_id="u1", session_id="s1", tool_call_budget=5)
    state["tool_call_count"] = 3

    assert is_within_budget(state) is True


def test_is_within_budget_true_exactly_at_limit():
    state = new_agent_state(user_id="u1", session_id="s1", tool_call_budget=5)
    state["tool_call_count"] = 5

    assert is_within_budget(state) is True


def test_is_within_budget_false_over_limit():
    state = new_agent_state(user_id="u1", session_id="s1", tool_call_budget=5)
    state["tool_call_count"] = 6

    assert is_within_budget(state) is False


def test_repeated_increments_eventually_exceed_budget():
    state = new_agent_state(user_id="u1", session_id="s1", tool_call_budget=2)

    for _ in range(3):
        state["tool_call_count"] = check_tool_budget(state)["tool_call_count"]

    assert state["tool_call_count"] == 3
    assert is_within_budget(state) is False
