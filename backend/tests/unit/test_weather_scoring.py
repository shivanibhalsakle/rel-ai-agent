from app.providers.weather_provider import HourlyForecast
from app.scoring.weather_scoring import score_and_rank


def _forecast(**overrides) -> HourlyForecast:
    defaults = dict(
        start_time="2026-07-23T14:00:00Z",
        is_daytime=True,
        condition="Clear",
        condition_type="CLEAR",
        temperature_degrees=18.0,
        temperature_unit="CELSIUS",
    )
    defaults.update(overrides)
    return HourlyForecast(**defaults)


def test_ideal_temperature_beats_extremes():
    ideal = _forecast(start_time="ideal", temperature_degrees=18.0)
    freezing = _forecast(start_time="freezing", temperature_degrees=-10.0)
    scorching = _forecast(start_time="scorching", temperature_degrees=40.0)

    results = score_and_rank([ideal, freezing, scorching])

    assert results[0].item.start_time == "ideal"
    assert results[-1].item.start_time in ("freezing", "scorching")


def test_fahrenheit_is_converted_before_scoring():
    # 70F ~ 21.1C, comfortably inside the ideal band.
    comfortable = _forecast(start_time="comfortable", temperature_degrees=70.0, temperature_unit="FAHRENHEIT")
    # 95F ~ 35C, at the ceiling of the comfort range.
    hot = _forecast(start_time="hot", temperature_degrees=95.0, temperature_unit="FAHRENHEIT")

    results = score_and_rank([comfortable, hot])

    assert [r.item.start_time for r in results] == ["comfortable", "hot"]


def test_lower_precipitation_chance_wins():
    dry = _forecast(start_time="dry", precipitation_probability_percent=5)
    wet = _forecast(start_time="wet", precipitation_probability_percent=90)

    results = score_and_rank([dry, wet])

    assert [r.item.start_time for r in results] == ["dry", "wet"]


def test_daytime_beats_after_dark_all_else_equal():
    day = _forecast(start_time="day", is_daytime=True)
    night = _forecast(start_time="night", is_daytime=False)

    results = score_and_rank([day, night])

    assert [r.item.start_time for r in results] == ["day", "night"]


def test_missing_optional_fields_only_scores_temperature_and_daylight():
    forecast = _forecast(start_time="sparse")

    results = score_and_rank([forecast])

    factors = {c.factor for c in results[0].components}
    assert factors == {"temperature", "daylight"}


def test_all_optional_fields_present_are_scored():
    forecast = _forecast(
        start_time="full",
        precipitation_probability_percent=10,
        wind_speed=8.0,
        wind_speed_unit="KILOMETERS_PER_HOUR",
        humidity_percent=45,
        uv_index=3,
    )

    results = score_and_rank([forecast])

    factors = {c.factor for c in results[0].components}
    assert factors == {"temperature", "daylight", "precipitation", "wind", "humidity", "uv_index"}
