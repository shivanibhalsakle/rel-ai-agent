"""
Assembles the LangGraph StateGraph for Milestone 4 (fitness + workspace
discovery via chat). Wires together every node built in M4.1-4.8 following
the design doc's Step 4 control-flow diagram, deliberately scoped down to
what M4 actually builds:

- route/weather intents are recognized (understand_request classifies
  them) but have no search/score pipeline yet (Milestone 6) -- routed to
  not_yet_supported instead of silently falling through to an empty
  result.
- present_results, the accept/reject feedback loop, and calendar approval
  (Milestones 7-8) aren't graph nodes here -- the graph simply ends after
  generate_explanation, and the API layer (M4.10) formats the final state
  into the /v1/chat response shape.
- Only geocode_location and search_places get retry/degrade error routing
  -- they're the two nodes with structured ProviderError reporting today.
  fetch_place_details' internal per-candidate review fetches aren't
  individually retried or reported as errors; a failure there just means
  fewer amenity signals for that turn, not a broken one. Documented
  simplification, not a silent gap.
- Tool-budget gating (check_tool_budget + is_within_budget) sits before
  geocode_location, search_places, and fetch_place_details as three
  separate node instances of the same function. fetch_place_details' own
  internal loop (up to 5 review fetches, see SHORTLIST_SIZE) counts as ONE
  gated call, not five -- decomposing it into a per-candidate subgraph for
  individually-gated calls is more complexity than M4's fitness/
  workspace-only scope justifies.
- The missing-info clarification loop (ask_user -> understand_request ->
  check_missing_info) isn't bounded by tool_call_budget the way the design
  doc's refine-query loop is, since asking a clarifying question isn't a
  provider tool call. It's naturally self-limiting today given how few
  fields check_missing_info can ask about (activities, location) -- an
  explicit turn counter is a documented candidate for later hardening if
  real usage ever shows a runaway loop, not something built preemptively
  here.

Checkpointer: in-memory (InMemorySaver), per the design doc's explicit
"start with an in-memory or Firestore-backed checkpointer" -- sufficient
for dev/testing and required for interrupt()/Command(resume=...) to work
at all. A durable (Firestore-backed) checkpointer is a documented future
upgrade: in-memory state is lost on process restart, which is fine for
now but would drop an in-progress paused session in production.
"""
from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes.ask_user import ask_user, generate_clarifying_question
from app.agent.nodes.budget_exceeded import budget_exceeded
from app.agent.nodes.check_missing_info import check_missing_info
from app.agent.nodes.enforce_tool_budget import check_tool_budget, is_within_budget
from app.agent.nodes.fetch_place_details import fetch_place_details
from app.agent.nodes.generate_explanation import generate_explanation
from app.agent.nodes.geocode_location import geocode_location
from app.agent.nodes.handle_provider_error import handle_provider_error, has_error, route_after_error
from app.agent.nodes.load_preferences import load_preferences
from app.agent.nodes.not_yet_supported import not_yet_supported
from app.agent.nodes.score_recommendations import score_recommendations
from app.agent.nodes.search_places import search_places
from app.agent.nodes.understand_request import understand_request
from app.agent.state import AgentState

_SEARCH_INTENTS = ("fitness", "workspace")
_UNBUILT_INTENTS = ("route", "weather")


def _route_after_missing_info(state: AgentState) -> str:
    """Combines two sequential decisions (design doc: check_missing_info's
    branch, then route_by_intent) into one routing function, since no node
    needs to run in between them."""
    if state["missing_fields"]:
        return "generate_clarifying_question"
    intent = state["intent"]
    if intent in _SEARCH_INTENTS:
        return "check_budget_geocode"
    if intent in _UNBUILT_INTENTS:
        return "not_yet_supported"
    return "generate_explanation"  # general (and defensively, anything else)


def _budget_gate(proceed_to: str):
    """Returns a routing function for the conditional edge right after a
    check_tool_budget node instance -- proceeds to `proceed_to` if under
    budget, otherwise short-circuits to budget_exceeded."""

    def _route(state: AgentState) -> str:
        return proceed_to if is_within_budget(state) else "budget_exceeded"

    return _route


def _route_after_geocode(state: AgentState) -> str:
    return "handle_geocode_error" if has_error(state) else "check_budget_search"


