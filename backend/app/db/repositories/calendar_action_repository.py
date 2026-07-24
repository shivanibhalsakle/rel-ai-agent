"""
Stores users/{userId}/calendarActions/{actionId} -- an append-only audit
trail of confirmed calendar-event proposals, per the design doc's
Firestore data model (Step 6). Exists independently of whether the actual
Google Calendar API write succeeded: a failed create_event call still gets
a record (status "confirmed" with no googleCalendarEventId, or "failed"
with a reason), which is what lets a settings/history view -- and M8.8's
test -- check against real persisted state, not just in-memory state that
vanishes at the end of one request.

Deliberately only ever called from the confirmed path (see
create_calendar_event.py) -- despite the design doc's status enum listing
"proposed"/"rejected" as states too, this repository never writes either
of those. A rejected proposal has nothing worth persisting (see
calendar_rejected's docstring in create_calendar_event.py); "proposed"
would only be meaningful if writes happened before confirmation, which
the whole point of the approval gate rules out. "failed" is this
repository's one addition beyond the design doc's original enum -- an
honest label for "we tried to write to Google Calendar and it errored,"
not folded into "confirmed" (which would misleadingly suggest nothing
went wrong) or silently dropped.
"""
from datetime import datetime, timezone

from app.db.firestore_client import get_firestore_client


def _collection(uid: str):
    client = get_firestore_client()
    return client.collection("users").document(uid).collection("calendarActions")


def record_confirmed(uid: str, proposed_event: dict) -> str:
    """Called once, at the start of create_calendar_event, immediately
    after approval_decision is confirmed True and before the actual
    Google Calendar API call -- so even a request that crashes mid-call
    still leaves a "confirmed" record behind, not silence. Returns the
    new action's auto-generated id."""
    doc_ref = _collection(uid).document()
    doc_ref.set(
        {
            "proposedEvent": proposed_event,
            "status": "confirmed",
            "googleCalendarEventId": None,
            "confirmedAt": datetime.now(timezone.utc),
        }
    )
    return doc_ref.id


def mark_created(uid: str, action_id: str, google_calendar_event_id: str) -> None:
    _collection(uid).document(action_id).update(
        {"status": "created", "googleCalendarEventId": google_calendar_event_id}
    )


def mark_failed(uid: str, action_id: str, reason: str) -> None:
    _collection(uid).document(action_id).update({"status": "failed", "failureReason": reason})
