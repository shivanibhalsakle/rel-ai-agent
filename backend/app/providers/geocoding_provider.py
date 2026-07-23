"""
Wraps Google's Geocoding API. Kept as a thin, isolated provider class — not
scattered httpx calls in route handlers — so that (a) callers never touch
Google's raw response shape, and (b) this is the one place that changes if
we ever swap providers (see design doc: "Separate agent logic from provider
logic"). No caching here yet — that's added as a shared wrapping layer in
M2.6 so every provider gets it uniformly instead of reimplementing it four
times.
"""
import httpx
from pydantic import BaseModel

from app.core.config import get_settings

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GeocodeResult(BaseModel):
    formatted_address: str
    lat: float
    lng: float
    place_id: str


class GeocodingProvider:
    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.google_maps_api_key
        if not self._api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY is not set.")

    async def geocode(self, address: str) -> GeocodeResult | None:
        """Address -> coordinates. Returns None if Google found no confident
        match (a bad or ambiguous address) rather than raising — the caller
        decides whether that's a hard error or a "ask the user to clarify"
        moment, which matches the design doc's missing/unavailable-data
        handling rather than crashing the request."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                GEOCODE_URL, params={"address": address, "key": self._api_key}
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "OK" or not data.get("results"):
            return None

        result = data["results"][0]
        location = result["geometry"]["location"]
        return GeocodeResult(
            formatted_address=result["formatted_address"],
            lat=location["lat"],
            lng=location["lng"],
            place_id=result["place_id"],
        )
