from langchain_core.messages import AIMessage, HumanMessage

from app.agent.nodes.understand_request import UnderstoodRequest, understand_request
from app.agent.state import new_agent_state


class _StubLLM:
    """Stands in for LLMProvider so this node's own logic (message lookup,
    dict shaping) can be tested deterministically without a real, paid
    Claude call on every test run."""

    def __init__(self, response: UnderstoodRequest):
        self._response = response
        self.last_call_kwargs: dict | None = None

    async def generate_structured(self, *, system, user_message, output_model, max_tokens=1024):
        self.last_call_kwargs = {"system": system, "user_message": user_message, "output_model": output_model}
        return self._response


async def test_intent_and_explicit_fields_are_extracted():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="find me a yoga studio under $80/month within 15 min walk")]
    stub = _StubLLM(
        UnderstoodRequest(
            intent="fitness",
            activities=["yoga"],
            budget_max_usd=80.0,
            max_travel_minutes=15,
            travel_mode="walk",
        )
    )

    update = await understand_request(state, llm=stub)

    assert update["intent"] == "fitness"
    assert update["extracted_preferences"] == {
        "activities": ["yoga"],
        "budget_max_usd": 80.0,
        "max_travel_minutes": 15,
        "travel_mode": "walk",
    }


async def test_unmentioned_fields_are_absent_not_defaulted():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="find me a gym")]
    stub = _StubLLM(UnderstoodRequest(intent="fitness", activities=["gym"]))

    update = await understand_request(state, llm=stub)

    assert update["extracted_preferences"] == {"activities": ["gym"]}
    assert "budget_max_usd" not in update["extracted_preferences"]
    assert "min_rating" not in update["extracted_preferences"]


async def test_empty_activities_list_is_dropped_not_kept_as_empty_list():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="somewhere chill to work")]
    stub = _StubLLM(UnderstoodRequest(intent="workspace", wants_quiet=True))

    update = await understand_request(state, llm=stub)

    assert update["extracted_preferences"] == {"wants_quiet": True}
    assert "activities" not in update["extracted_preferences"]


async def test_conversation_context_includes_prior_turns_for_follow_up_answers():
    # A bare "under $60" is only interpretable with the preceding question
    # as context -- the call to Claude needs to see it, not just the
    # isolated latest message.
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [
        HumanMessage(content="find me a gym"),
        AIMessage(content="What's your budget?"),
        HumanMessage(content="under $60"),
    ]
    stub = _StubLLM(UnderstoodRequest(intent="fitness", budget_max_usd=60.0))

    await understand_request(state, llm=stub)

    sent = stub.last_call_kwargs["user_message"]
    assert "find me a gym" in sent
    assert "What's your budget?" in sent
    assert "under $60" in sent


async def test_extracted_preferences_merge_across_turns_instead_of_replacing():
    # First turn already extracted a budget; this turn's answer ("yoga")
    # only fills in activities and must not wipe the earlier budget.
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"budget_max_usd": 60.0}
    state["messages"] = [
        HumanMessage(content="find me a gym under $60"),
        AIMessage(content="What kind of activity?"),
        HumanMessage(content="yoga"),
    ]
    stub = _StubLLM(UnderstoodRequest(intent="fitness", activities=["yoga"]))

    update = await understand_request(state, llm=stub)

    assert update["extracted_preferences"] == {"budget_max_usd": 60.0, "activities": ["yoga"]}


async def test_new_turn_overrides_same_field_from_earlier_turn():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"budget_max_usd": 60.0}
    state["messages"] = [HumanMessage(content="actually make it under $40")]
    stub = _StubLLM(UnderstoodRequest(intent="fitness", budget_max_usd=40.0))

    update = await understand_request(state, llm=stub)

    assert update["extracted_preferences"] == {"budget_max_usd": 40.0}


async def test_location_is_returned_as_location_query_not_extracted_preferences():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="find me a gym near Union Square")]
    stub = _StubLLM(UnderstoodRequest(intent="fitness", activities=["gym"], location="Union Square"))

    update = await understand_request(state, llm=stub)

    assert update["location_query"] == "Union Square"
    assert "location" not in update["extracted_preferences"]


async def test_no_location_mentioned_omits_location_query_key_entirely():
    # Omitting the key (not setting it to None) matters: it means an
    # already-resolved location from an earlier turn survives this update.
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="find me a gym")]
    stub = _StubLLM(UnderstoodRequest(intent="fitness", activities=["gym"]))

    update = await understand_request(state, llm=stub)

    assert "location_query" not in update


async def test_route_distance_and_duration_targets_are_extracted():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="find me a 3 mile route near Prospect Park")]
    stub = _StubLLM(
        UnderstoodRequest(
            intent="route",
            location="Prospect Park",
            target_distance_meters=4828.0,
        )
    )

    update = await understand_request(state, llm=stub)

    assert update["extracted_preferences"] == {"target_distance_meters": 4828.0}


async def test_route_with_no_stated_target_extracts_neither_field():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="find me a nice route to run")]
    stub = _StubLLM(UnderstoodRequest(intent="route"))

    update = await understand_request(state, llm=stub)

    assert update["extracted_preferences"] == {}
    assert "target_distance_meters" not in update["extracted_preferences"]
    assert "target_duration_seconds" not in update["extracted_preferences"]


async def test_unclear_intent_still_returns_a_valid_update():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="hmm")]
    stub = _StubLLM(UnderstoodRequest(intent="unclear"))

    update = await understand_request(state, llm=stub)

    assert update["intent"] == "unclear"
    assert update["extracted_preferences"] == {}
