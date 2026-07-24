"""
LangGraph agent state (design doc Step 4). This is the shared "memory" every
node in the graph reads from and writes back to.

Scope note for Milestone 4: only fitness/workspace intents get real node
implementations this milestone (route/weather join in Milestone 6, calendar
in Milestone 8). The state shape below already includes fields for all of
that — route_candidates, weather_data, pending_approval — so the shape
doesn't need a breaking change later; those fields just stay empty/None
until the milestones that populate them exist. Building the narrower shape
now and widening it later would mean migrating whatever's already in the
checkpointer, which is exactly the kind of churn this avoids.
"""
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.providers.places_provider import PlaceCandidate
from app.providers.weather_provider import HourlyForecast
from app.schemas.preferences import UserPreferences
from app.scoring.base import ScoredResult
from app.scoring.route_scoring import RouteCandidate

Intent = Literal["fitness", "workspace", "route", "weather", "add_to_calendar", "general", "unclear"]


class Location(TypedDict, total=False):
    lat: float
    lng: float
    formatted_address: str


class ApprovalRequest(TypedDict):
    """Populated by prepare_calendar_proposal, read by request_user_approval
    and create_calendar_event (Milestone 8 -- calendar writes)."""

    kind: Literal["calendar_event"]
    payload: dict


class ProviderError(TypedDict):
    node: str
    message: str
    retryable: bool


class AgentState(TypedDict):
    # conversation
    # Annotated with LangGraph's add_messages reducer: without it, a node
    # returning {"messages": [new_msg]} would REPLACE the whole list
    # (LangGraph's default merge behavior for a field with no reducer is
    # last-write-wins), wiping prior turns. add_messages appends instead
    # (and de-duplicates by message id), which is what every node in this
    # graph assumes when it returns just the new message(s), not the full
    # history.
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    session_id: str

    # intent & extraction
    intent: Intent
    extracted_preferences: dict
    missing_fields: list[str]

    # resolved context
    # location_query: added beyond the design doc's original listing. The
    # design doc assumed a home location would already be on file from
    # onboarding (users/{userId}.homeLocation), but M1 never actually built
    # that capture (onboarding only stores UserPreferences, no home
    # location) -- rather than retrofit onboarding, M4.5 captures location
    # conversationally instead (the raw text understand_request extracts,
    # e.g. "Union Square"), which geocode_location resolves into
    # resolved_location. Arguably a better fit for a chat-first product
    # anyway, per the design doc's own fallback framing ("ask for manual
    # address/neighborhood entry").
    location_query: str | None
    resolved_location: Location | None
    saved_preferences: UserPreferences | None

    # tool results (raw, provider-shaped)
    places_results: list[PlaceCandidate]
    # workspace_amenities: added beyond the design doc's original listing.
    # Output of fetch_place_details' selective review-mining (M4.5) --
    # {place_id: {amenity: bool}}, in exactly the shape
    # workspace_scoring.score_and_rank's `amenities` param expects (M3).
    workspace_amenities: dict[str, dict[str, bool]]
    route_candidates: list[RouteCandidate]
    weather_data: list[HourlyForecast]
    calendar_freebusy: list[dict] | None

    # scoring/output
    # last_weather_recommendation: added for M8.5 ("add to calendar" as a
    # follow-up user message). Deliberately NOT reset every turn the way
    # scored_results/explanations are (see app/api/chat.py's
    # _PER_TURN_RESET_FIELDS) -- a later turn's "add that to my calendar"
    # message needs to still find the weather pick that turn's own
    # scored_results has long since been wiped for. Set by
    # score_recommendations whenever intent is "weather" and it produced a
    # top result; read by prepare_calendar_proposal. A minimal snapshot
    # (title/start/end/location), not the full HourlyForecast/ScoredResult
    # -- everything else about that result is irrelevant to building a
    # calendar event.
    last_weather_recommendation: dict | None
    scored_results: list[ScoredResult]
    # explanations: added beyond the design doc's original listing. The
    # design doc's node table describes generate_explanation producing "a
    # natural-language explanation per item" -- plural -- but AgentState's
    # original `explanation: str | None` is singular, which only fits one
    # case: a direct conversational reply for "general" intent (no search,
    # nothing to attach a per-item explanation to). Per-recommendation
    # sentences live here instead, keyed by place_id, so M4.10 can zip them
    # with scored_results when building the API response.
    explanations: dict[str, str]
    explanation: str | None

    # control
    pending_approval: ApprovalRequest | None
    # approval_decision: added for M8.5. Set ONLY by request_user_approval,
    # from the value its interrupt() call resumes with -- this is the
    # single field the design doc's "structurally impossible to bypass"
    # requirement hinges on: create_calendar_event is reached by exactly
    # one conditional edge (_route_after_approval, agent/graph.py), which
    # reads this field and nothing else. No other node in the graph ever
    # sets it. Per-turn-reset (see _PER_TURN_RESET_FIELDS) so a stale
    # True from an earlier turn's approval can never leak into a new,
    # unrelated turn.
    approval_decision: bool | None
    tool_call_count: int
    tool_call_budget: int
    errors: list[ProviderError]
    retry_counts: dict[str, int]


DEFAULT_TOOL_CALL_BUDGET = 8
# ^ design doc's example figure (Step 4, "Retries, approval points, error
# states, persistence") — enough for a real fitness/workspace turn
# (geocode + search + a couple of selective Details fetches) with headroom
# for one retry, without letting a confused extraction loop indefinitely.


def new_agent_state(
    user_id: str,
    session_id: str,
    tool_call_budget: int = DEFAULT_TOOL_CALL_BUDGET,
) -> AgentState:
    """Build a fresh AgentState for the start of a session. TypedDicts don't
    carry default values themselves, so this is the one place those
    defaults are decided — every node can assume these fields exist rather
    than checking for missing keys."""
    return AgentState(
        messages=[],
        user_id=user_id,
        session_id=session_id,
        intent="unclear",
        extracted_preferences={},
        missing_fields=[],
        location_query=None,
        resolved_location=None,
        saved_preferences=None,
        places_results=[],
        workspace_amenities={},
        route_candidates=[],
        weather_data=[],
        calendar_freebusy=None,
        last_weather_recommendation=None,
        scored_results=[],
        explanations={},
        explanation=None,
        pending_approval=None,
        approval_decision=None,
        tool_call_count=0,
        tool_call_budget=tool_call_budget,
        errors=[],
        retry_counts={},
    )
