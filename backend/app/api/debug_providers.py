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
