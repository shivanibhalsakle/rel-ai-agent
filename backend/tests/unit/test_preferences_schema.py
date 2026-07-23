from app.schemas.preferences import UserPreferences


def test_defaults_are_sensible_when_nothing_provided():
    prefs = UserPreferences()
    assert prefs.activities == []
    assert prefs.travel_mode == "walk"
    assert prefs.min_rating == 0
    assert prefs.importance.affordability == 3


def test_accepts_camelcase_wire_format():
    prefs = UserPreferences.model_validate(
        {
            "activities": ["gym", "yoga"],
            "budgetBand": {"min": 0, "max": 80, "currency": "USD", "period": "month"},
            "maxTravelMinutes": 20,
            "travelMode": "transit",
            "minRating": 4.2,
        }
    )
    assert prefs.max_travel_minutes == 20
    assert prefs.budget_band.max == 80
    assert prefs.travel_mode == "transit"


def test_round_trips_back_to_camelcase():
    prefs = UserPreferences(activities=["gym"], max_travel_minutes=15)
    dumped = prefs.model_dump(by_alias=True)
    assert dumped["maxTravelMinutes"] == 15
    assert "max_travel_minutes" not in dumped
