"""
Reads and writes users/{userId}/feedback/{feedbackId} -- mirrors
preference_repository.py's shape (a thin Firestore wrapper, nothing
outside this file should know Firestore is the backend).

No feedbackId is chosen by the caller -- each save creates a new
auto-ID document (Firestore's `.document()` with no argument), since
feedback is an append-only event log, not something ever looked up by a
caller-known id or updated in place.
"""
from datetime import datetime, timezone

from firebase_admin import firestore

from app.db.firestore_client import get_firestore_client
from app.schemas.feedback import FeedbackRecord


def _collection(uid: str):
    client = get_firestore_client()
    return client.collection("users").document(uid).collection("feedback")


def save_feedback(uid: str, record: FeedbackRecord) -> FeedbackRecord:
    payload = record.model_dump(by_alias=True)
    payload["createdAt"] = datetime.now(timezone.utc)
    _collection(uid).document().set(payload)
    return record


def list_recent_feedback(uid: str, limit: int = 50) -> list[dict]:
    """Newest-first, capped at `limit` -- M7.3's adjustment rules only need
    a bounded recent window to compute a current adjustment, not a
    user's entire feedback history since account creation, so this
    deliberately doesn't grow into an unbounded read as an account ages.
    Returns raw Firestore dicts (camelCase, as stored) rather than
    re-validating into FeedbackRecord -- the adjustment rules module reads
    a few specific keys (action, intent, scoreBreakdown) and doesn't need
    the full round-trip through a Pydantic model for that.
    """
    docs = (
        _collection(uid)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]
