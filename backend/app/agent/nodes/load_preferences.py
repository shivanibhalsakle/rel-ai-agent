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

As of M7.4, the feedback-derived inferred adjustment (users/{userId}/
preferences/inferred, app.scoring.preference_adjustment) is applied on top
of the stored EXPLICIT preferences, before this-turn extraction is merged
in. Order matters: applying the inferred nudge first, then letting this
turn's own extracted values override it, means anything the user is
saying RIGHT NOW always wins over a standing implicit adjustment from past
behavior -- an explicit "actually, price doesn't matter this time" in the
current message isn't fighting an invisible thumb on the scale.
"""
from app.db.repositories.preference_repository import get_inferred_adjustment, get_preferences
from app.schemas.preferences import BudgetBand, UserPreferences
from app.scoring.preference_adjustment import apply_adjustment
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


def load_preferences(
    state: AgentState,
    get_preferences_fn=get_preferences,
    get_inferred_adjustment_fn=get_inferred_adjustment,
) -> dict:
    """`get_preferences_fn`/`get_inferred_adjustment_fn` are injectable
    (default to the real Firestore reads) so this node's merge logic can
    be unit-tested without a Firestore connection."""
    stored = get_preferences_fn(state["user_id"]) or UserPreferences()
    adjustment = get_inferred_adjustment_fn(state["user_id"])
    if not adjustment.is_empty:
        stored = stored.model_copy(update={"importance": apply_adjustment(stored.importance, adjustment.importance_delta)})
    merged = _merge_extracted(stored, state.get("extracted_preferences", {}))
    return {"saved_preferences": merged}
