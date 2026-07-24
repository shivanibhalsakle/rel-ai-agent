from app.agent.nodes.fetch_weather_forecast import fetch_weather_forecast
from app.agent.state import new_agent_state
from app.providers.weather_provider import HourlyForecast


class _StubWeatherProvider:
    def __init__(self, forecasts: list[HourlyForecast]):
        self._forecasts = forecasts
        self.last_lat: float | None = None
        self.last_lng: float | None = None

    async def get_hourly_forecast(self, lat: float, lng: float, hours: int = 24):
        self.last_lat = lat
        self.last_lng = lng
        return self._forecasts


def _forecast(start_time: str = "2026-07-25T14:00:00Z") -> HourlyForecast:
    return HourlyForecast(
        start_time=start_time,
        is_daytime=True,
        condition="Clear",
        condition_type="CLEAR",
        temperature_degrees=20.0,
        temperature_unit="CELSIUS",
    )


def _located_state(intent: str = "weather"):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = intent
    state["resolved_location"] = {"lat": 40.7, "lng": -73.9, "formatted_address": "Union Square, New York, NY"}
    return state


async def test_non_weather_intent_is_a_no_op():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"

    update = await fetch_weather_forecast(state)

    assert update == {}


async def test_no_resolved_location_returns_an_error():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "weather"

    update = await fetch_weather_forecast(state)

    assert "weather_data" not in update
    assert update["errors"][0]["node"] == "fetch_weather_forecast"


async def test_fetches_forecast_for_resolved_location():
    state = _located_state()
    forecasts = [_forecast("2026-07-25T14:00:00Z"), _forecast("2026-07-25T15:00:00Z")]
    stub = _StubWeatherProvider(forecasts)

    update = await fetch_weather_forecast(state, provider=stub)

    assert update["weather_data"] == forecasts
    assert stub.last_lat == 40.7
    assert stub.last_lng == -73.9
