"""
M7.7's "before/after comparison on a test user's recommendation set" --
distinct from test_preference_adjustment.py's unit tests (which check
compute_adjustment/apply_adjustment in isolation). This chains the whole
M7 pipeline for real: synthetic feedback -> compute_adjustment ->
apply_adjustment -> fitness_scoring.score_and_rank (M3's real, unmodified
scoring code), scored twice against the identical candidate pair, before
and after. The design doc's own completion criteria for this milestone
("a user who repeatedly rejects expensive options sees budget-sensitive
ranking shift measurably") is checked literally: the top-ranked candidate
actually flips from the pricier, higher-rated option to the cheaper,
lower-rated one once the adjustment is in effect -- not just that a
score number moved.
"""
from app.providers.places_provider import PlaceCandidate
from app.schemas.preferences import Importance, UserPreferences
from app.scoring import fitness_scoring
from app.scoring.preference_adjustment import ADJUSTMENT_THRESHOLD, apply_adjustment, compute_adjustment

_CHEAP = PlaceCandidate(
    place_id="cheap",
    name="Budget Gym",
    lat=0.0,
    lng=0.0,
    rating=3.0,
    user_rating_count=200,
    price_level="PRICE_LEVEL_INEXPENSIVE",
)
_PRICEY = PlaceCandidate(
    place_id="pricey",
    name="Premium Fitness Club",
    lat=0.0,
    lng=0.0,
    rating=5.0,
    user_rating_count=200,
    price_level="PRICE_LEVEL_VERY_EXPENSIVE",
)


def _rejected_pricey_for_affordability():
    """One synthetic feedback record: the user rejected an item whose
    weakest scored factor was affordability -- exactly what
    fitness_scoring would have produced for _PRICEY under low-affordability-
    weight preferences (its affordability component scores 0.0, its lowest
    of the three)."""
    return {
        "intent": "fitness",
        "action": "rejected",
        "scoreBreakdown": {"rating": 1.0, "review_count": 0.4, "affordability": 0.0},
    }


def test_repeated_rejection_of_pricey_options_flips_the_top_ranked_candidate():
    # Starts with a low affordability weight (1) -- a user who hasn't
    # indicated price sensitivity yet -- so the higher-rated but much
    # pricier candidate wins on the strength of its rating alone.
    before_prefs = UserPreferences(importance=Importance(affordability=1, review_count=3, distance=3))

    before_results = fitness_scoring.score_and_rank([_CHEAP, _PRICEY], before_prefs)
    assert before_results[0].item.place_id == "pricey"

    # Simulate the design doc's named scenario: this user rejects several
    # recent recommendations, each one pricier than they wanted.
    feedback = [_rejected_pricey_for_affordability() for _ in range(ADJUSTMENT_THRESHOLD)]
    adjustment = compute_adjustment(feedback)
    assert adjustment.importance_delta == {"affordability": 1}

    after_importance = apply_adjustment(before_prefs.importance, adjustment.importance_delta)
    after_prefs = before_prefs.model_copy(update={"importance": after_importance})

    after_results = fitness_scoring.score_and_rank([_CHEAP, _PRICEY], after_prefs)

    # The measurable shift: cheap now outranks pricey, having lost to it
    # before the adjustment -- not just a smaller score gap.
    assert after_results[0].item.place_id == "cheap"

    before_cheap_score = next(r.total_score for r in before_results if r.item.place_id == "cheap")
    after_cheap_score = next(r.total_score for r in after_results if r.item.place_id == "cheap")
    assert after_cheap_score > before_cheap_score  # cheap's own score rose too, not just its rank
