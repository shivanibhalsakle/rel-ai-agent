from app.agent.nodes.not_yet_supported import not_yet_supported
from app.agent.state import new_agent_state


def test_route_intent_gets_a_route_specific_message():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "route"

    update = not_yet_supported(state)

    assert "route" in update["explanation"].lower()


def test_weather_intent_gets_a_weather_specific_message():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "weather"

    update = not_yet_supported(state)

    assert "weather" in update["explanation"].lower()
