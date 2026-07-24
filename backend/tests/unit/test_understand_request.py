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


async def test_latest_human_message_is_used_even_with_prior_ai_turns():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [
        HumanMessage(content="find me a gym"),
        AIMessage(content="What's your budget?"),
        HumanMessage(content="under $60"),
    ]
    stub = _StubLLM(UnderstoodRequest(intent="fitness", budget_max_usd=60.0))

    await understand_request(state, llm=stub)

    assert stub.last_call_kwargs["user_message"] == "under $60"


async def test_unclear_intent_still_returns_a_valid_update():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["messages"] = [HumanMessage(content="hmm")]
    stub = _StubLLM(UnderstoodRequest(intent="unclear"))

    update = await understand_request(state, llm=stub)

    assert update["intent"] == "unclear"
    assert update["extracted_preferences"] == {}
