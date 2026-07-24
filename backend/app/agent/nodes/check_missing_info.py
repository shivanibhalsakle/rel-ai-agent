"""
check_missing_info node (design doc Step 4) — compares required fields for
the classified intent against the merged preferences and produces
missing_fields.

MVP heuristic, not the fuller judgment the design doc's own example
describes ("if the user hasn't set a budget and asks a budget-sensitive
query, agent asks... "): this is a fixed, small required-field list per
intent rather than context-dependent reasoning about which fields matter
for a specific query. Reasoned default for M4, same spirit as the M3
scoring weights doc — revisit once real conversations show what's actually
blocking good results, not before.
"""
from app.agent.state import AgentState

# Only fitness has a hard requirement today: without knowing what activity
# the user wants, a search has nothing to search for. workspace/route/
# weather all have workable defaults for everything (see fitness_scoring/
# workspace_scoring's own "skip if missing" behavior) so nothing blocks
# them yet.
_REQUIRED_FIELDS_BY_INTENT: dict[str, list[str]] = {
    "fitness": ["activities"],
    "workspace": [],
    "route": [],
    "weather": [],
    "general": [],
}


def check_missing_info(state: AgentState) -> dict:
    intent = state["intent"]

    if intent == "unclear":
        # We don't even know what the user wants yet -- "intent" itself is
        # the missing field, distinct from a known intent missing a slot.
        return {"missing_fields": ["intent"]}

    preferences = state["saved_preferences"]
    required = _REQUIRED_FIELDS_BY_INTENT.get(intent, [])

    missing = [field for field in required if not getattr(preferences, field, None)]
    return {"missing_fields": missing}