def _route_after_geocode_error(state: AgentState) -> str:
    decision = route_after_error(state, failed_node="geocode_location")
    return "geocode_location" if decision == "retry" else "generate_explanation"


def _route_after_search(state: AgentState) -> str:
    return "handle_search_error" if has_error(state) else "check_budget_details"


def _route_after_search_error(state: AgentState) -> str:
    decision = route_after_error(state, failed_node="search_places")
    return "search_places" if decision == "retry" else "generate_explanation"


def build_graph():
    """Compiles a fresh graph instance with its own InMemorySaver. Use
    get_graph() (below) for the shared, process-wide instance the API layer
    should actually call -- a fresh instance per call would mean every
    request gets its own empty checkpointer, breaking resume."""
    builder = StateGraph(AgentState)

    builder.add_node("understand_request", understand_request)
    builder.add_node("load_preferences", load_preferences)
    builder.add_node("check_missing_info", check_missing_info)
    builder.add_node("generate_clarifying_question", generate_clarifying_question)
    builder.add_node("ask_user", ask_user)
    builder.add_node("not_yet_supported", not_yet_supported)
    builder.add_node("budget_exceeded", budget_exceeded)
    builder.add_node("check_budget_geocode", check_tool_budget)
    builder.add_node("geocode_location", geocode_location)
    builder.add_node("handle_geocode_error", handle_provider_error)
    builder.add_node("check_budget_search", check_tool_budget)
    builder.add_node("search_places", search_places)
    builder.add_node("handle_search_error", handle_provider_error)
    builder.add_node("check_budget_details", check_tool_budget)
    builder.add_node("fetch_place_details", fetch_place_details)
    builder.add_node("score_recommendations", score_recommendations)
    builder.add_node("generate_explanation", generate_explanation)

    builder.add_edge(START, "understand_request")
    builder.add_edge("understand_request", "load_preferences")
    builder.add_edge("load_preferences", "check_missing_info")

    builder.add_conditional_edges(
        "check_missing_info",
        _route_after_missing_info,
        {
            "generate_clarifying_question": "generate_clarifying_question",
            "check_budget_geocode": "check_budget_geocode",
            "not_yet_supported": "not_yet_supported",
            "generate_explanation": "generate_explanation",
        },
    )
    builder.add_edge("generate_clarifying_question", "ask_user")
    builder.add_edge("ask_user", "understand_request")  # loop -- see module docstring
    builder.add_edge("not_yet_supported", END)

    builder.add_conditional_edges(
        "check_budget_geocode",
        _budget_gate("geocode_location"),
        {"geocode_location": "geocode_location", "budget_exceeded": "budget_exceeded"},
    )
    builder.add_conditional_edges(
        "geocode_location",
        _route_after_geocode,
        {"handle_geocode_error": "handle_geocode_error", "check_budget_search": "check_budget_search"},
    )
    builder.add_conditional_edges(
        "handle_geocode_error",
        _route_after_geocode_error,
        {"geocode_location": "geocode_location", "generate_explanation": "generate_explanation"},
    )

    builder.add_conditional_edges(
        "check_budget_search",
        _budget_gate("search_places"),
        {"search_places": "search_places", "budget_exceeded": "budget_exceeded"},
    )
    builder.add_conditional_edges(
        "search_places",
        _route_after_search,
        {"handle_search_error": "handle_search_error", "check_budget_details": "check_budget_details"},
    )
    builder.add_conditional_edges(
        "handle_search_error",
        _route_after_search_error,
        {"search_places": "search_places", "generate_explanation": "generate_explanation"},
    )

    builder.add_conditional_edges(
        "check_budget_details",
        _budget_gate("fetch_place_details"),
        {"fetch_place_details": "fetch_place_details", "budget_exceeded": "budget_exceeded"},
    )
    builder.add_edge("fetch_place_details", "score_recommendations")
    builder.add_edge("score_recommendations", "generate_explanation")

    builder.add_edge("budget_exceeded", END)
    builder.add_edge("generate_explanation", END)

    return builder.compile(checkpointer=InMemorySaver())


@lru_cache
def get_graph():
    """Process-wide compiled graph, built once and reused across requests
    so its InMemorySaver actually accumulates session checkpoints instead
    of starting empty every call. This is what app/api/chat.py (M4.10)
    should import."""
    return build_graph()
