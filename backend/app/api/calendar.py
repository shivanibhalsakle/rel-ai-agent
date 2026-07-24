"""
Google Calendar connect/disconnect (design doc Step 7: POST /v1/calendar/connect,
POST /v1/calendar/disconnect) plus the OAuth redirect callback those two
endpoints require in practice but the design doc's contract sketch doesn't
spell out (it predates working through the actual OAuth mechanics).

Why /connect can't literally return `{"status": "connected"}` synchronously,
as the doc's one-line example implies: OAuth 2.0's authorization-code flow
requires the browser itself to leave our site, grant consent on Google's
own domain, and be redirected back -- there is no way to complete that
inside a single POST request/response. So /connect instead returns an
`authorizationUrl` for the frontend to navigate the browser to; "connected"
only becomes true once GET /oauth/callback (Google's redirect target,
registered as GOOGLE_CALENDAR_REDIRECT_URI) receives the authorization
code and exchanges it. The callback is a plain browser GET Google issues
directly -- no Authorization header is possible there, which is exactly
why app/core/oauth_state.py's signed `state` param exists: it's the only
way the callback learns which authenticated user started the flow.

GET /status is not in the design doc's endpoint list either -- added
because the settings UI (M8.7) needs to know whether calendar is already
connected when the page loads, to render "Connect" vs. "Disconnect"
correctly. Same category of doc-vs-build gap as M4.5's location_query or
M6.4's explanations dict: a real gap in the original sketch, filled in
and noted explicitly rather than silently.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.oauth_state import InvalidOAuthState, make_state, verify_state
from app.db.repositories import calendar_repository
from app.providers.calendar_provider import CalendarProvider

router = APIRouter()


@router.post("/calendar/connect")
async def connect(user: dict = Depends(get_current_user)) -> dict:
    provider = CalendarProvider()
    state = make_state(user["uid"])
    return {"authorizationUrl": provider.authorization_url(state)}


@router.post("/calendar/disconnect")
async def disconnect(user: dict = Depends(get_current_user)) -> dict:
    # Deleting the token doc is the entire revoke -- see
    # calendar_repository.delete_tokens' docstring for why this alone is
    # sufficient to make every downstream calendar read/write fail closed
    # immediately, per the design doc's "revoking immediately stops all
    # calendar reads/writes" requirement.
    calendar_repository.delete_tokens(user["uid"])
    return {"status": "disconnected"}


@router.get("/calendar/status")
async def status(user: dict = Depends(get_current_user)) -> dict:
    return {"connected": calendar_repository.is_connected(user["uid"])}


@router.get("/calendar/oauth/callback")
async def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    settings = get_settings()

    if error or not code or not state:
        # e.g. the user clicked "Cancel" on Google's consent screen --
        # a normal outcome, not a server error.
        return RedirectResponse(f"{settings.frontend_base_url}/settings?calendar=cancelled")

    try:
        uid = verify_state(state)
    except InvalidOAuthState as exc:
        # Unlike a cancelled consent screen, this means the state didn't
        # verify -- surfaced distinctly (400) rather than folded into the
        # "cancelled" redirect, since it's a signal worth being able to
        # tell apart in logs (forged/expired state vs. a user backing out).
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    provider = CalendarProvider()
    tokens = await provider.exchange_code(code)
    calendar_repository.save_tokens(uid, tokens)

    return RedirectResponse(f"{settings.frontend_base_url}/settings?calendar=connected")
