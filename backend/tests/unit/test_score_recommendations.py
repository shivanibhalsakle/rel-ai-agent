from app.agent.nodes.score_recommendations import score_recommendations
from app.agent.state import new_agent_state
from app.providers.places_provider import PlaceCandidate
from app.providers.route_provider import RouteResult
from app.providers.weather_provider import HourlyForecast
from app.schemas.preferences import Importance, UserPreferences
from app.scoring.route_scoring import RouteCandidate


def _candidate(place_id: str, rating: float, review_count: int = 100) -> PlaceCandidate:
    return PlaceCandidate(place_id=place_id, name=place_id, lat=0.0, lng=0.0, rating=rating, user_rating_count=review_count)


def _route_candidate(candidate_id: str, distance_meters: float) -> RouteCandidate:
    return RouteCandidate(
        candidate_id=candidate_id,
        route=RouteResult(distance_meters=distance_meters, duration_seconds=distance_meters / 1.4, encoded_polyline="enc"),
        park_coverage_ratio=0.5,
        label=candidate_id,
    )


def _forecast(start_time: str, temp_c: float) -> HourlyForecast:
    return HourlyForecast(
        start_time=start_time,
        is_daytime=True,
        condition="Clear",
        condition_type="CLEAR",
        temperature_degrees=temp_c,
        temperature_unit="CELSIUS",
    )


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


async def test_route_intent_scores_via_route_scoring_using_extracted_targets():
    close = _route_candidate("close", distance_meters=4800.0)
    far = _route_candidate("far", distance_meters=9000.0)
    state = _state("route", [])
    state["route_candidates"] = [far, close]
    state["extracted_preferences"] = {"target_distance_meters": 4800.0}

    update = score_recommendations(state)

    results = update["scored_results"]
    # "close" matches the extracted target distance exactly, so it should
    # out-rank "far" -- confirms target_distance_meters actually flows from
    # extracted_preferences into route_scoring.score_and_rank, not just that
    # scoring ran at all.
    assert [r.item.candidate_id for r in results] == ["close", "far"]


async def test_route_intent_with_no_extracted_targets_still_scores_on_other_factors():
    state = _state("route", [])
    state["route_candidates"] = [_route_candidate("only", distance_meters=5000.0)]
    state["extracted_preferences"] = {}

    update = score_recommendations(state)

    results = update["scored_results"]
    assert [r.item.candidate_id for r in results] == ["only"]
    # No distance/duration target given -> those factors are skipped, not
    # scored against a made-up target (mirrors route_scoring's own tests).
    assert "distance_target" not in {c.factor for c in results[0].components}


async def test_weather_intent_scores_and_ranks_via_weather_scoring():
    cold = _forecast("2026-07-24T06:00:00Z", temp_c=2.0)
    mild = _forecast("2026-07-24T14:00:00Z", temp_c=18.0)
    state = _state("weather", [])
    state["weather_data"] = [cold, mild]

    update = score_recommendations(state)

    results = update["scored_results"]
    assert [r.item.start_time for r in results] == [mild.start_time, cold.start_time]


async def test_general_intent_returns_empty_scored_results():
    state = _state("general", [])

    update = score_recommendations(state)

    assert update["scored_results"] == []


async def test_weather_intent_snapshots_the_top_pick_for_later_add_to_calendar():
    cold = _forecast("2026-07-24T06:00:00Z", temp_c=2.0)
    mild = _forecast("2026-07-24T14:00:00Z", temp_c=18.0)
    state = _state("weather", [])
    state["weather_data"] = [cold, mild]
    state["resolved_location"] = {"lat": 40.66, "lng": -73.97, "formatted_address": "Prospect Park, Brooklyn, NY"}

    update = score_recommendations(state)

    snapshot = update["last_weather_recommendation"]
    assert snapshot["start"] == "2026-07-24T14:00:00+00:00"
    assert snapshot["end"] == "2026-07-24T15:00:00+00:00"
    assert snapshot["location"] == "Prospect Park, Brooklyn, NY"
    assert snapshot["title"]


async def test_weather_intent_with_no_results_sets_no_snapshot():
    state = _state("weather", [])
    state["weather_data"] = []

    update = score_recommendations(state)

    assert "last_weather_recommendation" not in update


async def test_weather_snapshot_location_is_none_without_a_resolved_location():
    mild = _forecast("2026-07-24T14:00:00Z", temp_c=18.0)
    state = _state("weather", [])
    state["weather_data"] = [mild]
    state["resolved_location"] = None

    update = score_recommendations(state)

    assert update["last_weather_recommendation"]["location"] is None
