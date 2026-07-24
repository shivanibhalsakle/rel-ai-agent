"""
Wraps Google Calendar API v3 and its OAuth 2.0 token endpoints. Same
provider-abstraction pattern as places_provider.py/weather_provider.py --
raw REST via httpx2, no heavy SDK -- but this provider differs from the
others in one respect: it mints and refreshes its own per-user credentials
(an OAuth access/refresh token pair) rather than using one shared API key.

Token *persistence* lives in CalendarRepository (M8.3,
db/repositories/calendar_repository.py) -- this class only knows how to
talk to Google, never how to store or look up a token. Keeping those
separate means the one place a raw access/refresh token pair ever touches
disk is auditable in isolation from the (much larger) surface of "how do we
call Google's REST API."

No caching here, unlike the other providers -- deliberate, not an
oversight. Free/busy is read live (a cached "busy" slot could let a
double-booking suggestion through) and event creation is a write, which
must never be replayed from a cache.

Scopes requested at connect time (design doc 3.9/Step 5):
  - calendar.freebusy: read-only busy/free, used immediately once connected.
  - calendar.events: create events, but only ever invoked after a
    request_user_approval interrupt confirms one specific event -- gated at
    the graph level (M8.5/M8.6), not by OAuth scope granularity. Google
    doesn't offer a narrower "create, but only this one event" scope, so
    the per-event confirmation is enforced entirely in our own code, same
    as the design doc's framing ("approval is a graph interrupt, not a
    prompt instruction").
access_type=offline + prompt=consent are both required to guarantee Google
returns a refresh_token on first connect -- omitting either is a common
bug (Google silently omits refresh_token on a repeat consent screen
without prompt=consent).
"""
import time
from urllib.parse import urlencode

import httpx2 as httpx  # httpx is unmaintained upstream; httpx2 is its API-compatible successor
from pydantic import BaseModel

from app.core.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/calendar.events",
]

PRIMARY_CALENDAR_ID = "primary"


class CalendarTokens(BaseModel):
    access_token: str
    # None on a refresh response -- Google only issues a new refresh_token
    # on the *first* consent grant, not on subsequent token refreshes. See
    # CalendarProvider.refresh(), which carries the original forward.
    refresh_token: str | None = None
    expires_at: float  # epoch seconds, computed from expires_in at fetch time


class BusyInterval(BaseModel):
    start: str  # ISO 8601
    end: str


class CalendarProvider:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ):
        settings = get_settings()
        self._client_id = client_id or settings.google_calendar_client_id
        self._client_secret = client_secret or settings.google_calendar_client_secret
        self._redirect_uri = redirect_uri or settings.google_calendar_redirect_uri
        if not (self._client_id and self._client_secret and self._redirect_uri):
            raise RuntimeError(
                "Google Calendar OAuth is not configured "
                "(GOOGLE_CALENDAR_CLIENT_ID/SECRET/REDIRECT_URI)."
            )

    def authorization_url(self, state: str) -> str:
        """`state` should be an opaque, unguessable token the caller can
        verify on callback (e.g. tying the callback back to the right
        user_id) -- see calendar_repository/M8.3 for how that's minted and
        checked. This method has no opinion on what `state` contains."""
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> CalendarTokens:
        """One-time exchange of the authorization code the OAuth redirect
        handed back, for an access/refresh token pair."""
        return await self._token_request(
            {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            }
        )

    async def refresh(self, refresh_token: str) -> CalendarTokens:
        """Access tokens are short-lived (~1hr) -- callers refresh using
        the stored refresh_token rather than re-running the consent flow."""
        tokens = await self._token_request(
            {
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            }
        )
        # Google omits refresh_token from a refresh response -- carry the
        # original forward so callers never have to special-case this.
        if tokens.refresh_token is None:
            tokens = tokens.model_copy(update={"refresh_token": refresh_token})
        return tokens

    async def _token_request(self, data: dict) -> CalendarTokens:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(TOKEN_URL, data=data)
            resp.raise_for_status()
            body = resp.json()

        return CalendarTokens(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=time.time() + body.get("expires_in", 3600),
        )

    async def get_freebusy(
        self,
        access_token: str,
        time_min: str,
        time_max: str,
        calendar_id: str = PRIMARY_CALENDAR_ID,
    ) -> list[BusyInterval]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                FREEBUSY_URL,
                headers=self._headers(access_token),
                json={"timeMin": time_min, "timeMax": time_max, "items": [{"id": calendar_id}]},
            )
            resp.raise_for_status()
            body = resp.json()

        busy = body.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        return [BusyInterval(start=b["start"], end=b["end"]) for b in busy]

    async def create_event(
        self,
        access_token: str,
        title: str,
        start: str,
        end: str,
        location: str | None = None,
        calendar_id: str = PRIMARY_CALENDAR_ID,
    ) -> str:
        """Returns the created event's Google Calendar event id. This
        method enforces nothing about *whether* it should be called --
        same division of responsibility as PlacesProvider.get_reviews'
        cost-gating comment. The caller (create_calendar_event node, M8.6)
        is solely responsible for never invoking this without a confirmed
        approval record; M8.8's test asserts that responsibility is
        actually met."""
        body: dict = {"summary": title, "start": {"dateTime": start}, "end": {"dateTime": end}}
        if location:
            body["location"] = location

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                EVENTS_URL.format(calendar_id=calendar_id),
                headers=self._headers(access_token),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        return data["id"]

    @staticmethod
    def _headers(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
