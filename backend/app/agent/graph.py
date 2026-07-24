"""
Assembles the LangGraph StateGraph for Milestone 4 (fitness + workspace
discovery via chat) plus Milestone 6 (route + weather). Wires together
every node built in M4.1-4.8 and M6.1-M6.4 following the design doc's
Step 4 control-flow diagram.

- Route/weather now have real pipelines (M6): after geocode_location
  succeeds, the graph branches by intent to either check_budget_search
  (fitness/workspace, unchanged from M4) or check_budget_route /
  check_budget_weather (M6), each gating exactly one tool node
  (generate_route_candidates / fetch_weather_forecast) the same way
  check_budget_details gates fetch_place_details. All four intents
  converge back on the same score_recommendations -> generate_explanation
  tail.
- Neither generate_route_candidates nor fetch_weather_forecast gets its
  own handle_provider_error retry/degrade routing, mirroring
  fetch_place_details' precedent (see below): both report a failure into
  state["errors"] and return gracefully (empty candidates/forecast)
  rather than raising, and score_recommendations/generate_explanation
  already handle an empty result honestly. A third parallel retry path
  for two more nodes was weighed against reusing handle_provider_error
  generically and rejected for the same reason M4.8 scoped retries to
  just geocode_location/search_places: those two are the ones with
  structured ProviderError reporting AND a real transient-failure mode
  (network blips) worth retrying; a bad route/weather fetch degrading
  straight to "couldn't complete that search" is an acceptable, honest
  failure mode for this milestone.
- The not_yet_supported node (M4's placeholder for route/weather) is
  removed as of M6 -- every intent it used to catch now has a real
  pipeline, so it had no remaining path to reach it. Deleted rather than
  left wired to nothing, per this project's running theme of not leaving
  dead code that misrepresents what the graph actually does.
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
from app.agent.nodes.fetch_weather_forecast import fetch_weather_forecast
from app.agent.nodes.generate_explanation import generate_explanation
from app.agent.nodes.generate_route_candidates import generate_route_candidates
from app.agent.nodes.geocode_location import geocode_location
from app.agent.nodes.handle_provider_error import handle_provider_error, has_error, route_after_error
from app.agent.nodes.load_preferences import load_preferences
from app.agent.nodes.score_recommendations import score_recommendations
from app.agent.nodes.search_places import search_places
from app.agent.nodes.understand_request import understand_request
from app.agent.state import AgentState

# Every intent below needs a resolved location before its tool node can run
# -- geocode_location is the shared first step for all four, same as M4.
_GEOCODE_REQUIRED_INTENTS = ("fitness", "workspace", "route", "weather")


def _route_after_missing_info(state: AgentState) -> str:
    """Combines two sequential decisions (design doc: check_missing_info's
    branch, then route_by_intent) into one routing function, since no node
    needs to run in between them."""
    if state["missing_fields"]:
        return "generate_clarifying_question"
    intent = state["intent"]
    if intent in _GEOCODE_REQUIRED_INTENTS:
        return "check_budget_geocode"
    return "generate_explanation"  # general/unclear (and defensively, anything else)


def _budget_gate(proceed_to: str):
    """Returns a routing function for the conditional edge right after a
    check_tool_budget node instance -- proceeds to `proceed_to` if under
    budget, otherwise short-circuits to budget_exceeded."""

    def _route(state: AgentState) -> str:
        return proceed_to if is_within_budget(state) else "budget_exceeded"

    return _route


_POST_GEOCODE_BUDGET_GATE = {
    "route": "check_budget_route",
    "weather": "check_budget_weather",
}


def _route_after_geocode(state: AgentState) -> str:
    """On success, branches by intent -- fitness/workspace go to
    check_budget_search (M4, unchanged), route/weather go to their own
    single-tool-node gate (M6). All three ultimately feed the same
    score_recommendations, just via a different tool node first."""
    if has_error(state):
        return "handle_geocode_error"
    return _POST_GEOCODE_BUDGET_GATE.get(state["intent"], "check_budget_search")


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
    builder.add_node("budget_exceeded", budget_exceeded)
    builder.add_node("check_budget_geocode", check_tool_budget)
    builder.add_node("geocode_location", geocode_location)
    builder.add_node("handle_geocode_error", handle_provider_error)
    builder.add_node("check_budget_search", check_tool_budget)
    builder.add_node("search_places", search_places)
    builder.add_node("handle_search_error", handle_provider_error)
    builder.add_node("check_budget_details", check_tool_budget)
    builder.add_node("fetch_place_details", fetch_place_details)
    builder.add_node("check_budget_route", check_tool_budget)
    builder.add_node("generate_route_candidates", generate_route_candidates)
    builder.add_node("check_budget_weather", check_tool_budget)
    builder.add_node("fetch_weather_forecast", fetch_weather_forecast)
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
            "generate_explanation": "generate_explanation",
        },
    )
    builder.add_edge("generate_clarifying_question", "ask_user")
    builder.add_edge("ask_user", "understand_request")  # loop -- see module docstring

    builder.add_conditional_edges(
        "check_budget_geocode",
        _budget_gate("geocode_location"),
        {"geocode_location": "geocode_location", "budget_exceeded": "budget_exceeded"},
    )
    builder.add_conditional_edges(
        "geocode_location",
        _route_after_geocode,
        {
            "handle_geocode_error": "handle_geocode_error",
            "check_budget_search": "check_budget_search",
            "check_budget_route": "check_budget_route",
            "check_budget_weather": "check_budget_weather",
        },
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

    builder.add_conditional_edges(
        "check_budget_route",
        _budget_gate("generate_route_candidates"),
        {"generate_route_candidates": "generate_route_candidates", "budget_exceeded": "budget_exceeded"},
    )
    builder.add_edge("generate_route_candidates", "score_recommendations")

    builder.add_conditional_edges(
        "check_budget_weather",
        _budget_gate("fetch_weather_forecast"),
        {"fetch_weather_forecast": "fetch_weather_forecast", "budget_exceeded": "budget_exceeded"},
    )
    builder.add_edge("fetch_weather_forecast", "score_recommendations")

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
