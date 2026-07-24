"""
not_yet_supported node — route and weather intents are recognized by
understand_request (M4.3), but their search/score pipelines don't exist
yet (route joins the agent in Milestone 6, same for weather-aware
scheduling). Without this node, those intents would fall through to
score_recommendations (which already returns an empty list for them, per
M4.6) and produce a silent, empty response. A fixed capability statement
doesn't need a Claude call.
"""
from app.agent.state import AgentState

_MESSAGES = {
    "route": "Running and walking route planning isn't available yet — it's coming in a later update.",
    "weather": "Weather-based scheduling isn't available yet — it's coming in a later update.",
}


def not_yet_supported(state: AgentState) -> dict:
    message = _MESSAGES.get(state["intent"], "That's not something I can help with yet.")
    return {"explanation": message}
