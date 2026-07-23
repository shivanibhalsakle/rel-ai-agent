"""
Wraps Google's Weather API (forecast.hours endpoint). Confirmed against the
live docs before writing this — Google's response nests each value with its
own unit (e.g. temperature.degrees + temperature.unit), so we carry the unit
through explicitly rather than assuming Celsius, since Google doesn't
guarantee which unit system a request returns without an explicit param.
"""
import httpx2 as httpx  # httpx is unmaintained upstream; httpx2 is its API-compatible successor
from pydantic import BaseModel

from app.core.cache import get_or_fetch
from app.core.config import get_settings

FORECAST_HOURS_URL = "https://weather.googleapis.com/v1/forecast/hours:lookup"
CACHE_TTL_SECONDS = 60 * 30  # 30 min — weather is the most time-sensitive of the four providers


class HourlyForecast(BaseModel):
    start_time: str  # ISO 8601, UTC
    is_daytime: bool
    condition: str
    condition_type: str
    temperature_degrees: float
    temperature_unit: str
    feels_like_degrees: float | None = None
    humidity_percent: int | None = None
    uv_index: int | None = None
    precipitation_probability_percent: int | None = None
    wind_speed: float | None = None
    wind_speed_unit: str | None = None
    cloud_cover_percent: int | None = None


class WeatherProvider:
    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.google_maps_api_key
        if not self._api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY is not set.")

    async def get_hourly_forecast(self, lat: float, lng: float, hours: int = 24) -> list[HourlyForecast]:
        """Single page only (max 24 hours) — enough for "best time today"
        style questions, which is all the MVP weather-scheduling feature
        needs. Multi-day forecasts (nextPageToken pagination) can be added
        later if a use case actually needs them."""
        hours = min(hours, 24)
        result = await get_or_fetch(
            provider="weather_hourly",
            params={"lat": round(lat, 3), "lng": round(lng, 3), "hours": hours},
            ttl_seconds=CACHE_TTL_SECONDS,
            fetch_fn=lambda: self._fetch_hourly_forecast(lat, lng, hours),
            model_type=HourlyForecast,
            is_list=True,
        )
        return result or []

    async def _fetch_hourly_forecast(self, lat: float, lng: float, hours: int) -> list[HourlyForecast]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                FORECAST_HOURS_URL,
                params={
                    "key": self._api_key,
                    "location.latitude": lat,
                    "location.longitude": lng,
                    "hours": hours,
                    "pageSize": hours,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return [self._to_forecast(h) for h in data.get("forecastHours", [])]

    @staticmethod
    def _to_forecast(hour: dict) -> HourlyForecast:
        temperature = hour.get("temperature", {})
        feels_like = hour.get("feelsLikeTemperature", {})
        precipitation = hour.get("precipitation", {}).get("probability", {})
        wind = hour.get("wind", {}).get("speed", {})
        condition = hour.get("weatherCondition", {})

        return HourlyForecast(
            start_time=hour.get("interval", {}).get("startTime", ""),
            is_daytime=hour.get("isDaytime", True),
            condition=condition.get("description", {}).get("text", "Unknown"),
            condition_type=condition.get("type", "UNKNOWN"),
            temperature_degrees=temperature.get("degrees", 0.0),
            temperature_unit=temperature.get("unit", "CELSIUS"),
            feels_like_degrees=feels_like.get("degrees"),
            humidity_percent=hour.get("relativeHumidity"),
            uv_index=hour.get("uvIndex"),
            precipitation_probability_percent=precipitation.get("percent"),
            wind_speed=wind.get("value"),
            wind_speed_unit=wind.get("unit"),
            cloud_cover_percent=hour.get("cloudCover"),
        )
