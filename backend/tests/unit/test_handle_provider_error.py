from app.agent.nodes.handle_provider_error import handle_provider_error, has_error, route_after_error
from app.agent.state import new_agent_state


def _with_error(node: str, retryable: bool, retry_counts: dict | None = None):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["errors"] = [{"node": node, "message": "boom", "retryable": retryable}]
    state["retry_counts"] = retry_counts or {}
    return state


def test_no_errors_is_a_no_op():
    state = new_agent_state(user_id="u1", session_id="s1")

    update = handle_provider_error(state)

    assert update == {}


def test_retryable_error_with_no_prior_attempts_schedules_a_retry():
    state = _with_error("geocode_location", retryable=True)

    update = handle_provider_error(state)

    assert update["errors"] == []
    assert update["retry_counts"] == {"geocode_location": 1}


def test_retryable_error_already_at_max_retries_gives_up():
    state = _with_error("geocode_location", retryable=True, retry_counts={"geocode_location": 1})

    update = handle_provider_error(state)

    assert update == {}


def test_non_retryable_error_gives_up_immediately():
    state = _with_error("search_places", retryable=False)

    update = handle_provider_error(state)

    assert update == {}


def test_only_the_failing_nodes_retry_count_is_touched():
    state = _with_error("geocode_location", retryable=True, retry_counts={"search_places": 1})

    update = handle_provider_error(state)

    assert update["retry_counts"] == {"search_places": 1, "geocode_location": 1}


def test_route_after_error_retries_when_the_error_was_cleared():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["errors"] = []  # handle_provider_error already removed it

    assert route_after_error(state, failed_node="geocode_location") == "retry"


def test_route_after_error_degrades_when_the_error_is_still_present():
    state = _with_error("geocode_location", retryable=False)

    assert route_after_error(state, failed_node="geocode_location") == "degrade"


def test_route_after_error_only_matches_the_specific_failed_node():
    # A different node's error is present -- shouldn't count as "still
    # failing" for the node this edge is guarding.
    state = _with_error("search_places", retryable=False)

    assert route_after_error(state, failed_node="geocode_location") == "retry"


def test_has_error_true_when_errors_present():
    state = _with_error("geocode_location", retryable=False)

    assert has_error(state) is True


def test_has_error_false_when_no_errors():
    state = new_agent_state(user_id="u1", session_id="s1")

    assert has_error(state) is False
