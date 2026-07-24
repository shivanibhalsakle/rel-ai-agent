from app.agent.nodes.generate_route_candidates import generate_route_candidates
from app.agent.state import new_agent_state
from app.providers.places_provider import PlaceCandidate
from app.providers.route_provider import RouteResult
from app.schemas.preferences import UserPreferences


class _StubPlacesProvider:
    def __init__(self, parks: list[PlaceCandidate]):
        self._parks = parks
        self.last_radius_meters: float | None = None
        self.last_included_types: list[str] | None = None

    async def search_nearby(self, lat, lng, radius_meters, included_types, max_results=15):
        self.last_radius_meters = radius_meters
        self.last_included_types = included_types
        return self._parks


class _StubRouteProvider:
    """Returns `result` for every call unless `skip_dest` matches the
    destination lat/lng, in which case it returns None (simulates
    Routes API finding no route to that waypoint)."""

    def __init__(self, result: RouteResult | None, skip_dest: tuple[float, float] | None = None):
        self._result = result
        self._skip_dest = skip_dest
        self.calls: list[tuple] = []

    async def compute_route(self, origin_lat, origin_lng, dest_lat, dest_lng, travel_mode="walk"):
        self.calls.append((origin_lat, origin_lng, dest_lat, dest_lng, travel_mode))
        if self._skip_dest and (round(dest_lat, 4), round(dest_lng, 4)) == self._skip_dest:
            return None
        return self._result


def _park(place_id: str, name: str, lat: float = 40.71, lng: float = -73.95) -> PlaceCandidate:
    return PlaceCandidate(place_id=place_id, name=name, lat=lat, lng=lng, types=["park"])


def _located_state(extracted: dict | None = None, travel_mode: str = "walk") -> dict:
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "route"
    state["resolved_location"] = {"lat": 40.7, "lng": -73.9, "formatted_address": "Union Square, New York, NY"}
    state["saved_preferences"] = UserPreferences(travel_mode=travel_mode)
    state["extracted_preferences"] = extracted or {}
    return state


async def test_non_route_intent_is_a_no_op():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"

    update = await generate_route_candidates(state)

    assert update == {}


async def test_no_resolved_location_returns_an_error():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "route"

    update = await generate_route_candidates(state)

    assert "route_candidates" not in update
    assert update["errors"][0]["node"] == "generate_route_candidates"


async def test_no_parks_falls_back_to_four_compass_headings():
    state = _located_state()
    route_result = RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly")

    update = await generate_route_candidates(
        state, places_provider=_StubPlacesProvider([]), route_provider=_StubRouteProvider(route_result)
    )

    assert len(update["route_candidates"]) == 4
    labels = {c.label for c in update["route_candidates"]}
    assert labels == {
        "Out-and-back heading north",
        "Out-and-back heading east",
        "Out-and-back heading south",
        "Out-and-back heading west",
    }


async def test_parks_fill_first_then_headings_fill_the_rest():
    state = _located_state()
    parks = [_park("park1", "Prospect Park"), _park("park2", "McCarren Park")]
    route_result = RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly")

    update = await generate_route_candidates(
        state, places_provider=_StubPlacesProvider(parks), route_provider=_StubRouteProvider(route_result)
    )

    candidates = update["route_candidates"]
    assert len(candidates) == 5  # 2 parks + 3 heading fallbacks (MAX_CANDIDATES=5)
    park_candidates = [c for c in candidates if "Prospect Park" in c.label or "McCarren Park" in c.label]
    assert len(park_candidates) == 2
    assert all(c.park_coverage_ratio == 0.6 for c in park_candidates)
    heading_candidates = [c for c in candidates if c not in park_candidates]
    assert all(c.park_coverage_ratio == 0.0 for c in heading_candidates)


async def test_distance_and_duration_are_doubled_for_the_round_trip():
    state = _located_state()
    route_result = RouteResult(distance_meters=1500, duration_seconds=900, encoded_polyline="abc123")

    update = await generate_route_candidates(
        state,
        places_provider=_StubPlacesProvider([_park("p1", "Test Park")]),
        route_provider=_StubRouteProvider(route_result),
    )

    candidate = update["route_candidates"][0]
    assert candidate.route.distance_meters == 3000
    assert candidate.route.duration_seconds == 1800
    assert candidate.route.encoded_polyline == "abc123"


async def test_major_road_exposure_ratio_is_never_set():
    state = _located_state()
    route_result = RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly")

    update = await generate_route_candidates(
        state, places_provider=_StubPlacesProvider([]), route_provider=_StubRouteProvider(route_result)
    )

    assert all(c.major_road_exposure_ratio is None for c in update["route_candidates"])


async def test_a_waypoint_with_no_route_found_is_skipped_not_crashed():
    state = _located_state()
    parks = [_park("p1", "Unreachable Park", lat=41.0, lng=-74.5)]
    route_result = RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly")
    stub_routes = _StubRouteProvider(route_result, skip_dest=(41.0, -74.5))

    update = await generate_route_candidates(
        state, places_provider=_StubPlacesProvider(parks), route_provider=stub_routes
    )

    # The unreachable park's candidate is dropped; all 4 heading fallbacks
    # (remaining = MAX_CANDIDATES(5) - 1 park slot = 4) still come through.
    assert len(update["route_candidates"]) == 4
    assert all("heading" in c.label for c in update["route_candidates"])


async def test_target_distance_defaults_when_not_extracted():
    state = _located_state(extracted={})
    stub_places = _StubPlacesProvider([])
    route_result = RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly")

    await generate_route_candidates(state, places_provider=stub_places, route_provider=_StubRouteProvider(route_result))

    assert stub_places.last_radius_meters == 2400.0  # DEFAULT_TARGET_DISTANCE_METERS (4800) / 2


async def test_target_distance_from_extracted_preferences_halves_the_search_radius():
    state = _located_state(extracted={"target_distance_meters": 10000.0})
    stub_places = _StubPlacesProvider([])
    route_result = RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly")

    await generate_route_candidates(state, places_provider=stub_places, route_provider=_StubRouteProvider(route_result))

    assert stub_places.last_radius_meters == 5000.0


async def test_travel_mode_from_preferences_is_passed_to_route_provider():
    state = _located_state(travel_mode="bike")
    stub_routes = _StubRouteProvider(RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly"))

    await generate_route_candidates(state, places_provider=_StubPlacesProvider([]), route_provider=stub_routes)

    assert all(call[4] == "bike" for call in stub_routes.calls)


async def test_park_search_uses_park_type():
    state = _located_state()
    stub_places = _StubPlacesProvider([])

    await generate_route_candidates(
        state,
        places_provider=stub_places,
        route_provider=_StubRouteProvider(RouteResult(distance_meters=1000, duration_seconds=600, encoded_polyline="poly")),
    )

    assert stub_places.last_included_types == ["park"]
