from app.providers.places_provider import PlaceCandidate
from app.schemas.preferences import Importance, UserPreferences
from app.scoring.fitness_scoring import score_and_rank


def _preferences(**overrides) -> UserPreferences:
    defaults = dict(
        min_rating=3.5,
        importance=Importance(affordability=3, review_count=4, distance=5),
        max_travel_minutes=30,
        indoor_outdoor_preference="either",
    )
    defaults.update(overrides)
    return UserPreferences(**defaults)


def _candidate(**overrides) -> PlaceCandidate:
    defaults = dict(
        place_id="place-default",
        name="Default Gym",
        lat=0.0,
        lng=0.0,
        rating=4.0,
        user_rating_count=100,
        price_level="PRICE_LEVEL_MODERATE",
        types=["gym"],
    )
    defaults.update(overrides)
    return PlaceCandidate(**defaults)


def test_candidates_below_min_rating_are_excluded():
    prefs = _preferences(min_rating=3.5)
    good = _candidate(place_id="good", rating=4.0)
    too_low = _candidate(place_id="too-low", rating=3.0)
    no_rating = _candidate(place_id="no-rating", rating=None)

    results = score_and_rank([good, too_low, no_rating], prefs)

    assert [r.item.place_id for r in results] == ["good"]


def test_higher_rating_reviews_and_closer_distance_wins():
    prefs = _preferences(min_rating=3.5)
    strong = _candidate(
        place_id="strong",
        rating=4.8,
        user_rating_count=450,
        price_level="PRICE_LEVEL_MODERATE",
    )
    weaker = _candidate(
        place_id="weaker",
        rating=4.0,
        user_rating_count=50,
        price_level="PRICE_LEVEL_INEXPENSIVE",
    )
    travel_minutes = {"strong": 10, "weaker": 25}

    results = score_and_rank([strong, weaker], prefs, travel_minutes=travel_minutes)

    assert [r.item.place_id for r in results] == ["strong", "weaker"]
    assert results[0].total_score > results[1].total_score


def test_affordability_weight_can_flip_ranking_on_price_alone():
    # Same rating, same review count, no distance data — only price_level
    # differs, with affordability weighted far above everything else.
    prefs = _preferences(
        min_rating=3.5,
        importance=Importance(affordability=5, review_count=1, distance=1),
    )
    cheap = _candidate(place_id="cheap", rating=4.0, user_rating_count=100, price_level="PRICE_LEVEL_INEXPENSIVE")
    pricey = _candidate(place_id="pricey", rating=4.0, user_rating_count=100, price_level="PRICE_LEVEL_VERY_EXPENSIVE")

    results = score_and_rank([cheap, pricey], prefs)

    assert [r.item.place_id for r in results] == ["cheap", "pricey"]


def test_missing_optional_data_does_not_crash_and_still_scores():
    prefs = _preferences(min_rating=3.5)
    candidate = _candidate(
        place_id="sparse",
        rating=4.2,
        user_rating_count=None,
        price_level=None,
        types=[],
    )

    results = score_and_rank([candidate], prefs)

    assert len(results) == 1
    assert results[0].total_score > 0
    # Only rating + review_count components should be present — no
    # distance, affordability, or setting data was available.
    factors = {c.factor for c in results[0].components}
    assert factors == {"rating", "review_count"}


def test_indoor_outdoor_preference_affects_ranking_when_signaled():
    prefs = _preferences(min_rating=3.5, indoor_outdoor_preference="outdoor")
    park = _candidate(place_id="park", rating=4.0, user_rating_count=100, types=["park"])
    indoor_gym = _candidate(place_id="gym", rating=4.0, user_rating_count=100, types=["gym"])

    results = score_and_rank([park, indoor_gym], prefs)

    assert [r.item.place_id for r in results] == ["park", "gym"]
