"""
Signs/verifies the OAuth `state` param carried through the Google Calendar
consent redirect: POST /v1/calendar/connect (authenticated, has a Bearer
token) -> Google's consent screen -> GET /v1/calendar/oauth/callback (a
plain browser redirect Google issues, carrying no Authorization header
at all). `state` is the only channel available to tell the callback which
user_id initiated the connect request, so it has to be tamper-evident:
HMAC-signed, not just base64-encoded, so a forged or edited state value
fails verification instead of silently attaching a Calendar connection to
the wrong user. Stdlib only (hmac/hashlib) -- a full JWT library is more
than this narrow, single-purpose, short-lived token needs.
"""
import base64
import hashlib
import hmac
import json
import time

from app.core.config import get_settings

_STATE_TTL_SECONDS = 60 * 10  # 10 min -- plenty to complete Google's consent screen


class InvalidOAuthState(Exception):
    pass


def _secret() -> bytes:
    settings = get_settings()
    if not settings.oauth_state_secret_key:
        raise RuntimeError("OAUTH_STATE_SECRET_KEY is not set.")
    return settings.oauth_state_secret_key.encode()


def make_state(uid: str) -> str:
    payload_b64 = base64.urlsafe_b64encode(json.dumps({"uid": uid, "iat": time.time()}).encode()).decode()
    signature = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_state(state: str) -> str:
    """Returns the uid if `state` is authentic and unexpired. Raises
    InvalidOAuthState otherwise -- callers (the oauth callback route)
    should treat that as a 400, never as "no user" (there's no valid
    no-user case here, unlike get_tokens' None-means-not-connected)."""
    try:
        payload_b64, signature = state.split(".", 1)
    except ValueError:
        raise InvalidOAuthState("Malformed state.") from None

    expected = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise InvalidOAuthState("State signature mismatch.")

    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
    except (ValueError, json.JSONDecodeError):
        raise InvalidOAuthState("Malformed state payload.") from None

    if time.time() - payload["iat"] > _STATE_TTL_SECONDS:
        raise InvalidOAuthState("State expired -- restart the connect flow.")

    return payload["uid"]
