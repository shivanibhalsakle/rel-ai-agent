"""
POST /v1/recommendations/{recommendationId}/feedback (design doc Step 7).

recommendationId here is exactly the same value the frontend already has
as Recommendation.placeId (app/scoring/base.py's item_id() -- a real
place_id for fitness/workspace, a route candidate_id for route, a
forecast start_time for weather, see M6.4). Reusing that identifier
rather than minting a new one keeps this endpoint able to receive
feedback on ANY recommendation the chat response ever returned, without
the backend needing to have kept a durable record of "recommendations
shown in session X" to validate against -- the id in the URL and the
score_breakdown in the body are exactly what M4.10's /v1/chat response
already gave the client for that card.
"""
from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.db.repositories import feedback_repository
from app.schemas.feedback import FeedbackRecord, FeedbackRequest

router = APIRouter()


@router.post("/recommendations/{recommendation_id}/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    recommendation_id: str, body: FeedbackRequest, user: dict = Depends(get_current_user)
) -> dict:
    record = FeedbackRecord(
        related_recommendation_id=recommendation_id,
        related_session_id=body.session_id,
        intent=body.intent,
        action=body.action,
        reason=body.reason,
        score_breakdown=body.score_breakdown,
    )
    feedback_repository.save_feedback(user["uid"], record)
    return {"status": "saved"}
