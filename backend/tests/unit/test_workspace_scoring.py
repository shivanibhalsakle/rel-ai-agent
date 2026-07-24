from app.providers.places_provider import PlaceCandidate
from app.schemas.preferences import Importance, UserPreferences, WorkspaceNeeds
from app.scoring.workspace_scoring import score_and_rank


def _preferences(**overrides) -> UserPreferences:
    defaults = dict(
        min_rating=3.5,
        importance=Importance(affordability=3, review_count=4, distance=5),
        max_travel_minutes=30,
        workspace_needs=WorkspaceNeeds(),
    )
    defaults.update(overrides)
    return UserPreferences(**defaults)


def _candidate(**overrides) -> PlaceCandidate:
    defaults = dict(
        place_id="place-default",
        name="Default Cafe",
        lat=0.0,
        lng=0.0,
        rating=4.0,
        user_rating_count=100,
        price_level="PRICE_LEVEL_MODERATE",
        types=["cafe"],
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
    prefs = _preferences()
    strong = _candidate(place_id="strong", rating=4.8, user_rating_count=450)
    weaker = _candidate(place_id="weaker", rating=4.0, user_rating_count=50)
    travel_minutes = {"strong": 5, "weaker": 25}

    results = score_and_rank([strong, weaker], prefs, travel_minutes=travel_minutes)

    assert [r.item.place_id for r in results] == ["strong", "weaker"]


def test_amenity_match_affects_ranking_when_requested_and_known():
    prefs = _preferences(workspace_needs=WorkspaceNeeds(wifi=True, quiet=True))
    has_both = _candidate(place_id="has-both", rating=4.0, user_rating_count=100)
    has_neither = _candidate(place_id="has-neither", rating=4.0, user_rating_count=100)
    amenities = {
        "has-both": {"wifi": True, "quiet": True},
        "has-neither": {"wifi": False, "quiet": False},
    }

    results = score_and_rank([has_both, has_neither], prefs, amenities=amenities)

    assert [r.item.place_id for r in results] == ["has-both", "has-neither"]


def test_amenity_not_requested_is_never_scored_even_if_known():
    # User didn't ask for food; even if we know a place has no food, that
    # shouldn't drag its score down.
    prefs = _preferences(workspace_needs=WorkspaceNeeds(wifi=False, food=False))
    candidate = _candidate(place_id="only-place")
    amenities = {"only-place": {"wifi": False, "food": False}}

    results = score_and_rank([candidate], prefs, amenities=amenities)

    factors = {c.factor for c in results[0].components}
    assert "wifi" not in factors
    assert "food" not in factors


def test_missing_amenity_data_does_not_crash_and_still_scores():
    prefs = _preferences(workspace_needs=WorkspaceNeeds(wifi=True, outlets=True))
    candidate = _candidate(place_id="unknown-amenities")

    # No `amenities` argument at all — this is the current real-world
    # state until Milestone 4 adds Details fetches.
    results = score_and_rank([candidate], prefs)

    assert len(results) == 1
    factors = {c.factor for c in results[0].components}
    assert "wifi" not in factors
    assert "outlets" not in factors
    assert factors == {"rating", "review_count", "affordability"}
