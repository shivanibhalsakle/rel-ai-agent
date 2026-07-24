"""
Chat request/response schemas (design doc Step 7 — POST /v1/chat and
POST /v1/chat/{sessionId}/resume).

`awaiting_approval` status exists in the design doc's contract but isn't
reachable yet — calendar approval is Milestone 8. `Recommendation.score_breakdown`
is shaped like the contract's intent (per-factor sub-scores) but not
byte-identical to its illustrative example, which was sketched before M3's
real ScoreComponent shape existed. `dataConfidence` from the contract's
example is intentionally omitted for now rather than filled with
placeholder values — a real per-field confidence map needs its own design
pass, not a guess.
"""
from typing import Literal

from pydantic import Field

from app.schemas.preferences import CamelModel


class ChatRequest(CamelModel):
    session_id: str | None = None
    message: str


class ResumeRequest(CamelModel):
    answer: str | None = None
    approved: bool | None = None  # reserved for Milestone 8 (calendar approval)


class Recommendation(CamelModel):
    rank: int
    # place_id is a slight misnomer for route/weather results (M6) --
    # kept as-is rather than renamed, to not break the frontend's already-
    # shipped wire contract (M5). Populated via app.scoring.base.item_id(),
    # which is a real place_id for fitness/workspace, a route candidate_id
    # for route, and a forecast start_time for weather -- always a stable
    # identifier, not always literally a Google Place ID.
    place_id: str
    name: str
    score: float
    score_breakdown: dict[str, float]
    explanation: str | None = None
    # Added for M5.5 (map display) -- every scored PlaceCandidate already
    # carries these (M2.3). Optional as of M6: RouteCandidate has no
    # single point (it's a path -- see M6.7 for the real polyline-based
    # map treatment) and HourlyForecast has no location of its own at all,
    # so both are None rather than a fabricated 0.0. The frontend's map
    # already filters out non-finite coordinates (M5.5's RecommendationMap
    # defensive fix), so this degrades to "no pin for this one" instead of
    # a bad marker.
    lat: float | None = None
    lng: float | None = None
    # Added for M6.7 (route map overlay + weather timeline). Both None for
    # fitness/workspace results -- neither concept applies to a PlaceCandidate.
    # polyline: RouteCandidate's encoded path (via app.scoring.base.item_polyline()),
    # None for everything else. The frontend draws this as a
    # google.maps.Polyline instead of a pin, since a route has no single
    # point to put a marker on.
    polyline: str | None = None
    # start_time: HourlyForecast's raw ISO 8601 UTC start_time, None for
    # everything else. `name` is already the human-formatted version of
    # this (e.g. "02:00 PM UTC", via item_display_name()) for display in
    # a card; this raw value is what the frontend's weather timeline needs
    # to sort/plot chronologically, which a formatted string can't do
    # reliably.
    start_time: str | None = None


class ChatResponse(CamelModel):
    session_id: str
    status: Literal["completed", "awaiting_input", "awaiting_approval"]
    intent: str | None = None
    question: str | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    # Set for the "general" reply, not-yet-supported, and budget-exceeded
    # cases -- an overall message rather than per-item recommendations.
    message: str | None = None
