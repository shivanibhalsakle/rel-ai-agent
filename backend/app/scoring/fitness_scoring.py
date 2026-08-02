"""
Scores fitness-domain candidates (gyms, studios, parks, trails — whatever
PlacesProvider returns for a fitness-type search) against a user's saved
UserPreferences.

Weight rationale (kept here inline; full writeup lands in
docs/decisions/0001-scoring-weights.md in M3.7):
- Star rating always counts, at a fixed baseline weight — there's no
  explicit "rating" slider in UserPreferences, so this isn't user-tunable
  yet (candidate for a future preference field, not an MVP gap we're
  hiding).
- Review count, distance, and affordability weights come directly from the
  user's `importance` sliders (1-5 each), so two users with the same
  candidates can get different rankings based on what they said matters.
- Indoor/outdoor match is a small fixed-weight bonus, only applied when the
  user expressed a preference and the candidate's `types` give us a signal.
"""
from app.providers.places_provider import PlaceCandidate
from app.schemas.preferences import UserPreferences
from app.scoring.base import ScoreComponent, ScoredResult, normalize, rank, to_scored_result

RATING_WEIGHT = 2.0
INDOOR_OUTDOOR_WEIGHT = 1.0

# user_rating_count above this is treated as "plenty of reviews" — the New
# Places API doesn't cap this, but diminishing returns kick in well before
# real-world counts like 5,000+, so we don't want a mega-gym with 8k
# reviews to totally dominate one with a solid, sufficient 500.
REVIEW_COUNT_CAP = 500

# Google's New Places API price_level enum, mapped to an ordinal scale so it
# can be normalized like any other numeric factor. This is a categorical
# proxy for affordability, not a dollar comparison against the user's
# budgetBand — Places doesn't return exact prices for fitness venues, so an
# exact-dollar match isn't possible with this data source. Documented
# limitation, not a silent approximation.
_PRICE_LEVEL_ORDINAL = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

# Approximate signal from Places `types` — not exhaustive, refine against
# real search results once M4 wires this up to live queries.
_INDOOR_TYPES = {"gym", "fitness_center", "yoga_studio", "sports_club", "swimming_pool"}
_OUTDOOR_TYPES = {"park", "hiking_area", "trail", "sports_complex"}


def score_and_rank(
    candidates: list[PlaceCandidate],
    preferences: UserPreferences,
    travel_minutes: dict[str, float] | None = None,
) -> list[ScoredResult[PlaceCandidate]]:
    """Filter out candidates below the user's min_rating (a candidate with
    no rating at all is excluded too — no rating means no fitness-quality
    signal, so we'd rather omit it than guess), score the rest, and return
    them highest-first.

    `travel_minutes` is optional and keyed by place_id: this module doesn't
    call RouteProvider itself (that's a network call, this module stays
    pure), so the caller (later, the agent) supplies travel times it
    already computed. Candidates missing an entry just skip the distance
    component instead of being penalized for missing data.
    """
    travel_minutes = travel_minutes or {}
    importance = preferences.importance

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

        if preferences.indoor_outdoor_preference != "either":
            candidate_types = set(candidate.types)
            is_indoor = bool(candidate_types & _INDOOR_TYPES)
            is_outdoor = bool(candidate_types & _OUTDOOR_TYPES)
            if is_indoor or is_outdoor:
                matches = (preferences.indoor_outdoor_preference == "indoor" and is_indoor) or (
                    preferences.indoor_outdoor_preference == "outdoor" and is_outdoor
                )
                components.append(
                    ScoreComponent(
                        factor="setting",
                        score=1.0 if matches else 0.0,
                        weight=INDOOR_OUTDOOR_WEIGHT,
                        detail=("Matches your indoor/outdoor preference" if matches else "Different setting than preferred"),
                        confidence="verified",
                    )
                )

        results.append(to_scored_result(item=candidate, components=components))

    return rank(results)
