"""
load_preferences node (design doc Step 4) — fetches the user's saved
UserPreferences from Firestore and merges this turn's extracted_preferences
on top ("this-turn overrides saved, but doesn't persist until confirmed" —
the merged result lives only in state["saved_preferences"] for this session;
persisting it back to Firestore is save_preference's job, a later node).

Field-naming translation lives here on purpose: understand_request's
extraction schema is flat and LLM-friendly (budget_max_usd, wants_wifi, ...)
while UserPreferences is nested (budgetBand, workspaceNeeds, ...) — this is
the one place that gap gets bridged, so no other node needs to know both
shapes.
"""
from app.db.repositories.preference_repository import get_preferences
from app.schemas.preferences import BudgetBand, UserPreferences
from app.agent.state import AgentState

_DIRECT_FIELDS = ("max_travel_minutes", "travel_mode", "min_rating", "indoor_outdoor_preference", "activities")
_WORKSPACE_NEED_FIELDS = {"wants_wifi": "wifi", "wants_outlets": "outlets", "wants_quiet": "quiet"}


def _merge_extracted(preferences: UserPreferences, extracted: dict) -> UserPreferences:
    updates: dict = {}

    for field in _DIRECT_FIELDS:
        if field in extracted:
            updates[field] = extracted[field]

    if "budget_max_usd" in extracted:
        existing = preferences.budget_band
        updates["budget_band"] = BudgetBand(
            min=existing.min if existing else 0.0,
            max=extracted["budget_max_usd"],
            currency=existing.currency if existing else "USD",
            period=existing.period if existing else "month",
        )

    needs_updates = {field: extracted[key] for key, field in _WORKSPACE_NEED_FIELDS.items() if key in extracted}
    if needs_updates:
        updates["workspace_needs"] = preferences.workspace_needs.model_copy(update=needs_updates)

    if not updates:
        return preferences
    return preferences.model_copy(update=updates)


def load_preferences(state: AgentState, get_preferences_fn=get_preferences) -> dict:
    """`get_preferences_fn` is injectable (defaults to the real Firestore
    read) so this node's merge logic can be unit-tested without a Firestore
    connection."""
    stored = get_preferences_fn(state["user_id"]) or UserPreferences()
    merged = _merge_extracted(stored, state.get("extracted_preferences", {}))
    return {"saved_preferences": merged}
