from app.schemas.preferences import Importance
from app.scoring.preference_adjustment import (
    ADJUSTMENT_THRESHOLD,
    apply_adjustment,
    compute_adjustment,
)


def _reject(intent="fitness", **breakdown):
    return {"intent": intent, "action": "rejected", "scoreBreakdown": breakdown}


def _accept(intent="fitness", **breakdown):
    return {"intent": intent, "action": "accepted", "scoreBreakdown": breakdown}


def test_no_feedback_produces_no_adjustment():
    result = compute_adjustment([])

    assert result.is_empty
    assert result.importance_delta == {}
    assert result.reasons == []


def test_below_threshold_rejections_produce_no_adjustment():
    # affordability is the weakest factor on every one of these, but there
    # are only ADJUSTMENT_THRESHOLD - 1 of them -- overcorrection guard,
    # a small sample shouldn't move anything.
    records = [_reject(affordability=0.1, rating=0.9) for _ in range(ADJUSTMENT_THRESHOLD - 1)]

    result = compute_adjustment(records)

    assert result.is_empty


def test_repeated_rejection_of_low_affordability_items_bumps_affordability():
    # This is the design doc's own named example: "a user who repeatedly
    # rejects expensive options sees budget-sensitive ranking shift."
    records = [_reject(affordability=0.1, rating=0.9, distance=0.8) for _ in range(ADJUSTMENT_THRESHOLD)]

    result = compute_adjustment(records)

    assert result.importance_delta == {"affordability": 1}
    assert len(result.reasons) == 1
    assert "affordability" in result.reasons[0].lower()
    assert "rejected" in result.reasons[0].lower()


def test_repeated_acceptance_driven_by_a_factor_also_bumps_it():
    records = [_accept(affordability=0.95, rating=0.6, distance=0.5) for _ in range(ADJUSTMENT_THRESHOLD)]

    result = compute_adjustment(records)

    assert result.importance_delta == {"affordability": 1}
    assert "accepted" in result.reasons[0].lower()


def test_reject_and_accept_evidence_for_the_same_factor_stacks_to_a_bump_of_two():
    records = [_reject(affordability=0.1, rating=0.9) for _ in range(ADJUSTMENT_THRESHOLD)] + [
        _accept(affordability=0.95, rating=0.5) for _ in range(ADJUSTMENT_THRESHOLD)
    ]

    result = compute_adjustment(records)

    assert result.importance_delta == {"affordability": 2}
    assert len(result.reasons) == 2


def test_route_and_weather_feedback_is_ignored_entirely():
    # Neither domain reads UserPreferences.importance at all (fixed
    # module-level weights instead) -- there's nothing to adjust from
    # this feedback, and it must not accidentally count toward a
    # fitness/workspace factor that happens to share a name.
    records = [_reject(intent="route", park_coverage=0.1) for _ in range(ADJUSTMENT_THRESHOLD)]
    records += [_reject(intent="weather", temperature=0.1) for _ in range(ADJUSTMENT_THRESHOLD)]

    result = compute_adjustment(records)

    assert result.is_empty


def test_records_with_no_adjustable_factors_in_the_breakdown_are_skipped():
    # e.g. a fitness candidate with no price_level at all never got an
    # "affordability" component (fitness_scoring.py skips it), so
    # "rating"/"setting" alone give this rule nothing to act on.
    records = [_reject(rating=0.2) for _ in range(ADJUSTMENT_THRESHOLD)]

    result = compute_adjustment(records)

    assert result.is_empty


def test_apply_adjustment_bumps_the_named_factor_only():
    base = Importance(affordability=3, review_count=3, distance=3)

    updated = apply_adjustment(base, {"affordability": 1})

    assert updated.affordability == 4
    assert updated.review_count == 3
    assert updated.distance == 3


def test_apply_adjustment_clamps_at_the_schema_maximum():
    base = Importance(affordability=5, review_count=3, distance=3)

    updated = apply_adjustment(base, {"affordability": 2})

    assert updated.affordability == 5


def test_apply_adjustment_with_no_delta_returns_the_same_values():
    base = Importance(affordability=3, review_count=3, distance=3)

    updated = apply_adjustment(base, {})

    assert updated == base


def test_apply_adjustment_does_not_mutate_the_base_instance():
    base = Importance(affordability=3, review_count=3, distance=3)

    apply_adjustment(base, {"affordability": 1})

    assert base.affordability == 3
