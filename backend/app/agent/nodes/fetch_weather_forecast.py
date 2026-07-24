"""
fetch_weather_forecast node (design doc Step 4) — fetches an hourly
forecast for resolved_location, feeding weather_scoring's "best time to
be outside" ranking (M3.5). Only runs for weather intent, mirroring
fetch_place_details' "only runs for the intent that needs it" pattern.

Fetches WeatherProvider's full page (its own documented single-page,
max-24-hour limit) rather than narrowing to "remaining daylight hours
today" here — weather_scoring scores every hour it's given and ranks
best-first, so handing it the whole available window is enough; no
separate time-of-day filtering logic needed in this node.
"""
from app.agent.state import AgentState
from app.providers.weather_provider import WeatherProvider


async def fetch_weather_forecast(state: AgentState, provider: WeatherProvider | None = None) -> dict:
    if state["intent"] != "weather":
        return {}

    location = state.get("resolved_location")
    if not location:
        return {
            "errors": state.get("errors", [])
            + [
                {
                    "node": "fetch_weather_forecast",
                    "message": "No resolved location to fetch weather for.",
                    "retryable": False,
                }
            ]
        }

    provider = provider or WeatherProvider()
    forecasts = await provider.get_hourly_forecast(location["lat"], location["lng"])
    return {"weather_data": forecasts}
