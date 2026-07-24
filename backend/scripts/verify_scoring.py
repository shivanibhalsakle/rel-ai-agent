"""
Manual verification script for Milestone 3. Not a test — a human-readable
demonstration that, given a fixed candidate set and a fixed preference
profile, every scoring module produces the same deterministic, explainable
ranked list every time it's run (no network calls, no randomness, no LLM).

Run it twice and diff the output (or just eyeball it) to see that nothing
changes between runs — that's the actual "deterministic" claim in the
Milestone 3 completion criteria being demonstrated, not just asserted.

Usage (from backend/, with the venv activated):
    python scripts/verify_scoring.py
"""
from app.providers.places_provider import PlaceCandidate
from app.providers.route_provider import RouteResult
from app.providers.weather_provider import HourlyForecast
from app.schemas.preferences import BudgetBand, Importance, UserPreferences, WorkspaceNeeds
from app.scoring import fitness_scoring, route_scoring, weather_scoring, workspace_scoring
from app.scoring.route_scoring import RouteCandidate


def _print_ranked(title: str, results) -> None:
    print(f"\n=== {title} ===")
    for rank_index, result in enumerate(results, start=1):
        label = getattr(result.item, "name", None) or getattr(result.item, "candidate_id", None) or getattr(
            result.item, "start_time", "candidate"
        )
        print(f"{rank_index}. {label} — {result.total_score}/100")
        for reason in result.explanation:
            print(f"     - {reason}")


def main() -> None:
    preferences = UserPreferences(
        activities=["gym", "running"],
        budget_band=BudgetBand(min=0, max=120),
        max_travel_minutes=25,
        travel_mode="walk",
        min_rating=3.5,
        importance=Importance(affordability=4, review_count=3, distance=5),
        workspace_needs=WorkspaceNeeds(wifi=True, outlets=True, quiet=False, food=False),
        indoor_outdoor_preference="either",
    )

    # --- Fitness ---
    fitness_candidates = [
        PlaceCandidate(
            place_id="gym-a", name="Riverside Fitness", lat=40.7, lng=-74.0,
            rating=4.7, user_rating_count=380, price_level="PRICE_LEVEL_MODERATE", types=["gym"],
        ),
        PlaceCandidate(
            place_id="gym-b", name="Budget Barbell", lat=40.71, lng=-74.01,
            rating=4.1, user_rating_count=60, price_level="PRICE_LEVEL_INEXPENSIVE", types=["gym"],
        ),
        PlaceCandidate(
            place_id="gym-c", name="Corner Yoga (too far)", lat=40.9, lng=-74.2,
            rating=4.9, user_rating_count=200, price_level="PRICE_LEVEL_EXPENSIVE", types=["yoga_studio"],
        ),
    ]
    fitness_travel_minutes = {"gym-a": 8, "gym-b": 15, "gym-c": 40}
    _print_ranked(
        "Fitness",
        fitness_scoring.score_and_rank(fitness_candidates, preferences, travel_minutes=fitness_travel_minutes),
    )

    # --- Workspace ---
    workspace_candidates = [
        PlaceCandidate(
            place_id="cafe-a", name="Quiet Corner Cafe", lat=40.72, lng=-74.0,
            rating=4.5, user_rating_count=150, price_level="PRICE_LEVEL_MODERATE", types=["cafe"],
        ),
        PlaceCandidate(
            place_id="cafe-b", name="Loud Espresso Bar", lat=40.73, lng=-74.02,
            rating=4.3, user_rating_count=90, price_level="PRICE_LEVEL_INEXPENSIVE", types=["cafe"],
        ),
    ]
    workspace_amenities = {
        "cafe-a": {"wifi": True, "outlets": True},
        "cafe-b": {"wifi": True, "outlets": False},
    }
    _print_ranked(
        "Workspace",
        workspace_scoring.score_and_rank(workspace_candidates, preferences, amenities=workspace_amenities),
    )

    # --- Route ---
    route_candidates = [
        RouteCandidate(
            candidate_id="route-park",
            route=RouteResult(distance_meters=4950, duration_seconds=1780, encoded_polyline="fake_a"),
            park_coverage_ratio=0.7,
            major_road_exposure_ratio=0.1,
            label="Riverside Park loop",
        ),
        RouteCandidate(
            candidate_id="route-street",
            route=RouteResult(distance_meters=5100, duration_seconds=1820, encoded_polyline="fake_b"),
            park_coverage_ratio=0.05,
            major_road_exposure_ratio=0.6,
            label="Main Street out-and-back",
        ),
    ]
    _print_ranked(
        "Route (target: 5km run)",
        route_scoring.score_and_rank(
            route_candidates, preferences, target_distance_meters=5000,
            weather_comfort={"route-park": 0.9, "route-street": 0.9},
        ),
    )

    # --- Weather ---
    weather_windows = [
        HourlyForecast(
            start_time="2026-07-23T07:00:00Z", is_daytime=True, condition="Clear", condition_type="CLEAR",
            temperature_degrees=17.0, temperature_unit="CELSIUS",
            precipitation_probability_percent=5, wind_speed=8.0, wind_speed_unit="KILOMETERS_PER_HOUR",
            humidity_percent=55, uv_index=3,
        ),
        HourlyForecast(
            start_time="2026-07-23T13:00:00Z", is_daytime=True, condition="Sunny", condition_type="CLEAR",
            temperature_degrees=33.0, temperature_unit="CELSIUS",
            precipitation_probability_percent=0, wind_speed=5.0, wind_speed_unit="KILOMETERS_PER_HOUR",
            humidity_percent=40, uv_index=9,
        ),
        HourlyForecast(
            start_time="2026-07-23T18:00:00Z", is_daytime=True, condition="Showers", condition_type="RAIN",
            temperature_degrees=19.0, temperature_unit="CELSIUS",
            precipitation_probability_percent=80, wind_speed=15.0, wind_speed_unit="KILOMETERS_PER_HOUR",
            humidity_percent=75, uv_index=2,
        ),
    ]
    _print_ranked("Weather (best window today)", weather_scoring.score_and_rank(weather_windows, preferences))

    print("\nRun this script again — identical scores/order every time confirms it's deterministic.")


if __name__ == "__main__":
    main()
