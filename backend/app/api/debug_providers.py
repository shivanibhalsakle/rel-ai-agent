"""
Manual test endpoints for verifying each provider works against the real
Google APIs while we build them. Rate-limited (not just auth-protected):
unlike our own data routes, every call here spends real money against the
Google Maps Platform key, so beyond requiring auth, each user is also capped
to a sliding-window request rate (see app/core/rate_limit.py) so a stuck
frontend loop or an overeager tester can't run up a surprise bill.
Not meant to be how the agent actually calls providers later — that happens
through LangGraph tool nodes (Milestone 4), not HTTP routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.rate_limit import rate_limit
from app.providers.geocoding_provider import GeocodeResult, GeocodingProvider
from app.providers.places_provider import PlaceCandidate, PlacesProvider
from app.providers.route_provider import RouteProvider, RouteResult
from app.providers.weather_provider import HourlyForecast, WeatherProvider

router = APIRouter()


@router.get("/debug/geocode", response_model=GeocodeResult)
async def debug_geocode(address: str, user: dict = Depends(rate_limit)) -> GeocodeResult:
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
    user: dict = Depends(rate_limit),
) -> list[PlaceCandidate]:
    provider = PlacesProvider()
    return await provider.search_nearby(
        lat=lat, lng=lng, radius_meters=radius_meters, included_types=[place_type]
    )


@router.get("/debug/places/text", response_model=list[PlaceCandidate])
async def debug_places_text(
    query: str, user: dict = Depends(rate_limit)
) -> list[PlaceCandidate]:
    provider = PlacesProvider()
    return await provider.search_text(query)


@router.get("/debug/weather/hourly", response_model=list[HourlyForecast])
async def debug_weather_hourly(
    lat: float, lng: float, hours: int = 12, user: dict = Depends(rate_limit)
) -> list[HourlyForecast]:
    provider = WeatherProvider()
    return await provider.get_hourly_forecast(lat=lat, lng=lng, hours=hours)


@router.get("/debug/route", response_model=RouteResult)
async def debug_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    travel_mode: str = "walk",
    user: dict = Depends(rate_limit),
) -> RouteResult:
    provider = RouteProvider()
    result = await provider.compute_route(origin_lat, origin_lng, dest_lat, dest_lng, travel_mode)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No route found between those points."
        )
    return result
