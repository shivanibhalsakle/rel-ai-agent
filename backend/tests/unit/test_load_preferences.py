from app.agent.nodes.load_preferences import load_preferences
from app.agent.state import new_agent_state
from app.schemas.preferences import BudgetBand, UserPreferences


def _no_stored_preferences(_uid: str) -> None:
    return None


def _stored(preferences: UserPreferences):
    def _fn(_uid: str) -> UserPreferences:
        return preferences

    return _fn


def test_no_stored_preferences_defaults_before_merging():
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"activities": ["yoga"]}

    update = load_preferences(state, get_preferences_fn=_no_stored_preferences)

    merged = update["saved_preferences"]
    assert merged.activities == ["yoga"]
    assert merged.min_rating == 0  # UserPreferences default, untouched


def test_no_extracted_preferences_returns_stored_unchanged():
    stored = UserPreferences(activities=["gym"], min_rating=4.0)
    state = new_agent_state(user_id="u1", session_id="s1")

    update = load_preferences(state, get_preferences_fn=_stored(stored))

    assert update["saved_preferences"] == stored


def test_direct_fields_are_overridden_by_extraction():
    stored = UserPreferences(max_travel_minutes=30, travel_mode="drive", min_rating=3.0)
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"max_travel_minutes": 15, "travel_mode": "walk", "min_rating": 4.5}

    update = load_preferences(state, get_preferences_fn=_stored(stored))

    merged = update["saved_preferences"]
    assert merged.max_travel_minutes == 15
    assert merged.travel_mode == "walk"
    assert merged.min_rating == 4.5


def test_budget_max_usd_builds_budget_band_preserving_currency_and_period():
    stored = UserPreferences(budget_band=BudgetBand(min=10, max=50, currency="USD", period="class"))
    state = new_agent_state(user_id="u1", session_id="s1")
    state["extracted_preferences"] = {"budget_max_usd": 80.0}

    update = load_preferences(state, get_preferences_fn=_stored(stored))

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

    update = load_preferences(state, get_preferences_fn=_stored(stored))

    needs = update["saved_preferences"].workspace_needs
    assert needs.wifi is True
    assert needs.outlets is True  # untouched
    assert needs.food is True  # untouched
