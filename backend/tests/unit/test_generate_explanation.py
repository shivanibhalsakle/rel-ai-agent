from langchain_core.messages import HumanMessage

from app.agent.nodes.generate_explanation import _ExplanationBatch, generate_explanation
from app.agent.state import new_agent_state
from app.providers.places_provider import PlaceCandidate
from app.scoring.base import ScoreComponent, to_scored_result


class _StubLLM:
    def __init__(self, structured_response=None, text_response: str | None = None):
        self._structured_response = structured_response
        self._text_response = text_response
        self.structured_call: dict | None = None
        self.text_call: dict | None = None

    async def generate_structured(self, *, system, user_message, output_model, max_tokens=1024):
        self.structured_call = {"system": system, "user_message": user_message}
        return self._structured_response

    async def generate_text(self, *, system, user_message, max_tokens=1024):
        self.text_call = {"system": system, "user_message": user_message}
        return self._text_response


def _scored(place_id: str, facts: list[str]):
    candidate = PlaceCandidate(place_id=place_id, name=place_id, lat=0.0, lng=0.0)
    components = [ScoreComponent(factor=f"f{i}", score=1.0, weight=1, detail=fact) for i, fact in enumerate(facts)]
    return to_scored_result(item=candidate, components=components)


async def test_general_intent_generates_a_direct_reply_not_per_item_explanations():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "general"
    state["messages"] = [HumanMessage(content="what can you help with?")]
    stub = _StubLLM(text_response="I can help you find gyms, workspaces, routes, and good weather windows.")

    update = await generate_explanation(state, llm=stub)

    assert update == {"explanation": "I can help you find gyms, workspaces, routes, and good weather windows."}
    assert stub.text_call["user_message"] == "what can you help with?"


async def test_fitness_intent_produces_per_item_explanations_keyed_by_place_id():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"
    state["scored_results"] = [_scored("p1", ["4.9★ rating", "8 min away"])]
    stub = _StubLLM(structured_response=_ExplanationBatch(explanations=["A great, close-by option."]))

    update = await generate_explanation(state, llm=stub)

    assert update["explanations"] == {"p1": "A great, close-by option."}
    assert "4.9★ rating" in stub.structured_call["user_message"]
    assert "8 min away" in stub.structured_call["user_message"]


async def test_empty_scored_results_returns_empty_explanations_without_calling_llm():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "workspace"
    state["scored_results"] = []
    stub = _StubLLM()

    update = await generate_explanation(state, llm=stub)

    assert update == {"explanations": {}}
    assert stub.structured_call is None


async def test_only_top_n_results_are_sent_to_the_llm():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"
    state["scored_results"] = [_scored(f"p{i}", [f"fact {i}"]) for i in range(8)]
    stub = _StubLLM(structured_response=_ExplanationBatch(explanations=["x"] * 5))

    await generate_explanation(state, llm=stub)

    sent = stub.structured_call["user_message"]
    assert sent.count("- p") == 5


async def test_unresolved_error_with_no_results_produces_an_honest_message():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"
    state["scored_results"] = []
    state["errors"] = [{"node": "geocode_location", "message": 'Could not find a location for "asdkfjh".', "retryable": False}]
    stub = _StubLLM()

    update = await generate_explanation(state, llm=stub)

    assert update == {"explanation": 'I couldn\'t complete that search: Could not find a location for "asdkfjh".'}
    assert stub.structured_call is None


async def test_fewer_explanations_than_items_does_not_crash():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"
    state["scored_results"] = [_scored("p1", ["fact"]), _scored("p2", ["fact"])]
    # Claude only returned one explanation for two items.
    stub = _StubLLM(structured_response=_ExplanationBatch(explanations=["only one"]))

    update = await generate_explanation(state, llm=stub)

    assert update["explanations"] == {"p1": "only one"}
