"""
Feedback request/record schemas (design doc Step 6's
users/{userId}/feedback/{feedbackId} collection, Step 7's
POST /v1/recommendations/{recommendationId}/feedback contract).

score_breakdown is deliberately part of the request, not re-derived
server-side: it's the exact same factor->score map the client already
rendered on the card the user just accepted/rejected (M5.2's
scoreBreakdown). Echoing it back is honest (it's what the user actually
saw when they acted) and cheap (no re-fetch of the original recommendation,
which the backend doesn't keep around after a turn ends anyway -- the
LangGraph checkpointer's state is turn-scoped, not a permanent record of
every recommendation ever shown). M7.3's adjustment rules read this map to
figure out which factors were unfavorable on rejected items, which
favorable on accepted ones -- no fabricated signal, just what was already
computed and shown.
"""
from typing import Literal

from pydantic import Field

from app.schemas.preferences import CamelModel

FeedbackAction = Literal["accepted", "rejected"]


class FeedbackRequest(CamelModel):
    session_id: str
    # Which domain this recommendation came from -- fitness/workspace/route/
    # weather. The adjustment rules (M7.3) only make sense per-domain (e.g.
    # "affordability" isn't a factor route/weather results have at all), so
    # this is required, not inferred later from score_breakdown's keys.
    intent: str
    action: FeedbackAction
    reason: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class FeedbackRecord(CamelModel):
    """What actually gets stored, one layer past the request: adds the
    recommendation/session identifiers the URL path and auth already give
    us, so a stored record is self-contained (readable later without
    needing to know which request produced it)."""

    related_recommendation_id: str
    related_session_id: str
    intent: str
    action: FeedbackAction
    reason: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)
