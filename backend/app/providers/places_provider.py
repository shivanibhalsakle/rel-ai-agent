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
import httpx2 as httpx  # httpx is unmaintained upstream; httpx2 is its API-compatible successor
from pydantic import BaseModel

from app.core.cache import get_or_fetch
from app.core.config import get_settings

SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
CACHE_TTL_SECONDS = 60 * 60 * 24  # 1 day — ratings/hours drift slowly, but do drift

# Place Details (New), reviews field only. This is Google's priciest Places
# SKU (Enterprise + Atmosphere, ~$0.04/call per the rates checked during
# Milestone 3's research) -- callers must never invoke get_reviews() for
# every search result. See agent/nodes/fetch_place_details.py (M4.5) for
# the actual selective-shortlist gating; this method itself has no
# knowledge of "how many is too many," on purpose -- that policy belongs
# to the caller, not the provider.
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
REVIEWS_FIELD_MASK = "reviews.text.text"
REVIEWS_CACHE_TTL_SECONDS = 60 * 60 * 24  # 1 day — reviews change slowly enough

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


class ReviewText(BaseModel):
    """Wrapper so a plain list[str] can go through get_or_fetch's
    is_list/model_type caching mechanics, which require a BaseModel."""

    text: str


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
        params = {
            "lat": round(lat, 4),
            "lng": round(lng, 4),
            "radius_meters": radius_meters,
            "included_types": sorted(included_types),
            "max_results": max_results,
        }
        result = await get_or_fetch(
            provider="places_nearby",
            params=params,
            ttl_seconds=CACHE_TTL_SECONDS,
            fetch_fn=lambda: self._fetch_search_nearby(lat, lng, radius_meters, included_types, max_results),
            model_type=PlaceCandidate,
            is_list=True,
        )
        return result or []

    async def _fetch_search_nearby(
        self, lat: float, lng: float, radius_meters: float, included_types: list[str], max_results: int
    ) -> list[PlaceCandidate]:
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
        result = await get_or_fetch(
            provider="places_text",
            params={"query": query.strip().lower(), "max_results": max_results},
            ttl_seconds=CACHE_TTL_SECONDS,
            fetch_fn=lambda: self._fetch_search_text(query, max_results),
            model_type=PlaceCandidate,
            is_list=True,
        )
        return result or []

    async def _fetch_search_text(self, query: str, max_results: int) -> list[PlaceCandidate]:
        body = {"textQuery": query, "maxResultCount": max_results}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                SEARCH_TEXT_URL, json=body, headers=self._headers(SEARCH_FIELD_MASK)
            )
            resp.raise_for_status()
            data = resp.json()

        return [self._to_candidate(p) for p in data.get("places", [])]

    async def get_reviews(self, place_id: str) -> list[str]:
        """Fetches up to a handful of review texts for one place. Real
        money per call (see module-level comment) -- callers are
        responsible for only calling this for a small, deliberately chosen
        shortlist, never for every search result."""
        result = await get_or_fetch(
            provider="place_reviews",
            params={"place_id": place_id},
            ttl_seconds=REVIEWS_CACHE_TTL_SECONDS,
            fetch_fn=lambda: self._fetch_reviews(place_id),
            model_type=ReviewText,
            is_list=True,
        )
        return [item.text for item in (result or [])]

    async def _fetch_reviews(self, place_id: str) -> list[ReviewText]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                DETAILS_URL.format(place_id=place_id), headers=self._headers(REVIEWS_FIELD_MASK)
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            ReviewText(text=review["text"]["text"])
            for review in data.get("reviews", [])
            if review.get("text", {}).get("text")
        ]

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
