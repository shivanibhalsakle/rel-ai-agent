from app.scoring.base import (
    ScoreComponent,
    clamp01,
    normalize,
    rank,
    to_scored_result,
    weighted_average,
)


def test_clamp01_bounds():
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0
    assert clamp01(0.3) == 0.3


def test_normalize_basic_range():
    assert normalize(5, low=0, high=10) == 0.5
    assert normalize(0, low=0, high=10) == 0.0
    assert normalize(10, low=0, high=10) == 1.0


def test_normalize_clamps_outside_range():
    assert normalize(-5, low=0, high=10) == 0.0
    assert normalize(15, low=0, high=10) == 1.0


def test_normalize_invert_flips_direction():
    # Lower raw value (closer distance) should score higher when inverted.
    assert normalize(0, low=0, high=10, invert=True) == 1.0
    assert normalize(10, low=0, high=10, invert=True) == 0.0
    assert normalize(2.5, low=0, high=10, invert=True) == 0.75


def test_normalize_degenerate_range_scores_full():
    # low == high means the factor doesn't vary across candidates — it
    # shouldn't be able to zero anyone out.
    assert normalize(7, low=7, high=7) == 1.0


def test_weighted_average_respects_weights():
    components = [
        ScoreComponent(factor="rating", score=1.0, weight=3, detail="5.0 stars"),
        ScoreComponent(factor="distance", score=0.0, weight=1, detail="far away"),
    ]
    # (1.0*3 + 0.0*1) / 4 = 0.75
    assert weighted_average(components) == 0.75


def test_weighted_average_zero_total_weight_is_zero():
    components = [ScoreComponent(factor="x", score=1.0, weight=0, detail="n/a")]
    assert weighted_average(components) == 0.0


def test_to_scored_result_scales_to_100():
    components = [ScoreComponent(factor="rating", score=0.8, weight=1, detail="4/5 stars")]
    result = to_scored_result(item="place-1", components=components)
    assert result.total_score == 80.0
    assert result.item == "place-1"


def test_explanation_orders_by_contribution_descending():
    components = [
        ScoreComponent(factor="distance", score=0.2, weight=1, detail="far"),
        ScoreComponent(factor="rating", score=0.9, weight=3, detail="great rating"),
        ScoreComponent(factor="budget", score=0.5, weight=1, detail="mid price"),
    ]
    result = to_scored_result(item="place-1", components=components)
    # contributions: rating=2.7, budget=0.5, distance=0.2
    assert result.explanation == ["great rating", "mid price", "far"]


def test_rank_orders_highest_first():
    low = to_scored_result("low", [ScoreComponent(factor="x", score=0.2, weight=1, detail="low")])
    high = to_scored_result("high", [ScoreComponent(factor="x", score=0.9, weight=1, detail="high")])
    mid = to_scored_result("mid", [ScoreComponent(factor="x", score=0.5, weight=1, detail="mid")])

    ranked = rank([low, high, mid])

    assert [r.item for r in ranked] == ["high", "mid", "low"]
