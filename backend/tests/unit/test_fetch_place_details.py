from app.agent.nodes.fetch_place_details import SHORTLIST_SIZE, fetch_place_details
from app.agent.state import new_agent_state
from app.providers.places_provider import PlaceCandidate


class _StubPlacesProvider:
    def __init__(self, reviews_by_place: dict[str, list[str]]):
        self._reviews_by_place = reviews_by_place
        self.calls: list[str] = []

    async def get_reviews(self, place_id: str) -> list[str]:
        self.calls.append(place_id)
        return self._reviews_by_place.get(place_id, [])


def _candidate(place_id: str, rating: float) -> PlaceCandidate:
    return PlaceCandidate(place_id=place_id, name=place_id, lat=0.0, lng=0.0, rating=rating)


def _workspace_state(candidates: list[PlaceCandidate]):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "workspace"
    state["places_results"] = candidates
    return state


async def test_non_workspace_intent_never_calls_the_provider():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"
    state["places_results"] = [_candidate("p1", 4.5)]
    stub = _StubPlacesProvider({})

    update = await fetch_place_details(state, provider=stub)

    assert update == {}
    assert stub.calls == []


async def test_empty_places_results_returns_empty_update():
    state = _workspace_state([])
    stub = _StubPlacesProvider({})

    update = await fetch_place_details(state, provider=stub)

    assert update == {}
    assert stub.calls == []


async def test_only_top_shortlist_size_candidates_by_rating_are_fetched():
    candidates = [
        _candidate("p1", 4.9),
        _candidate("p2", 4.8),
        _candidate("p3", 4.5),
        _candidate("p4", 4.2),
        _candidate("p5", 4.0),
        _candidate("p6", 3.5),  # 6th place, should be excluded (shortlist size is 5)
    ]
    state = _workspace_state(candidates)
    stub = _StubPlacesProvider({})

    await fetch_place_details(state, provider=stub)

    assert len(stub.calls) == SHORTLIST_SIZE
    assert set(stub.calls) == {"p1", "p2", "p3", "p4", "p5"}
    assert "p6" not in stub.calls


async def test_reviews_with_amenity_mentions_populate_workspace_amenities():
    state = _workspace_state([_candidate("p1", 4.5)])
    stub = _StubPlacesProvider({"p1": ["Great wifi here, worked all day.", "No outlets near the window seats."]})

    update = await fetch_place_details(state, provider=stub)

    assert update["workspace_amenities"]["p1"]["wifi"] is True
    assert update["workspace_amenities"]["p1"]["outlets"] is False


async def test_place_with_no_reviews_is_skipped_not_included_as_empty():
    state = _workspace_state([_candidate("p1", 4.5)])
    stub = _StubPlacesProvider({"p1": []})

    update = await fetch_place_details(state, provider=stub)

    assert "p1" not in update["workspace_amenities"]


async def test_place_with_no_amenity_keyword_matches_is_skipped():
    state = _workspace_state([_candidate("p1", 4.5)])
    stub = _StubPlacesProvider({"p1": ["The croissants here are amazing."]})

    update = await fetch_place_details(state, provider=stub)

    assert "p1" not in update["workspace_amenities"]
