"""
Reads and writes users/{userId}/preferences/profile (the user's EXPLICIT
preferences -- onboarding/settings, never touched by feedback-driven
adjustment) and, as of M7, users/{userId}/preferences/inferred (the
feedback-derived Importance adjustment computed by
app.scoring.preference_adjustment). Nothing outside this file should know
Firestore is the storage backend — that's the point of a repository layer
(see design doc: "Design the data-access layer so Firestore can later be
supplemented or replaced").

profile and inferred are deliberately two separate documents, not one
merged preferences doc with adjusted values baked in. Keeping them apart
is what makes an honest "why we think this" settings panel (M7.6)
possible -- it can display "what you set" against "what we've inferred
and why" as two real, independently-readable things, instead of trying to
reverse-engineer a diff out of an already-merged value. It's also what
lets M7.4's load_preferences apply the adjustment on top of whatever the
explicit profile currently is, rather than the adjustment silently
overwriting the user's own stated preference.
"""
from datetime import datetime, timezone

from app.db.firestore_client import get_firestore_client
from app.scoring.preference_adjustment import InferredAdjustment
from app.schemas.preferences import UserPreferences


def _doc_ref(uid: str):
    client = get_firestore_client()
    return client.collection("users").document(uid).collection("preferences").document("profile")


def _inferred_doc_ref(uid: str):
    client = get_firestore_client()
    return client.collection("users").document(uid).collection("preferences").document("inferred")


def get_preferences(uid: str) -> UserPreferences | None:
    snapshot = _doc_ref(uid).get()
    if not snapshot.exists:
        return None
    data = snapshot.to_dict()
    data.pop("updatedAt", None)
    data.pop("updatedBy", None)
    return UserPreferences.model_validate(data)


def save_preferences(
    uid: str, preferences: UserPreferences, updated_by: str = "explicit"
) -> UserPreferences:
    payload = preferences.model_dump(by_alias=True)
    payload["updatedAt"] = datetime.now(timezone.utc)
    payload["updatedBy"] = updated_by
    _doc_ref(uid).set(payload)
    return preferences


def get_inferred_adjustment(uid: str) -> InferredAdjustment:
    """Always returns a real InferredAdjustment, never None -- a user with
    no feedback yet (or none that crossed ADJUSTMENT_THRESHOLD) has an
    empty adjustment (InferredAdjustment().is_empty is True), which is a
    normal, expected state, not a missing-document error the way absent
    onboarding preferences (get_preferences returning None) is."""
    snapshot = _inferred_doc_ref(uid).get()
    if not snapshot.exists:
        return InferredAdjustment()
    data = snapshot.to_dict()
    data.pop("updatedAt", None)
    return InferredAdjustment.model_validate(data)


def save_inferred_adjustment(uid: str, adjustment: InferredAdjustment) -> InferredAdjustment:
    """Overwrites the prior inferred doc rather than merging into it --
    app.scoring.preference_adjustment.compute_adjustment already
    recomputes a full, fresh adjustment from the current feedback window
    on every call (see that module's docstring on why it's not
    accumulated), so this write is meant to replace, not layer on top of,
    whatever was stored before."""
    payload = adjustment.model_dump(by_alias=True)
    payload["updatedAt"] = datetime.now(timezone.utc)
    _inferred_doc_ref(uid).set(payload)
    return adjustment
