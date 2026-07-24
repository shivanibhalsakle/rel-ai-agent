"""
score_recommendations node (design doc Step 4) — deterministic scoring, no
LLM involvement, per the design doc's explicit Claude-vs-deterministic
split. Wires M3's scoring modules straight into the graph; the actual
ranking math lives there, not here.

Branches per intent explicitly rather than a uniform dispatch dict (M4's
original shape, when fitness/workspace really did share one call
signature) -- route needs its distance/duration targets and reads from
route_candidates, weather has no candidates list the same way and reads
from weather_data, so the four scorers never actually had one shared
call shape once route/weather existed to check that against (M6). This
mirrors every other place in this codebase that gave up a premature
uniform abstraction once real data proved it didn't fit
(understand_request's field-naming split, route_scoring's optional
road-exposure component, etc.).

Known M4 simplification, still true for fitness/workspace: travel_minutes
(the per-candidate distance factor both scoring modules support) isn't
computed here — that needs a RouteProvider call per candidate, which
isn't wired up for the fitness/workspace search flow. Both scoring
modules already handle missing travel_minutes gracefully (see M3), not
silently faked with a made-up number.

route_candidates' weather_comfort input is deliberately left unset here
-- combining a route's candidates with a weather forecast for the same
window is a real enhancement (M3.4's own docstring anticipates it) but
adds coupling between two domains that don't need to ship together for
either one to work; see generate_route_candidates.py / M6.3's own note
on the same decision.
"""
from app.agent.state import AgentState
from app.scoring import fitness_scoring, route_scoring, weather_scoring, workspace_scoring


def score_recommendations(state: AgentState) -> dict:
    intent = state["intent"]
    preferences = state["saved_preferences"]

    if intent == "fitness":
        results = fitness_scoring.score_and_rank(state.get("places_results", []), preferences)
    elif intent == "workspace":
        results = workspace_scoring.score_and_rank(
            state.get("places_results", []), preferences, amenities=state.get("workspace_amenities", {})
        )
    elif intent == "route":
        extracted = state.get("extracted_preferences", {})
        results = route_scoring.score_and_rank(
            state.get("route_candidates", []),
            preferences,
            target_distance_meters=extracted.get("target_distance_meters"),
            target_duration_seconds=extracted.get("target_duration_seconds"),
        )
    elif intent == "weather":
        results = weather_scoring.score_and_rank(state.get("weather_data", []), preferences)
    else:
        # general/unclear -- nothing to score.
        results = []

    return {"scored_results": results}
