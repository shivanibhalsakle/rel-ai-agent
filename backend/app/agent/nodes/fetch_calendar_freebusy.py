"""
fetch_calendar_freebusy node (design doc Step 4 node table + control-flow
diagram: "weather -> fetch_weather -> (fetch_calendar_freebusy if
connected) -> score_recommendations"). Read-only -- this node never writes
anything to Google Calendar, only reads busy/free.

Only reachable for weather intent, and only when the graph's own routing
(_route_after_weather in agent/graph.py) has already confirmed the user
has a calendar connected -- checked again here defensively (mirrors
fetch_weather_forecast/fetch_place_details' own intent guards) so this
node is safe to call directly in a test without needing to fake the whole
graph's routing decision.

What "inform scheduling suggestions" means concretely: weather_scoring.py
scores whatever forecast hours it's handed and explicitly documents that
free/busy filtering is the CALLER's job ("callers should already have
narrowed forecasts to the relevant window... e.g. free/busy-checked
slots"). This node is that caller-side narrowing -- it fetches busy
intervals for the same window fetch_weather_forecast already covered, then
drops any forecast hour that falls inside a busy interval from
weather_data before score_recommendations ever sees it. No separate
"exclude busy hours" concept needs to exist inside weather_scoring itself.

Fails open, not closed: any error here (expired token needing a refresh
that itself fails, a Calendar API error, malformed data) degrades to
"show the full, unfiltered forecast" rather than blocking the weather
recommendation entirely -- consistent with generate_route_candidates/
fetch_place_details' precedent of reporting into state["errors"] and
returning gracefully rather than raising. A user who can't get
busy-aware suggestions right now should still get weather suggestions.
"""
import time
from datetime import datetime, timezone

from app.agent.state import AgentState
from app.db.repositories import calendar_repository
from app.providers.calendar_provider import BusyInterval, CalendarProvider
from app.providers.weather_provider import HourlyForecast


def _parse(iso_time: str) -> datetime:
    return datetime.fromisoformat(iso_time.replace("Z", "+00:00"))


def _overlaps_any(forecast_time: datetime, busy: list[BusyInterval]) -> bool:
    return any(_parse(b.start) <= forecast_time < _parse(b.end) for b in busy)


async def fetch_calendar_freebusy(
    state: AgentState,
    provider: CalendarProvider | None = None,
    repo=calendar_repository,
) -> dict:
    if state["intent"] != "weather":
        return {}

    # Checked before the repo.get_tokens read on purpose: if there's no
    # forecast to filter (empty on a clean turn, or empty because
    # fetch_weather_forecast itself already degraded on an error), there's
    # nothing this node could do even for a connected user -- no reason to
    # spend a Firestore read finding that out. Also means an
    # already-degraded weather turn never touches Firestore at all here,
    # which is what lets the graph's integration tests reach this node
    # safely with an empty forecast without needing to fake it.
    forecasts: list[HourlyForecast] = state.get("weather_data") or []
    if not forecasts:
        return {}

    uid = state["user_id"]
    tokens = repo.get_tokens(uid)
    if tokens is None:
        return {}  # not connected -- nothing to do

    provider = provider or CalendarProvider()

    try:
        if tokens.expires_at <= time.time():
            tokens = await provider.refresh(tokens.refresh_token)
            repo.save_tokens(uid, tokens)

        times = sorted(f.start_time for f in forecasts)
        busy = await provider.get_freebusy(tokens.access_token, time_min=times[0], time_max=times[-1])
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see module docstring on failing open
        return {
            "errors": state.get("errors", [])
            + [{"node": "fetch_calendar_freebusy", "message": str(exc), "retryable": True}]
        }

    freebusy_dicts = [b.model_dump() for b in busy]
    if not busy:
        return {"calendar_freebusy": freebusy_dicts}

    filtered = [f for f in forecasts if not _overlaps_any(_parse(f.start_time).astimezone(timezone.utc), busy)]
    return {"calendar_freebusy": freebusy_dicts, "weather_data": filtered}
