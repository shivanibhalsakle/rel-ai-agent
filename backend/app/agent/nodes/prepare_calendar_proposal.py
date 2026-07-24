"""
prepare_calendar_proposal node (M8.5) -- the deterministic step between
understand_request classifying "add_to_calendar" intent and
request_user_approval pausing the graph. Builds the ApprovalRequest
payload from last_weather_recommendation (score_recommendations' durable
snapshot of the most recently shown weather pick -- see that module's
docstring for why it survives the per-turn state reset that scored_results
itself doesn't).

Two ways this degrades to an honest message instead of ever reaching the
approval interrupt, neither of which is a system error:
  - no recent weather recommendation this session to attach to ("add to
    calendar" said before ever asking about weather this session, or in a
    session where the checkpointer's memory doesn't go back that far)
  - calendar isn't connected (never went through OAuth connect, or
    disconnected since)
Both set `explanation` directly; _route_after_calendar_proposal
(agent/graph.py) sends either case straight to generate_explanation
(which safely no-ops without touching `explanation` when there's nothing
to score -- see that node) rather than to request_user_approval. There is
nothing to interrupt/resume for a proposal that was never valid to begin
with.
"""
from app.agent.state import AgentState
from app.db.repositories import calendar_repository


def prepare_calendar_proposal(state: AgentState, repo=calendar_repository) -> dict:
    recommendation = state.get("last_weather_recommendation")
    if not recommendation:
        return {
            "explanation": (
                "I don't have a recent weather recommendation to add to your calendar -- "
                "ask me for the best time to be outside today first, then I can offer to "
                "add it for you."
            )
        }

    if not repo.is_connected(state["user_id"]):
        return {
            "explanation": (
                "Your Google Calendar isn't connected yet -- connect it from Settings, "
                "then ask me to add a time to your calendar."
            )
        }

    return {
        "pending_approval": {
            "kind": "calendar_event",
            "payload": {
                "title": recommendation["title"],
                "start": recommendation["start"],
                "end": recommendation["end"],
                "location": recommendation.get("location"),
            },
        }
    }
