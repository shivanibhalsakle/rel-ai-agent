from langchain_core.messages import AIMessage

from app.agent.nodes.ask_user import generate_clarifying_question
from app.agent.state import new_agent_state


class _StubLLM:
    def __init__(self, text: str):
        self._text = text
        self.last_call_kwargs: dict | None = None

    async def generate_text(self, *, system, user_message, max_tokens=1024):
        self.last_call_kwargs = {"system": system, "user_message": user_message}
        return self._text


async def test_uses_known_field_description_for_the_prompt():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["missing_fields"] = ["activities"]
    stub = _StubLLM("What kind of activity are you looking for?")

    update = await generate_clarifying_question(state, llm=stub)

    assert "activity" in stub.last_call_kwargs["user_message"].lower()
    assert update["messages"] == [AIMessage(content="What kind of activity are you looking for?")]


async def test_unknown_missing_field_falls_back_to_the_raw_field_name():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["missing_fields"] = ["some_future_field"]
    stub = _StubLLM("Can you tell me more?")

    await generate_clarifying_question(state, llm=stub)

    assert "some_future_field" in stub.last_call_kwargs["user_message"]


async def test_only_the_first_missing_field_is_asked_about():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["missing_fields"] = ["activities", "intent"]
    stub = _StubLLM("Question about activities")

    await generate_clarifying_question(state, llm=stub)

    assert "activity" in stub.last_call_kwargs["user_message"].lower()
