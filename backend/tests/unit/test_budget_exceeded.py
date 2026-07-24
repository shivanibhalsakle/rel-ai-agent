from app.agent.nodes.budget_exceeded import budget_exceeded
from app.agent.state import new_agent_state


def test_returns_a_narrow_your_request_message():
    state = new_agent_state(user_id="u1", session_id="s1")

    update = budget_exceeded(state)

    assert "narrow" in update["explanation"].lower()
