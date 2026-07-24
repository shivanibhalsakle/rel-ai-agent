"""
fetch_place_details node (design doc Step 4) — selective, budget-conscious
Details+reviews fetch. This is the live wiring for the feature M3
deliberately left unimplemented: review_signals.py (M3.3b) was built to
scan review text for wifi/outlets/quiet mentions, but fetching that text
costs real money (Google's priciest Places SKU, Enterprise + Atmosphere,
~$0.04/call per the rates checked during Milestone 3's research), so it was
held back until an agent existed to gate how often it fires. This node is
that gate.

Deliberately tighter than the design doc's own illustrative number (Step
3.2 says "e.g. top 15 candidates") — 15 calls on this SKU would be $0.60
for a single search, which doesn't hold up against this project's stated
cost discipline (PlacesProvider's own M2 docstring: "a handful of places a
user actually looks at," not every result). SHORTLIST_SIZE is a deliberate
tightening now that real per-call pricing is known, not an oversight.

Only runs for workspace intent: amenity signals are a workspace_scoring
input; fitness_scoring has no use for them, so there's no reason to spend
on data that won't affect the outcome.
"""
from app.agent.state import AgentState
from app.providers.places_provider import PlacesProvider
from app.scoring.review_signals import extract_amenity_signals, to_amenities_bool

SHORTLIST_SIZE = 5


async def fetch_place_details(state: AgentState, provider: PlacesProvider | None = None) -> dict:
    if state["intent"] != "workspace":
        return {}

    candidates = state.get("places_results", [])
    shortlist = sorted(candidates, key=lambda c: c.rating or 0, reverse=True)[:SHORTLIST_SIZE]
    if not shortlist:
        return {}

    provider = provider or PlacesProvider()
    amenities: dict[str, dict[str, bool]] = {}
    for candidate in shortlist:
        reviews = await provider.get_reviews(candidate.place_id)
        if not reviews:
            continue
        signals = extract_amenity_signals(reviews)
        if signals:
            amenities[candidate.place_id] = to_amenities_bool(signals)

    return {"workspace_amenities": amenities}
