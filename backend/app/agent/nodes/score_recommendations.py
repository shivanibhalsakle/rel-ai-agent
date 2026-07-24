"""
score_recommendations node (design doc Step 4) — deterministic scoring, no
LLM involvement, per the design doc's explicit Claude-vs-deterministic
split. Wires M3's fitness_scoring/workspace_scoring straight into the
graph; the actual ranking math lives there, not here.

Known M4 simplification: travel_minutes (the per-candidate distance factor
both scoring modules support) isn't computed here — that needs a
RouteProvider call per candidate, which this milestone doesn't build
(route computation joins the agent properly in Milestone 6). Every
candidate's distance component is simply skipped for now (both scoring
modules already handle missing travel_minutes gracefully — see M3), not
silently faked with a made-up number.
"""
from app.agent.state import AgentState
from app.scoring import fitness_scoring, workspace_scoring

_SCORERS = {
    "fitness": fitness_scoring,
    "workspace": workspace_scoring,
}


def score_recommendations(state: AgentState) -> dict:
    intent = state["intent"]
    scorer = _SCORERS.get(intent)
    if scorer is None:
        # route/weather (M6) or general/unclear -- nothing to score yet.
        return {"scored_results": []}

    candidates = state.get("places_results", [])
    preferences = state["saved_preferences"]

    if intent == "workspace":
        results = scorer.score_and_rank(candidates, preferences, amenities=state.get("workspace_amenities", {}))
    else:
        results = scorer.score_and_rank(candidates, preferences)

    return {"scored_results": results}
