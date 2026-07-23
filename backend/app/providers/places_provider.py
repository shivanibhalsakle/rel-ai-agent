"""
Wraps Google's Places API (New). Field masks are the primary cost control
here — the New Places API bills by which field "SKU" tier you request
(Basic / Advanced / Preferred), so requesting only what we actually use
directly controls cost, not just response size (see design doc: "Use field
masks to request only necessary information and control costs").

Search results here intentionally stay in the cheaper Basic tier — enough to
rank and show a shortlist. Richer (paid) details only get fetched later for
the handful of places a user actually looks at, not for every search result.
"""
import httpx
from pydantic import BaseModel

from app.core.config import get_settings

SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

SEARCH_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.types",
        "places.currentOpeningHours.openNow",
    ]
)


class PlaceCandidate(BaseModel):
    place_id: str
    name: str
    address: str | None = None
    lat: float
    lng: float
    rating: float | None = None
    user_rating_count: int | None = None
    price_level: str | None = None
    types: list[str] = []
    open_now: bool | None = None


class PlacesProvider:
    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self._api_key = api_key or settings.google_maps_api_key
        if not self._api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY is not set.")

    def _headers(self, field_mask: str) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": field_mask,
        }

    async def search_nearby(
        self,
        lat: float,
        lng: float,
        radius_meters: float,
        included_types: list[str],
        max_results: int = 15,
    ) -> list[PlaceCandidate]:
        """Bounded shortlist by design (max_results caps it) — the pattern is
        cheap/broad search first, then selective Details fetches later only
        for shortlisted candidates a scoring step actually picks, never full
        Details for every nearby result."""
        body = {
            "includedTypes": included_types,
            "maxResultCount": max_results,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_meters,
                }
            },
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                SEARCH_NEARBY_URL, json=body, headers=self._headers(SEARCH_FIELD_MASK)
            )
            resp.raise_for_status()
            data = resp.json()

        return [self._to_candidate(p) for p in data.get("places", [])]

    async def search_text(self, query: str, max_results: int = 15) -> list[PlaceCandidate]:
        body = {"textQuery": query, "maxResultCount": max_results}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                SEARCH_TEXT_URL, json=body, headers=self._headers(SEARCH_FIELD_MASK)
            )
            resp.raise_for_status()
            data = resp.json()

        return [self._to_candidate(p) for p in data.get("places", [])]

    @staticmethod
    def _to_candidate(place: dict) -> PlaceCandidate:
        location = place.get("location", {})
        return PlaceCandidate(
            place_id=place["id"],
            name=place.get("displayName", {}).get("text", "Unknown"),
            address=place.get("formattedAddress"),
            lat=location.get("latitude", 0.0),
            lng=location.get("longitude", 0.0),
            rating=place.get("rating"),
            user_rating_count=place.get("userRatingCount"),
            price_level=place.get("priceLevel"),
            types=place.get("types", []),
            open_now=place.get("currentOpeningHours", {}).get("openNow"),
        )
