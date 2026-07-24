"""
Structural verification only -- does the graph compile, does it contain
the nodes this milestone actually wired up, and is get_graph() a real
singleton. A full live run needs real API keys (LLMProvider,
GeocodingProvider, PlacesProvider all construct real clients when a node
runs with no injected override, and graph-invoked nodes can't be handed a
stub the way the standalone node unit tests do -- LangGraph calls nodes as
node(state) only). Mocked multi-turn conversation tests are M4.11's job;
a real, paid end-to-end run is M4.12's, done by hand against a live key.
"""
from app.agent.graph import build_graph, get_graph

EXPECTED_NODES = {
    "understand_request",
    "load_preferences",
    "check_missing_info",
    "generate_clarifying_question",
    "ask_user",
    "budget_exceeded",
    "check_budget_geocode",
    "geocode_location",
    "handle_geocode_error",
    "check_budget_search",
    "search_places",
    "handle_search_error",
    "check_budget_details",
    "fetch_place_details",
    "check_budget_route",
    "generate_route_candidates",
    "check_budget_weather",
    "fetch_weather_forecast",
    "score_recommendations",
    "generate_explanation",
}


def test_build_graph_compiles_without_error():
    graph = build_graph()

    assert graph is not None


def test_compiled_graph_contains_every_expected_node():
    graph = build_graph()

    node_names = set(graph.get_graph().nodes.keys())

    assert EXPECTED_NODES.issubset(node_names)


def test_get_graph_is_a_cached_singleton():
    first = get_graph()
    second = get_graph()

    assert first is second


def test_build_graph_returns_a_fresh_instance_each_call():
    # Unlike get_graph(), build_graph() should NOT be cached -- each call
    # gets its own InMemorySaver, useful for test isolation.
    first = build_graph()
    second = build_graph()

    assert first is not second
