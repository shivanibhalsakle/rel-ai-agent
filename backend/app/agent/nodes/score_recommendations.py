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
from datetime import datetime, timedelta, timezone

from app.agent.state import AgentState
from app.scoring import fitness_scoring, route_scoring, weather_scoring, workspace_scoring


def _weather_calendar_snapshot(forecast, location: dict | None) -> dict:
    """Builds the minimal snapshot M8.5's last_weather_recommendation
    holds -- title/start/end/location, exactly what a calendar event
    needs and nothing else. Each HourlyForecast entry represents a
    one-hour window (see weather_provider.py), so end = start + 1h."""
    start = datetime.fromisoformat(forecast.start_time.replace("Z", "+00:00"))
    end = start + timedelta(hours=1)
    return {
        "title": "Time outside",
        "start": start.astimezone(timezone.utc).isoformat(),
        "end": end.astimezone(timezone.utc).isoformat(),
        "location": (location or {}).get("formatted_address"),
    }


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
        update: dict = {"scored_results": results}
        if results:
            # M8.5: snapshot the top pick into the durable (not per-turn-
            # reset) last_weather_recommendation field, so a later "add
            # that to my calendar" turn can still find it once
            # scored_results itself has been wiped for the new turn.
            update["last_weather_recommendation"] = _weather_calendar_snapshot(
                results[0].item, state.get("resolved_location")
            )
        return update
    else:
        # general/unclear/add_to_calendar -- nothing to score. (add_to_calendar
        # never reaches this node at all -- see agent/graph.py's routing --
        # this branch is just the safe default for anything unmatched.)
        results = []

    return {"scored_results": results}
