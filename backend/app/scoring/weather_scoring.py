"""
Scores hourly forecast windows for "best time to be outside" recommendations
(design doc Step 3.5 — weather-aware scheduling). Ranks HourlyForecast
entries by comfort: temperature, precipitation chance, wind, humidity, UV,
and daylight.

Unlike fitness_scoring/workspace_scoring, this module doesn't currently read
anything from UserPreferences — there's no "ideal temperature" or "wind
tolerance" field in the schema yet, and weather comfort is closer to an
objective property of the hour than a personal taste. `preferences` is
still accepted (and ignored) so the call signature matches the other three
scoring modules and doesn't need to change if a personalized comfort
preference gets added later.

Known simplification: wind_speed isn't unit-converted (Google's Weather API
can return km/h or mph depending on request locale, and WeatherProvider
doesn't currently pin a units system). The comfort range used here is wide
enough to be roughly sane either way, but this isn't a precise conversion —
documented, not silently assumed correct.
"""
from app.providers.weather_provider import HourlyForecast
from app.schemas.preferences import UserPreferences
from app.scoring.base import ScoreComponent, ScoredResult, normalize, rank, to_scored_result

PRECIP_WEIGHT = 4.0
TEMP_COMFORT_WEIGHT = 3.0
WIND_WEIGHT = 1.5
HUMIDITY_WEIGHT = 1.0
UV_WEIGHT = 1.0
DAYLIGHT_WEIGHT = 1.0

# Comfort band in Celsius: full score between ideal_low/ideal_high, tapering
# to 0 at floor/ceiling. Chosen for "comfortable to be outside and active,"
# not a claim about anyone's personal preference.
_FLOOR_C = -5.0
_IDEAL_LOW_C = 12.0
_IDEAL_HIGH_C = 24.0
_CEILING_C = 35.0

# Generous upper bound so a moderate breeze doesn't tank the score — this is
# the "documented simplification" from the module docstring re: units.
_WIND_HIGH_BOUND = 40.0

_AFTER_DARK_SCORE = 0.5


def _to_celsius(value: float, unit: str) -> float:
    if unit == "FAHRENHEIT":
        return (value - 32) * 5 / 9
    return value  # CELSIUS or unrecognized unit: assume already Celsius


def _temperature_comfort(temp_c: float) -> float:
    if temp_c < _IDEAL_LOW_C:
        return normalize(temp_c, low=_FLOOR_C, high=_IDEAL_LOW_C)
    if temp_c > _IDEAL_HIGH_C:
        return normalize(temp_c, low=_IDEAL_HIGH_C, high=_CEILING_C, invert=True)
    return 1.0


def _unit_symbol(unit: str) -> str:
    return {"CELSIUS": "C", "FAHRENHEIT": "F"}.get(unit, "")


def score_and_rank(
    forecasts: list[HourlyForecast],
    preferences: UserPreferences | None = None,
) -> list[ScoredResult[HourlyForecast]]:
    """Score and rank hourly forecast windows, best first. No filtering —
    every hour passed in gets scored; callers should already have narrowed
    `forecasts` to the relevant window (e.g. remaining daylight hours, or
    free/busy-checked slots) before calling this."""
    del preferences  # not yet used — see module docstring

    results: list[ScoredResult[HourlyForecast]] = []
    for forecast in forecasts:
        temp_c = _to_celsius(forecast.temperature_degrees, forecast.temperature_unit)
        components: list[ScoreComponent] = [
            ScoreComponent(
                factor="temperature",
                score=_temperature_comfort(temp_c),
                weight=TEMP_COMFORT_WEIGHT,
                detail=f"{forecast.temperature_degrees:g}°{_unit_symbol(forecast.temperature_unit)}",
                confidence="verified",
            ),
            ScoreComponent(
                factor="daylight",
                score=1.0 if forecast.is_daytime else _AFTER_DARK_SCORE,
                weight=DAYLIGHT_WEIGHT,
                detail="Daytime" if forecast.is_daytime else "After dark",
                confidence="verified",
            ),
        ]

        if forecast.precipitation_probability_percent is not None:
            precip = forecast.precipitation_probability_percent
            components.append(
                ScoreComponent(
                    factor="precipitation",
                    score=normalize(precip, low=0, high=100, invert=True),
                    weight=PRECIP_WEIGHT,
                    detail=f"{precip}% chance of precipitation",
                    confidence="verified",
                )
            )

        if forecast.wind_speed is not None:
            unit_label = f" {forecast.wind_speed_unit}" if forecast.wind_speed_unit else ""
            components.append(
                ScoreComponent(
                    factor="wind",
                    score=normalize(forecast.wind_speed, low=0, high=_WIND_HIGH_BOUND, invert=True),
                    weight=WIND_WEIGHT,
                    detail=f"{forecast.wind_speed:g}{unit_label} wind",
                    confidence="verified",
                )
            )

        if forecast.humidity_percent is not None:
            components.append(
                ScoreComponent(
                    factor="humidity",
                    score=normalize(forecast.humidity_percent, low=30, high=90, invert=True),
                    weight=HUMIDITY_WEIGHT,
                    detail=f"{forecast.humidity_percent}% humidity",
                    confidence="verified",
                )
            )

        if forecast.uv_index is not None:
            components.append(
                ScoreComponent(
                    factor="uv_index",
                    score=normalize(forecast.uv_index, low=0, high=11, invert=True),
                    weight=UV_WEIGHT,
                    detail=f"UV index {forecast.uv_index}",
                    confidence="verified",
                )
            )

        results.append(to_scored_result(item=forecast, components=components))

    return rank(results)
