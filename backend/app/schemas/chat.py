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
    place_id: str
    name: str
    score: float
    score_breakdown: dict[str, float]
    explanation: str | None = None
    # Added for M5.5 (map display) -- every scored PlaceCandidate already
    # carries these (M2.3), _build_response just wasn't copying them
    # through until the frontend actually needed to plot a marker.
    lat: float
    lng: float


class ChatResponse(CamelModel):
    session_id: str
    status: Literal["completed", "awaiting_input", "awaiting_approval"]
    intent: str | None = None
    question: str | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    # Set for the "general" reply, not-yet-supported, and budget-exceeded
    # cases -- an overall message rather than per-item recommendations.
    message: str | None = None
