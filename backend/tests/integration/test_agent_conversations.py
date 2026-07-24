"""
M4.11 -- multi-turn conversations run through the REAL compiled StateGraph
(app.agent.graph.build_graph()), not through individual node unit tests.
The goal is different from every *_node test so far: those check one
node's logic in isolation; these check that nodes hand state to each
other correctly -- routing, the tool-call budget gate, the retry/degrade
error path, and the interrupt/resume pause -- which only shows up once
the graph actually runs turns end to end.

The catch (documented in M4.9's test_graph.py and M4.10's test_chat_routes.py
too): LangGraph invokes every node as node(state) with no injection point,
so the provider-injection trick the standalone node unit tests use
(llm=fake_llm, provider=fake_provider) doesn't reach a node that's running
inside a compiled graph. What DOES work: app/agent/graph.py imports each
node function by name at module load time and reads those same names when
build_graph() wires up add_node() calls -- so patching a name in
app.agent.graph's own namespace BEFORE calling build_graph() (fresh, not
the cached get_graph()) substitutes a fake for that node inside the graph
that gets compiled. That's what _build_test_graph does below.

Only the nodes that need a real API key are faked this way: understand_request,
load_preferences, generate_clarifying_question, geocode_location,
search_places, fetch_place_details, generate_route_candidates,
fetch_weather_forecast, generate_explanation. Everything else
(check_missing_info, ask_user, the five check_tool_budget instances,
handle_provider_error, score_recommendations, budget_exceeded, and every
conditional-edge routing function) is the REAL implementation -- these
tests are exercising exactly that code, using fitness_scoring/
workspace_scoring/route_scoring/weather_scoring (M3) for real against fake
provider data, so the scoring hand-off is genuinely tested too, not just
stubbed through.
"""
import app.agent.graph as graph_module
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agent.state import new_agent_state
from app.providers.places_provider import PlaceCandidate
from app.providers.route_provider import RouteResult
from app.providers.weather_provider import HourlyForecast
from app.schemas.preferences import UserPreferences
from app.scoring.base import item_display_name, item_id
from app.scoring.route_scoring import RouteCandidate


