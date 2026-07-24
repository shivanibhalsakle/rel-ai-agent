from app.agent.nodes.load_preferences import load_preferences
from app.agent.state import new_agent_state
from app.schemas.preferences import BudgetBand, Importance, UserPreferences
from app.scoring.preference_adjustment import InferredAdjustment


def _no_stored_preferences(_uid: str) -> None:
    return None


def _stored(preferences: UserPreferences):
    def _fn(_uid: str) -> UserPreferences:
        return preferences

    return _fn


# M7.4 added a second Firestore read to load_preferences (the inferred
# adjustment) -- every pre-existing call below now also injects this fake
# so tests that predate M7 keep exercising only the merge logic they were
# written for, not a real Firestore connection for the new read.
def _no_adjustment(_uid: str) -> InferredAdjustment:
    return InferredAdjustment()


def _adjustment(delta: dict[str, int]):
    def _fn(_uid: str) -> InferredAdjustment:
        return InferredAdjustment(importance_delta=delta, reasons=["test reason"])

    return _fn


def test_no_stored_preferences_defaults_before_merging():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"activities": ["yoga"]}

    update = load_preferences(
        state, get_preferences_fn=_no_stored_preferences, get_inferred_adjustment_fn=_no_adjustment
    )

    merged = update["saved_preferences"]
    assert merged.activities == ["yoga"]
    assert merged.min_rating == 0  # UserPreferences default, untouched


def test_no_extracted_preferences_returns_stored_unchanged():
    stored = UserPreferences(activities=["gym"], min_rating=4.0)
    state = new_agent_state(user_id="u1", session_id="s1")

    update = load_preferences(state, get_preferences_fn=_stored(stored), get_inferred_adjustment_fn=_no_adjustment)

    assert update["saved_preferences"] == stored


def test_direct_fields_are_overridden_by_extraction():
    stored = UserPreferences(max_travel_minutes=30, travel_mode="drive", min_rating=3.0)
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"max_travel_minutes": 15, "travel_mode": "walk", "min_rating": 4.5}

    update = load_preferences(state, get_preferences_fn=_stored(stored), get_inferred_adjustment_fn=_no_adjustment)

    merged = update["saved_preferences"]
    assert merged.max_travel_minutes == 15
    assert merged.travel_mode == "walk"
    assert merged.min_rating == 4.5


def test_budget_max_usd_builds_budget_band_preserving_currency_and_period():
    stored = UserPreferences(budget_band=BudgetBand(min=10, max=50, currency="USD", period="class"))
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"budget_max_usd": 80.0}

    update = load_preferences(state, get_preferences_fn=_stored(stored), get_inferred_adjustment_fn=_no_adjustment)

    band = update["saved_preferences"].budget_band
    assert band.max == 80.0
    assert band.min == 10  # preserved from stored, extraction only ever supplies a ceiling
    assert band.currency == "USD"
    assert band.period == "class"


def test_workspace_needs_only_updates_the_mentioned_fields():
    from app.schemas.preferences import WorkspaceNeeds

    stored = UserPreferences(workspace_needs=WorkspaceNeeds(wifi=False, outlets=True, quiet=False, food=True))
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"wants_wifi": True}

    update = load_preferences(state, get_preferences_fn=_stored(stored), get_inferred_adjustment_fn=_no_adjustment)

    needs = update["saved_preferences"].workspace_needs
    assert needs.wifi is True
    assert needs.outlets is True  # untouched
    assert needs.food is True  # untouched


# ---- M7.4: inferred adjustment applied on top of stored, before this-turn extraction ----


def test_empty_adjustment_leaves_importance_unchanged():
    stored = UserPreferences(importance=Importance(affordability=3, review_count=3, distance=3))
    state = new_agent_state(user_id="u1", session_id="s1")

    update = load_preferences(state, get_preferences_fn=_stored(stored), get_inferred_adjustment_fn=_no_adjustment)

    assert update["saved_preferences"].importance == Importance(affordability=3, review_count=3, distance=3)


def test_nonempty_adjustment_bumps_the_named_importance_factor():
    stored = UserPreferences(importance=Importance(affordability=3, review_count=3, distance=3))
    state = new_agent_state(user_id="u1", session_id="s1")

    update = load_preferences(
        state,
        get_preferences_fn=_stored(stored),
        get_inferred_adjustment_fn=_adjustment({"affordability": 1}),
    )

    importance = update["saved_preferences"].importance
    assert importance.affordability == 4
    assert importance.review_count == 3  # untouched
    assert importance.distance == 3  # untouched


def test_this_turns_explicit_extraction_still_overrides_the_inferred_adjustment():
    # A standing implicit nudge from past feedback must never outrank
    # something the user is explicitly saying in THIS message -- extraction
    # is merged in after the adjustment is applied, so this ordering is
    # what load_preferences' own docstring promises.
    stored = UserPreferences(min_rating=3.0, importance=Importance(affordability=3, review_count=3, distance=3))
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"min_rating": 4.5}

    update = load_preferences(
        state,
        get_preferences_fn=_stored(stored),
        get_inferred_adjustment_fn=_adjustment({"affordability": 1}),
    )

    merged = update["saved_preferences"]
    assert merged.min_rating == 4.5  # this turn's explicit value wins
    assert merged.importance.affordability == 4  # the inferred adjustment still applied underneath
