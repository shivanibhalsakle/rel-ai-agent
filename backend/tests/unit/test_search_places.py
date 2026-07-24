from app.agent.nodes.search_places import search_places
from app.agent.state import new_agent_state
from app.providers.places_provider import PlaceCandidate
from app.schemas.preferences import UserPreferences


class _StubPlacesProvider:
    def __init__(self, results: list[PlaceCandidate]):
        self._results = results
        self.last_query: str | None = None
        self.last_max_results: int | None = None

    async def search_text(self, query: str, max_results: int = 15):
        self.last_query = query
        self.last_max_results = max_results
        return self._results


def _candidate(place_id: str) -> PlaceCandidate:
    return PlaceCandidate(place_id=place_id, name="Test Place", lat=0.0, lng=0.0)


def _located_state(intent: str, preferences: UserPreferences | None = None):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = intent
    state["saved_preferences"] = preferences or UserPreferences()
    state["resolved_location"] = {"lat": 40.7, "lng": -73.9, "formatted_address": "Union Square, New York, NY"}
    return state


async def test_no_resolved_location_returns_an_error():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"
    state["saved_preferences"] = UserPreferences(activities=["gym"])

    update = await search_places(state, provider=_StubPlacesProvider([]))

    assert "places_results" not in update
    assert update["errors"][0]["node"] == "search_places"


async def test_fitness_query_uses_first_activity_and_address():
    state = _located_state("fitness", UserPreferences(activities=["yoga", "gym"]))
    stub = _StubPlacesProvider([_candidate("p1")])

    update = await search_places(state, provider=stub)

    assert stub.last_query == "yoga near Union Square, New York, NY"
    assert update["places_results"] == [_candidate("p1")]


async def test_fitness_with_no_activities_falls_back_to_gym():
    state = _located_state("fitness", UserPreferences(activities=[]))
    stub = _StubPlacesProvider([])

    await search_places(state, provider=stub)

    assert stub.last_query == "gym near Union Square, New York, NY"


async def test_workspace_uses_default_workspace_query():
    state = _located_state("workspace")
    stub = _StubPlacesProvider([])

    await search_places(state, provider=stub)

    assert stub.last_query == "coworking space or cafe with wifi near Union Square, New York, NY"


async def test_max_results_is_capped_at_fifteen():
    state = _located_state("fitness", UserPreferences(activities=["gym"]))
    stub = _StubPlacesProvider([])

    await search_places(state, provider=stub)

    assert stub.last_max_results == 15
