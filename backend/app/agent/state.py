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

Intent = Literal["fitness", "workspace", "route", "weather", "general", "unclear"]


class Location(TypedDict, total=False):
    lat: float
    lng: float
    formatted_address: str


class ApprovalRequest(TypedDict):
    """Populated by request_user_approval (Milestone 8 — calendar writes).
    Unused until then, but part of the state shape from the start per the
    note above."""

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
    resolved_location: Location | None
    saved_preferences: UserPreferences | None

    # tool results (raw, provider-shaped)
    places_results: list[PlaceCandidate]
    route_candidates: list[RouteCandidate]
    weather_data: list[HourlyForecast]
    calendar_freebusy: list[dict] | None

    # scoring/output
    scored_results: list[ScoredResult]
    explanation: str | None

    # control
    pending_approval: ApprovalRequest | None
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
        resolved_location=None,
        saved_preferences=None,
        places_results=[],
        route_candidates=[],
        weather_data=[],
        calendar_freebusy=None,
        scored_results=[],
        explanation=None,
        pending_approval=None,
        tool_call_count=0,
        tool_call_budget=tool_call_budget,
        errors=[],
        retry_counts={},
    )
