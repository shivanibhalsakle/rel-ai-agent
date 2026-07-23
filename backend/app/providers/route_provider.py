"""
Wraps Google's Routes API (computeRoutes). Field mask kept to exactly the
three fields we use (distance, duration, polyline) — same cost-control
principle as PlacesProvider, since Routes API also bills based on which
fields/route-preference tiers a request includes.
"""
import httpx
from pydantic import BaseModel

from app.core.config import get_settings

COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"

# Our UserPreferences.travel_mode values -> Routes API's TravelMode enum.
_TRAVEL_MODE_MAP = {
    "walk": "WALK",
    "bike": "BICYCLE",
    "transit": "TRANSIT",
    "drive": "DRIVE",
}


class RouteResult(BaseModel):
    distance_meters: float
    duration_seconds: float
    encoded_polyline: str


class RouteProvider:
    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.google_maps_api_key
        if not self._api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY is not set.")

    async def compute_route(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "walk",
    ) -> RouteResult | None:
        google_mode = _TRAVEL_MODE_MAP.get(travel_mode, "WALK")

        body = {
            "origin": {"location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}},
            "destination": {"location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}},
            "travelMode": google_mode,
            "computeAlternativeRoutes": False,
            "units": "METRIC",
        }
        # routingPreference (traffic-aware) is only valid for DRIVE/TWO_WHEELER —
        # sending it for WALK/BICYCLE/TRANSIT causes a request error, so it's
        # conditional rather than always included.
        if google_mode in ("DRIVE", "TWO_WHEELER"):
            body["routingPreference"] = "TRAFFIC_AWARE"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(COMPUTE_ROUTES_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        routes = data.get("routes", [])
        if not routes:
            return None

        route = routes[0]
        duration_str = route.get("duration", "0s")  # e.g. "165s"
        duration_seconds = float(duration_str.rstrip("s")) if duration_str.endswith("s") else 0.0

        return RouteResult(
            distance_meters=route.get("distanceMeters", 0),
            duration_seconds=duration_seconds,
            encoded_polyline=route.get("polyline", {}).get("encodedPolyline", ""),
        )
