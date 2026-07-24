"""
search_places node (design doc Step 4) — calls PlacesProvider.search_text
with a query built from the resolved location plus the user's activities
(fitness) or a generic workspace query (workspace).

Uses search_text rather than search_nearby + a hand-maintained "activity
string -> Places type enum" mapping table: text search tolerates the wide
variety of ways people phrase "yoga studio" / "24 hour gym" / "quiet cafe"
far better than forcing an exact enum match would, and this app doesn't yet
have a reason to need search_nearby's tighter radius control.
"""
from app.agent.state import AgentState
from app.providers.places_provider import PlacesProvider

MAX_RESULTS = 15
_DEFAULT_WORKSPACE_QUERY = "coworking space or cafe with wifi"


def _build_query(state: AgentState) -> str | None:
    location = state.get("resolved_location")
    if not location:
        return None
    address = location.get("formatted_address", "")

    intent = state["intent"]
    if intent == "fitness":
        preferences = state["saved_preferences"]
        activity = preferences.activities[0] if preferences and preferences.activities else "gym"
        return f"{activity} near {address}"
    if intent == "workspace":
        return f"{_DEFAULT_WORKSPACE_QUERY} near {address}"
    return None


async def search_places(state: AgentState, provider: PlacesProvider | None = None) -> dict:
    query = _build_query(state)
    if not query:
        return {
            "errors": state.get("errors", [])
            + [{"node": "search_places", "message": "No resolved location to search near.", "retryable": False}]
        }

    provider = provider or PlacesProvider()
    results = await provider.search_text(query, max_results=MAX_RESULTS)
    return {"places_results": results}
