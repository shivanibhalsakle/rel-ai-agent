from app.providers.route_provider import RouteResult
from app.schemas.preferences import UserPreferences
from app.scoring.route_scoring import RouteCandidate, score_and_rank


def _route(distance_meters: float, duration_seconds: float) -> RouteResult:
    return RouteResult(
        distance_meters=distance_meters,
        duration_seconds=duration_seconds,
        encoded_polyline="fake_polyline",
    )


def _candidate(
    candidate_id: str,
    distance_meters: float,
    duration_seconds: float,
    park_coverage_ratio: float = 0.0,
    major_road_exposure_ratio: float = 0.0,
) -> RouteCandidate:
    return RouteCandidate(
        candidate_id=candidate_id,
        route=_route(distance_meters, duration_seconds),
        park_coverage_ratio=park_coverage_ratio,
        major_road_exposure_ratio=major_road_exposure_ratio,
    )


def test_closer_to_target_distance_wins():
    prefs = UserPreferences()
    close = _candidate("close", distance_meters=5100, duration_seconds=1800)
    far = _candidate("far", distance_meters=8000, duration_seconds=2400)

    results = score_and_rank([close, far], prefs, target_distance_meters=5000)

    assert [r.item.candidate_id for r in results] == ["close", "far"]


def test_closer_to_target_duration_wins():
    prefs = UserPreferences()
    close = _candidate("close", distance_meters=5000, duration_seconds=1850)
    far = _candidate("far", distance_meters=5000, duration_seconds=3000)

    results = score_and_rank([close, far], prefs, target_duration_seconds=1800)

    assert [r.item.candidate_id for r in results] == ["close", "far"]


def test_park_coverage_and_road_exposure_break_ties():
    prefs = UserPreferences()
    parky = _candidate("parky", 5000, 1800, park_coverage_ratio=0.8, major_road_exposure_ratio=0.1)
    roady = _candidate("roady", 5000, 1800, park_coverage_ratio=0.0, major_road_exposure_ratio=0.9)

    results = score_and_rank([parky, roady], prefs, target_distance_meters=5000)

    assert [r.item.candidate_id for r in results] == ["parky", "roady"]


def test_weather_comfort_lifts_ranking_when_provided():
    prefs = UserPreferences()
    a = _candidate("a", 5000, 1800)
    b = _candidate("b", 5000, 1800)

    results = score_and_rank(
        [a, b],
        prefs,
        weather_comfort={"a": 0.9, "b": 0.1},
    )

    assert [r.item.candidate_id for r in results] == ["a", "b"]


def test_no_targets_or_weather_data_still_scores_on_route_quality_alone():
    prefs = UserPreferences()
    candidate = _candidate("solo", 5000, 1800, park_coverage_ratio=0.5, major_road_exposure_ratio=0.2)

    results = score_and_rank([candidate], prefs)

    assert len(results) == 1
    factors = {c.factor for c in results[0].components}
    assert factors == {"park_coverage", "road_exposure"}


def test_road_exposure_detail_never_claims_safety():
    prefs = UserPreferences()
    candidate = _candidate("solo", 5000, 1800, major_road_exposure_ratio=0.3)

    results = score_and_rank([candidate], prefs)

    road_detail = next(c.detail for c in results[0].components if c.factor == "road_exposure")
    # The bug in an earlier version of this test: "safe" is a substring of
    # "safety", so `"safe" not in text` incorrectly failed on the correct,
    # careful wording below. The actual requirement is narrower: the text
    # must never assert the route IS safe, and must carry the explicit
    # disclaimer — both of which this checks without the substring trap.
    assert "is safe" not in road_detail.lower()
    assert "safe route" not in road_detail.lower()
    assert "not a safety guarantee" in road_detail.lower()
