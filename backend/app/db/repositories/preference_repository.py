"""
Reads and writes users/{userId}/preferences/profile. Nothing outside this
file should know Firestore is the storage backend — that's the point of a
repository layer (see design doc: "Design the data-access layer so Firestore
can later be supplemented or replaced").
"""
from datetime import datetime, timezone

from app.db.firestore_client import get_firestore_client
from app.schemas.preferences import UserPreferences


def _doc_ref(uid: str):
    client = get_firestore_client()
    return client.collection("users").document(uid).collection("preferences").document("profile")


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
