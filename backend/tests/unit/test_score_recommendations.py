from app.agent.nodes.score_recommendations import score_recommendations
from app.agent.state import new_agent_state
from app.providers.places_provider import PlaceCandidate
from app.schemas.preferences import Importance, UserPreferences


def _candidate(place_id: str, rating: float, review_count: int = 100) -> PlaceCandidate:
    return PlaceCandidate(place_id=place_id, name=place_id, lat=0.0, lng=0.0, rating=rating, user_rating_count=review_count)


def _state(intent: str, candidates: list[PlaceCandidate], preferences: UserPreferences | None = None):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = intent
    state["places_results"] = candidates
    state["saved_preferences"] = preferences or UserPreferences(min_rating=3.5)
    return state


async def test_fitness_intent_scores_and_ranks_via_fitness_scoring():
    candidates = [_candidate("weak", 4.0), _candidate("strong", 4.9, review_count=400)]
    state = _state("fitness", candidates)

    update = score_recommendations(state)

    results = update["scored_results"]
    assert [r.item.place_id for r in results] == ["strong", "weak"]


async def test_workspace_intent_uses_amenities_from_state():
    candidates = [_candidate("has-wifi", 4.0), _candidate("no-wifi", 4.0)]
    preferences = UserPreferences(min_rating=3.5, importance=Importance(affordability=1, review_count=1, distance=1))
    state = _state("workspace", candidates, preferences)
    state["workspace_amenities"] = {"has-wifi": {"wifi": True}, "no-wifi": {"wifi": False}}
    # workspace_needs.wifi must be True for the amenity to actually be scored
    state["saved_preferences"].workspace_needs.wifi = True

    update = score_recommendations(state)

    results = update["scored_results"]
    assert [r.item.place_id for r in results] == ["has-wifi", "no-wifi"]


async def test_route_intent_returns_empty_scored_results_not_a_crash():
    state = _state("route", [])

    update = score_recommendations(state)

    assert update["scored_results"] == []


async def test_general_intent_returns_empty_scored_results():
    state = _state("general", [])

    update = score_recommendations(state)

    assert update["scored_results"] == []
