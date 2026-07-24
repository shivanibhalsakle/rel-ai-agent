"""
geocode_location node (design doc Step 4) — resolves state["location_query"]
(the raw text captured by understand_request, e.g. "Union Square" or
"Brooklyn") into real coordinates via GeocodingProvider, which already
caches by normalized query with a 30-day TTL (M2) — this node adds no
caching logic of its own.
"""
from app.agent.state import AgentState
from app.providers.geocoding_provider import GeocodingProvider


def _error(node: str, message: str, state: AgentState) -> dict:
    return {"errors": state.get("errors", []) + [{"node": node, "message": message, "retryable": False}]}


async def geocode_location(state: AgentState, provider: GeocodingProvider | None = None) -> dict:
    query = state.get("location_query")
    if not query:
        # check_missing_info should have caught this via ask_user before
        # the graph ever reaches this node -- fail honestly rather than
        # geocoding an empty string if it somehow doesn't.
        return _error("geocode_location", "No location to geocode.", state)

    provider = provider or GeocodingProvider()
    result = await provider.geocode(query)
    if result is None:
        return _error("geocode_location", f"Could not find a location for \"{query}\".", state)

    return {
        "resolved_location": {
            "lat": result.lat,
            "lng": result.lng,
            "formatted_address": result.formatted_address,
        }
    }
