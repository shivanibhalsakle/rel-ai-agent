"""
Scores candidate running/walking routes against a target distance/duration
and the heuristics described in the design doc's route-planning flow
(Step 3.3): distance-to-target accuracy, park coverage, major-road exposure,
and weather comfort for the window.

This module does NOT generate route candidates — that's the waypoint-biasing
step ("generate candidate waypoints biased toward known park/green-space
polygons, then request routes through those waypoints") which calls
RouteProvider and PlacesProvider repeatedly and belongs in Milestone 4's
`fetch_route_data` tool node. This module is purely the
`score_recommendations` half: given a set of already-computed candidates,
rank them.

Road exposure and park coverage aren't things RouteProvider gives us
directly (Google's Routes API doesn't expose road-classification or
park-overlap data) — they're heuristic ratios the M6 route-generation step
(app/agent/nodes/generate_route_candidates.py) estimates and attaches to
each candidate.

The two factors are handled differently on purpose. park_coverage_ratio
defaults to 0.0 and is always shown, because M6's candidate generation
always produces a real, determined value for it (a candidate really was
or wasn't routed through a known park) -- 0.0 there means "confirmed not
near a park," not "unknown." major_road_exposure_ratio is Optional and
its component is SKIPPED (not shown with a default) when None, because
there is currently no real data source for it at all (Routes API's field
mask has no road-classification data) -- defaulting it to 0.0 and
displaying it anyway would have every candidate's explanation claim "100%
estimated non-major roads" with zero actual signal behind that number,
which is fabricating a favorable estimate, not just omitting an unknown
one. This mirrors how distance_target/duration_target are already
skipped rather than scored against a made-up target when the user didn't
give one.

Road-exposure detail text deliberately never says "safe" — the design doc's
risk log calls this out explicitly: "'safe route' claims are a legal and
trust risk if wrong; must consistently use 'lower-traffic based on
available data' framing."
"""
from pydantic import BaseModel, Field

from app.providers.route_provider import RouteResult
from app.schemas.preferences import UserPreferences
from app.scoring.base import ScoreComponent, ScoredResult, clamp01, normalize, rank, to_scored_result

DISTANCE_TARGET_WEIGHT = 4.0
DURATION_TARGET_WEIGHT = 3.0
PARK_COVERAGE_WEIGHT = 2.0
ROAD_EXPOSURE_WEIGHT = 3.0
WEATHER_COMFORT_WEIGHT = 2.0

# How far off-target (as a fraction of the target) a route can be before it
# scores 0 on that factor. 50% deviation -> 0, exact match -> 1, linear
# between. Chosen to be forgiving of the inherent imprecision in
# waypoint-biased route generation, not a claim about what's "acceptable."
_TARGET_DEVIATION_CEILING = 0.5


class RouteCandidate(BaseModel):
    """A generated route plus the heuristic overlays used to score it.
    Wraps the real RouteProvider output (RouteResult) rather than
    duplicating its fields, per the project's "score against real provider
    data shapes" principle."""

    candidate_id: str
    route: RouteResult
    park_coverage_ratio: float = Field(default=0.0, ge=0, le=1)
    # None means "no data source for this yet" -- see module docstring.
    # Distinct from 0.0, which means "confirmed low/no major-road exposure."
    major_road_exposure_ratio: float | None = Field(default=None, ge=0, le=1)
    label: str | None = None


def _target_closeness(actual: float, target: float) -> float:
    if target <= 0:
        return 1.0
    deviation_ratio = abs(actual - target) / target
    return normalize(deviation_ratio, low=0.0, high=_TARGET_DEVIATION_CEILING, invert=True)


def score_and_rank(
    candidates: list[RouteCandidate],
    preferences: UserPreferences,
    target_distance_meters: float | None = None,
    target_duration_seconds: float | None = None,
    weather_comfort: dict[str, float] | None = None,
) -> list[ScoredResult[RouteCandidate]]:
    """Score and rank route candidates. `target_distance_meters` and/or
    `target_duration_seconds` are optional — a user might ask for "a 3 mile
    route" (distance target) or "a 30 minute run" (duration target) or
    neither (just "find me a nice route"), in which case that factor is
    skipped rather than scored against a made-up target.

    `weather_comfort` is an optional {candidate_id: 0-1 score} map, meant
    to be produced by weather_scoring (M3.5) for the specific time window
    each route would be run in — kept as a separate module rather than
    duplicated here, since "how comfortable is this weather" is a distinct,
    reusable concern (weather-aware scheduling reuses the exact same logic).

    `preferences` isn't used yet — kept in the signature for consistency
    with fitness_scoring/workspace_scoring and because a future per-user
    weighting (e.g. a "prefer scenic routes" slider) will need it without
    another call-site change.
    """
    weather_comfort = weather_comfort or {}

    results: list[ScoredResult[RouteCandidate]] = []
    for candidate in candidates:
        route = candidate.route
        components: list[ScoreComponent] = []

        if target_distance_meters is not None:
            score = _target_closeness(route.distance_meters, target_distance_meters)
            components.append(
                ScoreComponent(
                    factor="distance_target",
                    score=score,
                    weight=DISTANCE_TARGET_WEIGHT,
                    detail=f"{route.distance_meters / 1000:.1f} km (target {target_distance_meters / 1000:.1f} km)",
                )
            )

        if target_duration_seconds is not None:
            score = _target_closeness(route.duration_seconds, target_duration_seconds)
            components.append(
                ScoreComponent(
                    factor="duration_target",
                    score=score,
                    weight=DURATION_TARGET_WEIGHT,
                    detail=f"{route.duration_seconds / 60:.0f} min (target {target_duration_seconds / 60:.0f} min)",
                )
            )

        components.append(
            ScoreComponent(
                factor="park_coverage",
                score=clamp01(candidate.park_coverage_ratio),
                weight=PARK_COVERAGE_WEIGHT,
                detail=f"{candidate.park_coverage_ratio * 100:.0f}% estimated through parks/green space",
            )
        )

        if candidate.major_road_exposure_ratio is not None:
            road_score = clamp01(1 - candidate.major_road_exposure_ratio)
            components.append(
                ScoreComponent(
                    factor="road_exposure",
                    score=road_score,
                    weight=ROAD_EXPOSURE_WEIGHT,
                    detail=(
                        f"Lower-traffic based on available data "
                        f"({road_score * 100:.0f}% estimated non-major roads) — not a safety guarantee"
                    ),
                )
            )

        comfort = weather_comfort.get(candidate.candidate_id)
        if comfort is not None:
            components.append(
                ScoreComponent(
                    factor="weather_comfort",
                    score=clamp01(comfort),
                    weight=WEATHER_COMFORT_WEIGHT,
                    detail="Favorable weather expected for this window",
                )
            )

        results.append(to_scored_result(item=candidate, components=components))

    return rank(results)
