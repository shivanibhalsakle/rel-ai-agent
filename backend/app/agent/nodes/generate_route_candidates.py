"""
generate_route_candidates node (design doc Step 4, and the exact step
route_scoring.py's own M3.4 docstring flagged as not-yet-built: "generate
candidate waypoints biased toward known park/green-space polygons, then
request routes through those waypoints").

Google's Routes API only computes point-to-point directions (see
RouteProvider) -- there is no "generate a loop of X distance near me"
endpoint. This node picks the route SHAPE that sidesteps that gap
entirely: out-and-back. A candidate is "walk to waypoint W, then walk
back the way you came," not an attempt at a true loop. That choice isn't
just simpler, it's more honest about the data available: an out-and-back
route's return leg is definitionally the same path as the outbound leg
reversed, so doubling RouteProvider's one-way distance/duration is exact
by construction, not an approximation -- and only ONE compute_route call
is needed per candidate instead of two.

Waypoints come from two sources:
  1. Parks found via PlacesProvider.search_nearby (type=park) within the
     target one-way distance -- these get a real, determined
     park_coverage_ratio (not a guess).
  2. Compass-heading fallback points (N/E/S/W) at the target one-way
     distance, computed with plain great-circle geometry -- these fill
     out the candidate list when too few (or zero) parks are nearby.
     This is the design doc's own explicitly named risk ("route candidate
     generation quality in areas with sparse park data") made concrete
     and handled, not silently producing an empty result.

major_road_exposure_ratio is deliberately left unset (None) on every
candidate here -- there is no real data source for it yet (see
route_scoring.py's module docstring for the full reasoning). Not
estimated, not guessed at.

Bounded to MAX_CANDIDATES RouteProvider calls (plus one PlacesProvider
call) regardless of how it's invoked -- same cost-discipline pattern as
fetch_place_details' SHORTLIST_SIZE. In graph.py (M6.5) this whole node
sits behind a single check_tool_budget gate, same as fetch_place_details'
internal multi-call loop counts as one gated call, not several.
"""
import math

from app.agent.state import AgentState
from app.providers.places_provider import PlacesProvider
from app.providers.route_provider import RouteProvider, RouteResult
from app.scoring.route_scoring import RouteCandidate

MAX_CANDIDATES = 5
DEFAULT_TARGET_DISTANCE_METERS = 4800.0  # ~3 miles -- a reasonable "go for a run" default when unstated
EARTH_RADIUS_METERS = 6_371_000.0
# Real, determined value for a candidate that IS routed through a known
# park -- not a guess, but also not a precise polyline/greenspace overlap
# measurement (we don't have that data), so it's a flat heuristic rather
# than a computed percentage.
PARK_WAYPOINT_COVERAGE_RATIO = 0.6
_FALLBACK_HEADINGS = [(0, "north"), (90, "east"), (180, "south"), (270, "west")]


def _destination_point(lat: float, lng: float, bearing_degrees: float, distance_meters: float) -> tuple[float, float]:
    """Great-circle destination point at a given bearing/distance from
    (lat, lng). Standard spherical navigation formula -- no geo library
    needed for a single point projection."""
    lat1 = math.radians(lat)
    lng1 = math.radians(lng)
    bearing = math.radians(bearing_degrees)
    angular_distance = distance_meters / EARTH_RADIUS_METERS

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance) + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lng2 = lng1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lng2)


async def generate_route_candidates(
    state: AgentState,
    places_provider: PlacesProvider | None = None,
    route_provider: RouteProvider | None = None,
) -> dict:
    if state["intent"] != "route":
        return {}

    location = state.get("resolved_location")
    if not location:
        return {
            "errors": state.get("errors", [])
            + [{"node": "generate_route_candidates", "message": "No resolved location to route near.", "retryable": False}]
        }

    target_distance_meters = (
        state.get("extracted_preferences", {}).get("target_distance_meters") or DEFAULT_TARGET_DISTANCE_METERS
    )
    one_way_meters = target_distance_meters / 2

    preferences = state.get("saved_preferences")
    travel_mode = preferences.travel_mode if preferences else "walk"

    places_provider = places_provider or PlacesProvider()
    route_provider = route_provider or RouteProvider()

    origin_lat, origin_lng = location["lat"], location["lng"]

    # Waypoint 1: real parks nearby, each a real park_coverage_ratio.
    waypoints: list[tuple[float, float, str, float]] = []
    parks = await places_provider.search_nearby(
        lat=origin_lat,
        lng=origin_lng,
        radius_meters=one_way_meters,
        included_types=["park"],
        max_results=MAX_CANDIDATES,
    )
    for park in parks[:MAX_CANDIDATES]:
        waypoints.append((park.lat, park.lng, f"Out-and-back to {park.name}", PARK_WAYPOINT_COVERAGE_RATIO))

    # Waypoint 2: compass-heading fallbacks, filling out to MAX_CANDIDATES.
    # Always at least attempted, even when parks fully cover the quota,
    # would be redundant -- only used for the remainder.
    remaining = MAX_CANDIDATES - len(waypoints)
    for bearing, direction_name in _FALLBACK_HEADINGS[:remaining]:
        dest_lat, dest_lng = _destination_point(origin_lat, origin_lng, bearing, one_way_meters)
        waypoints.append((dest_lat, dest_lng, f"Out-and-back heading {direction_name}", 0.0))

    candidates: list[RouteCandidate] = []
    for i, (dest_lat, dest_lng, label, park_ratio) in enumerate(waypoints):
        one_way = await route_provider.compute_route(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode)
        if one_way is None:
            continue
        round_trip = RouteResult(
            distance_meters=one_way.distance_meters * 2,
            duration_seconds=one_way.duration_seconds * 2,
            # The one-way polyline -- exactly what an out-and-back route's
            # path actually is, walked in each direction. Not a
            # simplification of a "real" round-trip polyline; there isn't
            # a different one.
            encoded_polyline=one_way.encoded_polyline,
        )
        candidates.append(
            RouteCandidate(
                candidate_id=f"route-{i}",
                route=round_trip,
                park_coverage_ratio=park_ratio,
                label=label,
            )
        )

    return {"route_candidates": candidates}
