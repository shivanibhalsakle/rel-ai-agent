"""
Manual test endpoints for verifying each provider works against the real
Google APIs while we build them. Auth-protected: unlike our own data routes,
every call here spends real money against the Google Maps Platform key, so
this must never be reachable by anyone but an authenticated project user.
Not meant to be how the agent actually calls providers later — that happens
through LangGraph tool nodes (Milestone 4), not HTTP routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.providers.geocoding_provider import GeocodeResult, GeocodingProvider
from app.providers.places_provider import PlaceCandidate, PlacesProvider

router = APIRouter()


@router.get("/debug/geocode", response_model=GeocodeResult)
async def debug_geocode(address: str, user: dict = Depends(get_current_user)) -> GeocodeResult:
    provider = GeocodingProvider()
    result = await provider.geocode(address)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not geocode '{address}' — try a more specific address.",
        )
    return result


@router.get("/debug/places/nearby", response_model=list[PlaceCandidate])
async def debug_places_nearby(
    lat: float,
    lng: float,
    place_type: str = "gym",
    radius_meters: float = 3000,
    user: dict = Depends(get_current_user),
) -> list[PlaceCandidate]:
    provider = PlacesProvider()
    return await provider.search_nearby(
        lat=lat, lng=lng, radius_meters=radius_meters, included_types=[place_type]
    )


@router.get("/debug/places/text", response_model=list[PlaceCandidate])
async def debug_places_text(
    query: str, user: dict = Depends(get_current_user)
) -> list[PlaceCandidate]:
    provider = PlacesProvider()
    return await provider.search_text(query)
