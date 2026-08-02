"""
Scores workspace-domain candidates (cafes, coworking spaces, libraries —
whatever PlacesProvider returns for a workspace-type search) against a
user's saved UserPreferences.

Known MVP limitation: WorkspaceNeeds (wifi/outlets/quiet/food) can't be
scored from PlaceCandidate alone — the New Places API's search fields don't
expose those as booleans, only a per-place Details fetch would (see
PlacesProvider's docstring: cheap search now, paid Details later for
shortlisted candidates only). This module accepts an optional `amenities`
dict so it's ready to score real data the moment Milestone 4 adds those
selective Details fetches; until then, every candidate just skips that
component the same way missing distance data is skipped.
"""
from app.providers.places_provider import PlaceCandidate
from app.schemas.preferences import UserPreferences
from app.scoring.base import ScoreComponent, ScoredResult, normalize, rank, to_scored_result

RATING_WEIGHT = 2.0
AMENITY_WEIGHT = 1.5

REVIEW_COUNT_CAP = 500

_PRICE_LEVEL_ORDINAL = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

_AMENITY_LABELS = {
    "wifi": "Wifi",
    "outlets": "Power outlets",
    "quiet": "Quiet",
    "food": "Food available",
}


def score_and_rank(
    candidates: list[PlaceCandidate],
    preferences: UserPreferences,
    travel_minutes: dict[str, float] | None = None,
    amenities: dict[str, dict[str, bool]] | None = None,
) -> list[ScoredResult[PlaceCandidate]]:
    """Filter out candidates below min_rating (same "no rating, no signal,
    exclude it" rule as fitness_scoring), score the rest, return
    highest-first.

    `amenities` is keyed by place_id, values are a dict like
    {"wifi": True, "outlets": False, ...} — only include keys you actually
    know, from a real Details fetch. Only the needs the user turned ON in
    WorkspaceNeeds are scored; needs left off aren't penalized either way.
    """
    travel_minutes = travel_minutes or {}
    amenities = amenities or {}
    importance = preferences.importance
    needs = preferences.workspace_needs

    eligible = [c for c in candidates if c.rating is not None and c.rating >= preferences.min_rating]

    results: list[ScoredResult[PlaceCandidate]] = []
    for candidate in eligible:
        components: list[ScoreComponent] = [
            ScoreComponent(
                factor="rating",
                score=normalize(candidate.rating, low=1, high=5),
                weight=RATING_WEIGHT,
                detail=f"{candidate.rating}★ rating",
                confidence="verified",
            ),
            ScoreComponent(
                factor="review_count",
                score=normalize(candidate.user_rating_count or 0, low=0, high=REVIEW_COUNT_CAP),
                weight=importance.review_count,
                detail=f"{candidate.user_rating_count or 0} reviews",
                confidence="verified",
            ),
        ]

        minutes = travel_minutes.get(candidate.place_id)
        if minutes is not None:
            high = preferences.max_travel_minutes or 60
            components.append(
                ScoreComponent(
                    factor="distance",
                    score=normalize(minutes, low=0, high=high, invert=True),
                    weight=importance.distance,
                    detail=f"{minutes:g} min away",
                    confidence="verified",
                )
            )

        ordinal = _PRICE_LEVEL_ORDINAL.get(candidate.price_level or "")
        if candidate.price_level is not None and ordinal is not None:
            label = candidate.price_level.replace("PRICE_LEVEL_", "").replace("_", " ").title()
            components.append(
                ScoreComponent(
                    factor="affordability",
                    score=normalize(ordinal, low=0, high=4, invert=True),
                    weight=importance.affordability,
                    detail=f"{label} pricing",
                    confidence="verified",
                )
            )

            unavailable: list[str] = []
        known_amenities = amenities.get(candidate.place_id, {})
        for need_name in ("wifi", "outlets", "quiet", "food"):
            wants_it = getattr(needs, need_name)
            if not wants_it:
                continue
            if need_name not in known_amenities:
                unavailable.append(need_name)
                continue
            has_it = known_amenities[need_name]
            components.append(
                ScoreComponent(
                    factor=need_name,
                    score=1.0 if has_it else 0.0,
                    weight=AMENITY_WEIGHT,
                    detail=(
                        f"{_AMENITY_LABELS[need_name]} available"
                        if has_it
                        else f"No {_AMENITY_LABELS[need_name].lower()}"
                    ),
                    confidence="estimated",
                )
            )

        results.append(to_scored_result(item=candidate, components=components, unavailable_factors=unavailable))

    return rank(results)