class _FakeNode:
    """Stands in for one graph node. Returns the next canned response each
    time it's called -- one entry per turn/invocation, since e.g.
    understand_request runs once per conversation turn. A response can be
    a plain dict (the state update to return) or a callable(state) -> dict
    for cases where the right response depends on state the fake can't
    know in advance (e.g. generate_explanation needs the place_ids
    score_recommendations actually produced)."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    async def __call__(self, state):
        self.calls.append(state)
        assert self._responses, f"_FakeNode called more times ({len(self.calls)}) than responses provided"
        response = self._responses.pop(0)
        return response(state) if callable(response) else response

    def assert_exhausted(self):
        assert not self._responses, f"{len(self._responses)} canned response(s) never consumed"


def _build_test_graph(monkeypatch, **fakes):
    for name, fake in fakes.items():
        monkeypatch.setattr(graph_module, name, fake)
    return graph_module.build_graph()


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _place(place_id, name, rating=4.5):
    return PlaceCandidate(place_id=place_id, name=name, lat=40.7, lng=-73.9, rating=rating)


def _route_candidate(candidate_id, label, distance_meters=4800.0):
    return RouteCandidate(
        candidate_id=candidate_id,
        route=RouteResult(distance_meters=distance_meters, duration_seconds=distance_meters / 1.4, encoded_polyline="enc"),
        park_coverage_ratio=0.6,
        label=label,
    )


def _forecast(start_time, temp_c=18.0):
    return HourlyForecast(
        start_time=start_time,
        is_daytime=True,
        condition="Clear",
        condition_type="CLEAR",
        temperature_degrees=temp_c,
        temperature_unit="CELSIUS",
    )


def _explanations_from_scores(state):
    """A generic-enough generate_explanation fake: phrases whatever
    score_recommendations (the REAL node) actually produced, or the
    honest degrade message if the pipeline failed upstream -- mirrors the
    two branches M4.7's real node has, without needing an LLM call.

    Keyed via item_id() and phrased via item_display_name() (M6's shared
    helpers), not a hardcoded r.item.place_id/r.item.name -- route/weather
    results have neither at all, so this fake needs the same domain-
    agnostic lookups the real generate_explanation node uses."""
    top = state.get("scored_results", [])[:5]
    if not top:
        errors = state.get("errors", [])
        if errors:
            return {"explanation": f"I couldn't complete that search: {errors[-1]['message']}"}
        return {"explanations": {}}
    return {"explanations": {item_id(r.item): f"Good pick: {item_display_name(r.item)}" for r in top}}


# ---- fitness: clarifying question, then a second turn that completes ----


async def test_fitness_flow_pauses_for_location_then_completes(monkeypatch):
    understand = _FakeNode(
        # turn 1: "find me a yoga studio" -- activity given, no location
        {"intent": "fitness", "extracted_preferences": {"activities": ["yoga"]}},
        # turn 2 (after the clarifying question is answered): now we have one
        {"intent": "fitness", "extracted_preferences": {"activities": ["yoga"]}, "location_query": "Union Square"},
    )
    load_prefs = _FakeNode(
        {"saved_preferences": UserPreferences(activities=["yoga"])},
        {"saved_preferences": UserPreferences(activities=["yoga"])},
    )
    ask_question = _FakeNode({"messages": [HumanMessage(content="Which neighborhood?")]})
    geocode = _FakeNode(
        {"resolved_location": {"lat": 40.735, "lng": -73.991, "formatted_address": "Union Square, New York, NY"}}
    )
    search = _FakeNode(
        {
            "places_results": [
                _place("p1", "Union Square Yoga", rating=4.8),
                _place("p2", "Downtown Yoga Loft", rating=4.1),
            ]
        }
    )
    details = _FakeNode({})  # fitness intent -- real node would no-op too
    explain = _FakeNode(_explanations_from_scores)

    graph = _build_test_graph(
        monkeypatch,
        understand_request=understand,
        load_preferences=load_prefs,
        generate_clarifying_question=ask_question,
        geocode_location=geocode,
        search_places=search,
        fetch_place_details=details,
        generate_explanation=explain,
    )
    config = _config("fitness-session")

    state = new_agent_state(user_id="u1", session_id="fitness-session")
    state["messages"] = [HumanMessage(content="find me a yoga studio")]
    turn1 = await graph.ainvoke(state, config)

    assert "__interrupt__" in turn1
    assert turn1["__interrupt__"][0].value == "Which neighborhood?"

    turn2 = await graph.ainvoke(Command(resume="Union Square"), config)

    assert turn2["intent"] == "fitness"
    assert len(turn2["scored_results"]) == 2
    ranked_ids = [r.item.place_id for r in turn2["scored_results"]]
    assert set(ranked_ids) == {"p1", "p2"}
    top_id = ranked_ids[0]
    assert turn2["explanations"][top_id] == f"Good pick: {turn2['scored_results'][0].item.name}"
    # budget was spent on exactly geocode + search (fetch_place_details is a
    # no-op for fitness, and check_tool_budget still runs immediately before
    # it per graph.py, so this is 3 gated calls, not 2)
    assert turn2["tool_call_count"] == 3

    understand.assert_exhausted()
    load_prefs.assert_exhausted()
    ask_question.assert_exhausted()
    geocode.assert_exhausted()
    search.assert_exhausted()


# ---- workspace: location given upfront, no clarifying question needed ----


async def test_workspace_flow_fetches_amenities_and_scores(monkeypatch):
    understand = _FakeNode(
        {"intent": "workspace", "extracted_preferences": {}, "location_query": "downtown Boston"}
    )
    load_prefs = _FakeNode({"saved_preferences": UserPreferences()})
    geocode = _FakeNode(
        {"resolved_location": {"lat": 42.36, "lng": -71.06, "formatted_address": "Downtown, Boston, MA"}}
    )
    search = _FakeNode(
        {
            "places_results": [
                _place("w1", "Quiet Cafe", rating=4.6),
                _place("w2", "Busy Coworking Hub", rating=4.3),
            ]
        }
    )
    details = _FakeNode({"workspace_amenities": {"w1": {"wifi": True, "outlets": True, "quiet": True, "food": False}}})
    explain = _FakeNode(_explanations_from_scores)

    graph = _build_test_graph(
        monkeypatch,
        understand_request=understand,
        load_preferences=load_prefs,
        geocode_location=geocode,
        search_places=search,
        fetch_place_details=details,
        generate_explanation=explain,
    )
    config = _config("workspace-session")

    state = new_agent_state(user_id="u1", session_id="workspace-session")
    state["messages"] = [HumanMessage(content="find me a coworking space near downtown Boston")]
    result = await graph.ainvoke(state, config)

    assert "__interrupt__" not in result
    assert result["intent"] == "workspace"
    assert result["workspace_amenities"] == {"w1": {"wifi": True, "outlets": True, "quiet": True, "food": False}}
    assert len(result["scored_results"]) == 2
    assert set(result["explanations"]) == {"w1", "w2"}
    assert result["tool_call_count"] == 3  # geocode + search + details, each gated


# ---- general intent: no search pipeline runs at all ----


async def test_general_intent_skips_search_entirely(monkeypatch):
    understand = _FakeNode({"intent": "general", "extracted_preferences": {}})
    load_prefs = _FakeNode({"saved_preferences": UserPreferences()})
    explain = _FakeNode({"explanation": "Hi! I can help you find gyms, workspaces, and more."})

    graph = _build_test_graph(
        monkeypatch,
        understand_request=understand,
        load_preferences=load_prefs,
        generate_explanation=explain,
    )
    config = _config("general-session")

    state = new_agent_state(user_id="u1", session_id="general-session")
    state["messages"] = [HumanMessage(content="hi there")]
    result = await graph.ainvoke(state, config)

    assert result["explanation"] == "Hi! I can help you find gyms, workspaces, and more."
    assert result["tool_call_count"] == 0  # never touched a gated tool node
    assert result["scored_results"] == []


# ---- route: geocode -> generate_route_candidates -> score -> explain (Milestone 6) ----


async def test_route_flow_generates_and_scores_candidates(monkeypatch):
    understand = _FakeNode(
        {
            "intent": "route",
            "extracted_preferences": {"target_distance_meters": 4800.0},
            "location_query": "Golden Gate Park",
        }
    )
    load_prefs = _FakeNode({"saved_preferences": UserPreferences()})
    geocode = _FakeNode(
        {"resolved_location": {"lat": 37.769, "lng": -122.483, "formatted_address": "Golden Gate Park, San Francisco, CA"}}
    )
    candidates = _FakeNode(
        {
            "route_candidates": [
                _route_candidate("route-0", "Out-and-back to Golden Gate Park", distance_meters=4800.0),
                _route_candidate("route-1", "Out-and-back heading north", distance_meters=9000.0),
            ]
        }
    )
    explain = _FakeNode(_explanations_from_scores)

    graph = _build_test_graph(
        monkeypatch,
        understand_request=understand,
        load_preferences=load_prefs,
        geocode_location=geocode,
        generate_route_candidates=candidates,
        generate_explanation=explain,
    )
    config = _config("route-session")

    state = new_agent_state(user_id="u1", session_id="route-session")
    state["messages"] = [HumanMessage(content="find me a 3 mile route near Golden Gate Park")]
    result = await graph.ainvoke(state, config)

    assert "__interrupt__" not in result
    assert result["intent"] == "route"
    assert len(result["scored_results"]) == 2
    # "route-0" matches the extracted 4800m target exactly -- route_scoring
    # (the REAL node) should rank it first, confirming target_distance_meters
    # actually flowed from extracted_preferences through to scoring.
    assert result["scored_results"][0].item.candidate_id == "route-0"
    assert set(result["explanations"]) == {"route-0", "route-1"}
    assert result["tool_call_count"] == 2  # geocode + generate_route_candidates, each gated


# ---- weather: geocode -> fetch_weather_forecast -> score -> explain (Milestone 6) ----


async def test_weather_flow_fetches_and_scores_forecast(monkeypatch):
    understand = _FakeNode({"intent": "weather", "extracted_preferences": {}, "location_query": "Prospect Park"})
    load_prefs = _FakeNode({"saved_preferences": UserPreferences()})
    geocode = _FakeNode(
        {"resolved_location": {"lat": 40.66, "lng": -73.97, "formatted_address": "Prospect Park, Brooklyn, NY"}}
    )
    forecast = _FakeNode(
        {
            "weather_data": [
                _forecast("2026-07-24T06:00:00Z", temp_c=2.0),
                _forecast("2026-07-24T14:00:00Z", temp_c=18.0),
            ]
        }
    )
    explain = _FakeNode(_explanations_from_scores)

    graph = _build_test_graph(
        monkeypatch,
        understand_request=understand,
        load_preferences=load_prefs,
        geocode_location=geocode,
        fetch_weather_forecast=forecast,
        generate_explanation=explain,
    )
    config = _config("weather-session")

    state = new_agent_state(user_id="u1", session_id="weather-session")
    state["messages"] = [HumanMessage(content="best time to run today near Prospect Park")]
    result = await graph.ainvoke(state, config)

    assert "__interrupt__" not in result
    assert result["intent"] == "weather"
    assert len(result["scored_results"]) == 2
    # The mild 18C hour should outrank the near-freezing 2C hour --
    # confirms weather_scoring (the REAL node) actually ran, not just that
    # something was returned.
    assert result["scored_results"][0].item.start_time == "2026-07-24T14:00:00Z"
    assert set(result["explanations"]) == {"2026-07-24T06:00:00Z", "2026-07-24T14:00:00Z"}
    assert result["tool_call_count"] == 2  # geocode + fetch_weather_forecast, each gated


# ---- tool budget: short-circuits before a second gated call ----


async def test_tool_budget_exceeded_short_circuits(monkeypatch):
    understand = _FakeNode(
        {"intent": "workspace", "extracted_preferences": {}, "location_query": "downtown Boston"}
    )
    load_prefs = _FakeNode({"saved_preferences": UserPreferences()})
    geocode = _FakeNode({"resolved_location": {"lat": 42.36, "lng": -71.06, "formatted_address": "Boston, MA"}})

    graph = _build_test_graph(
        monkeypatch, understand_request=understand, load_preferences=load_prefs, geocode_location=geocode
    )
    config = _config("budget-session")

    state = new_agent_state(user_id="u1", session_id="budget-session", tool_call_budget=1)
    state["messages"] = [HumanMessage(content="find me a coworking space near downtown Boston")]
    result = await graph.ainvoke(state, config)

    assert "narrow" in result["explanation"].lower()
    # geocode's own gate (count 0->1) was still within budget=1 and ran;
    # search's gate (count 1->2) is what actually exceeded it
    assert result["tool_call_count"] == 2


# ---- provider error: transient failure retries once, then succeeds ----


async def test_geocode_transient_error_retries_then_succeeds(monkeypatch):
    understand = _FakeNode(
        {"intent": "workspace", "extracted_preferences": {}, "location_query": "downtown Boston"}
    )
    load_prefs = _FakeNode({"saved_preferences": UserPreferences()})
    geocode = _FakeNode(
        {"errors": [{"node": "geocode_location", "message": "Timed out.", "retryable": True}]},
        {"resolved_location": {"lat": 42.36, "lng": -71.06, "formatted_address": "Boston, MA"}},
    )
    search = _FakeNode({"places_results": [_place("w1", "Quiet Cafe")]})
    details = _FakeNode({})
    explain = _FakeNode(_explanations_from_scores)

    graph = _build_test_graph(
        monkeypatch,
        understand_request=understand,
        load_preferences=load_prefs,
        geocode_location=geocode,
        search_places=search,
        fetch_place_details=details,
        generate_explanation=explain,
    )
    config = _config("retry-session")

    state = new_agent_state(user_id="u1", session_id="retry-session")
    state["messages"] = [HumanMessage(content="find me a coworking space near downtown Boston")]
    result = await graph.ainvoke(state, config)

    assert result["errors"] == []  # the transient error was cleared on retry
    assert result["retry_counts"] == {"geocode_location": 1}
    assert len(result["scored_results"]) == 1
    geocode.assert_exhausted()  # confirms it really was called twice


# ---- provider error: permanent failure degrades to an honest message ----


async def test_geocode_permanent_error_degrades_to_honest_message(monkeypatch):
    understand = _FakeNode(
        {"intent": "fitness", "extracted_preferences": {"activities": ["gym"]}, "location_query": "Nowhereville"}
    )
    load_prefs = _FakeNode({"saved_preferences": UserPreferences(activities=["gym"])})
    geocode = _FakeNode(
        {
            "errors": [
                {"node": "geocode_location", "message": 'Could not find a location for "Nowhereville".', "retryable": False}
            ]
        }
    )
    explain = _FakeNode(_explanations_from_scores)

    graph = _build_test_graph(
        monkeypatch,
        understand_request=understand,
        load_preferences=load_prefs,
        geocode_location=geocode,
        generate_explanation=explain,
    )
    config = _config("degrade-session")

    state = new_agent_state(user_id="u1", session_id="degrade-session")
    state["messages"] = [HumanMessage(content="find me a gym near Nowhereville")]
    result = await graph.ainvoke(state, config)

    assert result["scored_results"] == []
    assert "Nowhereville" in result["explanation"]
    assert len(result["errors"]) == 1  # left in place, not silently cleared
    geocode.assert_exhausted()  # confirms no retry attempt was made
