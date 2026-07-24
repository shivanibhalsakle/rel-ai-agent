import time

from app.agent.nodes.fetch_calendar_freebusy import fetch_calendar_freebusy
from app.agent.state import new_agent_state
from app.providers.calendar_provider import BusyInterval, CalendarTokens
from app.providers.weather_provider import HourlyForecast


class _StubRepo:
    def __init__(self, tokens: CalendarTokens | None):
        self._tokens = tokens
        self.saved: list[tuple[str, CalendarTokens]] = []

    def get_tokens(self, uid):
        return self._tokens

    def save_tokens(self, uid, tokens):
        self.saved.append((uid, tokens))
        self._tokens = tokens


class _StubProvider:
    def __init__(self, busy: list[BusyInterval] | None = None, refreshed: CalendarTokens | None = None):
        self._busy = busy or []
        self._refreshed = refreshed
        self.refresh_called_with: str | None = None
        self.freebusy_called_with: tuple | None = None

    async def refresh(self, refresh_token):
        self.refresh_called_with = refresh_token
        return self._refreshed

    async def get_freebusy(self, access_token, time_min, time_max, calendar_id="primary"):
        self.freebusy_called_with = (access_token, time_min, time_max)
        return self._busy


def _forecast(start_time: str) -> HourlyForecast:
    return HourlyForecast(
        start_time=start_time,
        is_daytime=True,
        condition="Clear",
        condition_type="CLEAR",
        temperature_degrees=20.0,
        temperature_unit="CELSIUS",
    )


def _weather_state(forecasts):
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "weather"
    state["weather_data"] = forecasts
    return state


def _valid_tokens():
    return CalendarTokens(access_token="access-1", refresh_token="refresh-1", expires_at=time.time() + 3600)


async def test_non_weather_intent_is_a_no_op():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["intent"] = "fitness"

    update = await fetch_calendar_freebusy(state, repo=_StubRepo(_valid_tokens()))

    assert update == {}


async def test_not_connected_is_a_no_op():
    state = _weather_state([_forecast("2026-07-25T14:00:00Z")])

    update = await fetch_calendar_freebusy(state, repo=_StubRepo(None))

    assert update == {}


async def test_no_forecasts_is_a_no_op():
    state = _weather_state([])

    update = await fetch_calendar_freebusy(state, repo=_StubRepo(_valid_tokens()))

    assert update == {}


async def test_filters_out_forecast_hours_that_overlap_a_busy_interval():
    forecasts = [
        _forecast("2026-07-25T14:00:00Z"),  # busy
        _forecast("2026-07-25T16:00:00Z"),  # free
    ]
    state = _weather_state(forecasts)
    busy = [BusyInterval(start="2026-07-25T13:30:00Z", end="2026-07-25T15:00:00Z")]
    provider = _StubProvider(busy=busy)

    update = await fetch_calendar_freebusy(state, provider=provider, repo=_StubRepo(_valid_tokens()))

    assert [f.start_time for f in update["weather_data"]] == ["2026-07-25T16:00:00Z"]
    assert update["calendar_freebusy"] == [{"start": busy[0].start, "end": busy[0].end}]


async def test_no_busy_intervals_leaves_forecast_untouched_but_records_empty_freebusy():
    forecasts = [_forecast("2026-07-25T14:00:00Z")]
    state = _weather_state(forecasts)
    provider = _StubProvider(busy=[])

    update = await fetch_calendar_freebusy(state, provider=provider, repo=_StubRepo(_valid_tokens()))

    assert update == {"calendar_freebusy": []}
    assert "weather_data" not in update  # unchanged -- caller keeps the original list


async def test_expired_token_is_refreshed_and_saved_before_the_freebusy_call():
    expired = CalendarTokens(access_token="old", refresh_token="refresh-1", expires_at=time.time() - 10)
    refreshed = CalendarTokens(access_token="new-access", refresh_token="refresh-1", expires_at=time.time() + 3600)
    repo = _StubRepo(expired)
    provider = _StubProvider(busy=[], refreshed=refreshed)
    state = _weather_state([_forecast("2026-07-25T14:00:00Z")])

    await fetch_calendar_freebusy(state, provider=provider, repo=repo)

    assert provider.refresh_called_with == "refresh-1"
    assert repo.saved == [("u1", refreshed)]
    assert provider.freebusy_called_with[0] == "new-access"


async def test_provider_error_degrades_gracefully_instead_of_raising():
    class _RaisingProvider(_StubProvider):
        async def get_freebusy(self, *args, **kwargs):
            raise RuntimeError("Calendar API unavailable")

    state = _weather_state([_forecast("2026-07-25T14:00:00Z")])

    update = await fetch_calendar_freebusy(state, provider=_RaisingProvider(), repo=_StubRepo(_valid_tokens()))

    assert "weather_data" not in update  # original forecast preserved by the caller
    assert update["errors"][0]["node"] == "fetch_calendar_freebusy"
