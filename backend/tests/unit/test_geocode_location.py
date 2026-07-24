from app.agent.nodes.geocode_location import geocode_location
from app.agent.state import new_agent_state
from app.providers.geocoding_provider import GeocodeResult


class _StubGeocodingProvider:
    def __init__(self, result: GeocodeResult | None):
        self._result = result
        self.last_query: str | None = None

    async def geocode(self, address: str):
        self.last_query = address
        return self._result


async def test_no_location_query_returns_an_error_not_a_crash():
    state = new_agent_state(user_id="u1", session_id="s1")

    update = await geocode_location(state, provider=_StubGeocodingProvider(None))

    assert "resolved_location" not in update
    assert update["errors"][0]["node"] == "geocode_location"
    assert update["errors"][0]["retryable"] is False


async def test_provider_returning_none_is_reported_as_a_not_found_error():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["location_query"] = "asdkfjhaskdjf"

    update = await geocode_location(state, provider=_StubGeocodingProvider(None))

    assert "resolved_location" not in update
    assert "asdkfjhaskdjf" in update["errors"][0]["message"]


async def test_successful_geocode_sets_resolved_location():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["location_query"] = "Union Square"
    result = GeocodeResult(formatted_address="Union Square, New York, NY", lat=40.7359, lng=-73.9911, place_id="p1")
    stub = _StubGeocodingProvider(result)

    update = await geocode_location(state, provider=stub)

    assert stub.last_query == "Union Square"
    assert update["resolved_location"] == {
        "lat": 40.7359,
        "lng": -73.9911,
        "formatted_address": "Union Square, New York, NY",
    }
