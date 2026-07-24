"""
understand_request node (design doc Step 4) — the one place free text turns
into structured data. Claude classifies intent and extracts only the slots
the user's message explicitly states; everything else stays unset here.
Filling gaps from saved preferences happens in load_preferences, and asking
about anything still missing happens in ask_user (both M4.4) — this node
never guesses or defaults a value the user didn't actually say.

Field-naming note: this node's extraction schema (flat: budget_max_usd,
wants_wifi, ...) intentionally doesn't match UserPreferences' persisted
shape (nested: budgetBand, workspaceNeeds, ...) — this is "what did the user
just say this turn," a simple LLM-friendly shape. Translating/merging it
into UserPreferences is load_preferences' job, not this node's, per the
design doc's own node table ("merge with this-turn extraction").
"""
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agent.state import AgentState
from app.providers.llm_provider import LLMProvider

SYSTEM_PROMPT = """You are the request-understanding step of a relocation and \
routine copilot. Read the user's latest message and:

1. Classify its intent as exactly one of: fitness, workspace, route, \
weather, general, unclear.
   - fitness: gyms, studios, yoga, running/working out at a place
   - workspace: cafes, coworking spaces, libraries, somewhere to work
   - route: a running/walking route or path
   - weather: best time of day to be outside / weather-driven scheduling
   - general: anything else answerable without a search (greetings, \
questions about the app itself)
   - unclear: you cannot tell what the user wants

2. Extract ONLY the constraints the user's message explicitly states. \
Leave a field unset if the user did not mention it — never guess, infer, \
or fill in a plausible default. A user who says "find me a gym" has NOT \
stated a budget, travel time, or rating threshold, even if those would be \
reasonable assumptions to make later.
"""


class UnderstoodRequest(BaseModel):
    intent: Literal["fitness", "workspace", "route", "weather", "general", "unclear"]
    activities: list[str] = []
    budget_max_usd: float | None = None
    max_travel_minutes: int | None = None
    travel_mode: Literal["walk", "bike", "transit", "drive"] | None = None
    min_rating: float | None = None
    indoor_outdoor_preference: Literal["indoor", "outdoor", "either"] | None = None
    wants_wifi: bool | None = None
    wants_outlets: bool | None = None
    wants_quiet: bool | None = None


def _latest_user_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content
    return ""


async def understand_request(state: AgentState, llm: LLMProvider | None = None) -> dict:
    """Returns a partial state update — LangGraph merges this into the
    running state — rather than mutating `state` directly, per LangGraph's
    node contract. `llm` is injectable (defaults to a real LLMProvider) so
    this node's extraction/shaping logic can be unit-tested with a stub,
    without spending real API calls on every test run."""
    llm = llm or LLMProvider()
    user_text = _latest_user_text(state["messages"])

    understood = await llm.generate_structured(
        system=SYSTEM_PROMPT,
        user_message=user_text,
        output_model=UnderstoodRequest,
    )

    extracted = understood.model_dump(exclude={"intent"}, exclude_none=True)
    # An empty `activities` list means "nothing meaningfully extracted"
    # just as much as an unset field does elsewhere in this schema — drop
    # it too, so a bare [] doesn't get merged in and mistaken for an
    # explicit "no activities wanted."
    if not extracted.get("activities"):
        extracted.pop("activities", None)

    return {
        "intent": understood.intent,
        "extracted_preferences": extracted,
    }
