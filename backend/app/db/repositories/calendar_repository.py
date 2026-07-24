"""
Stores the Google Calendar OAuth token pair at
users/{userId}/calendarConnection/tokens -- server-side only. Per the
design doc (Step 5, line 325; Step 5 privacy notes, line 346), this
document must never be sent to the frontend; only app/api/calendar.py
(and, later, the fetch_calendar_freebusy / create_calendar_event nodes)
read it, to attach a live Authorization header on outbound
CalendarProvider calls. "Encrypted at rest" here means Firestore/Cloud
infra's own default encryption, which the design doc names explicitly as
the intended protection layer for this token (not a bespoke
application-level encryption scheme) -- access control is otherwise the
same as every other users/{userId}/... document: firestore.rules' wildcard
match, plus this repository only ever being called with a caller-supplied,
already-authenticated uid (see app/auth/dependencies.py).

One doc per user, not a subcollection of many -- there's only ever one
Google Calendar connection per user in this product, mirroring
preference_repository.py's single-document-per-concern pattern.
"""
from datetime import datetime, timezone

from app.db.firestore_client import get_firestore_client
from app.providers.calendar_provider import CalendarTokens

_SUBCOLLECTION = "calendarConnection"
_DOC_ID = "tokens"


def _doc_ref(uid: str):
    client = get_firestore_client()
    return client.collection("users").document(uid).collection(_SUBCOLLECTION).document(_DOC_ID)


def save_tokens(uid: str, tokens: CalendarTokens) -> None:
    """Overwrites any prior token doc -- a fresh connect (or a refresh)
    always replaces, never merges, so a stale refresh_token can never
    linger alongside a newer access_token."""
    _doc_ref(uid).set(
        {
            "accessToken": tokens.access_token,
            "refreshToken": tokens.refresh_token,
            "expiresAt": tokens.expires_at,
            "connectedAt": datetime.now(timezone.utc),
        }
    )


def get_tokens(uid: str) -> CalendarTokens | None:
    """None means "not connected" -- every caller (freebusy node, event
    creation node, the settings UI's connected-status check) treats that
    as a normal, expected state, not an error."""
    snapshot = _doc_ref(uid).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict()
    return CalendarTokens(
        access_token=data["accessToken"],
        refresh_token=data.get("refreshToken"),
        expires_at=data["expiresAt"],
    )


def is_connected(uid: str) -> bool:
    return _doc_ref(uid).get().exists


def delete_tokens(uid: str) -> None:
    """Disconnect. Per the design doc: revoking must immediately stop all
    calendar reads/writes -- deleting the token doc achieves that
    structurally (get_tokens returns None on the very next call, so every
    downstream node's "only if calendar connected" check fails closed)
    rather than relying on a separate `connected: bool` flag that could
    drift out of sync with whether a usable token actually still exists."""
    _doc_ref(uid).delete()
