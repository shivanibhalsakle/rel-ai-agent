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

As of M7.4, saving feedback also recomputes and persists the user's
inferred preference adjustment (app.scoring.preference_adjustment) in the
same request -- the write is small (a bounded, capped-limit read plus one
document write) and doing it inline means the very next /v1/chat call
already reflects today's feedback, rather than needing a separate
background job or cron this MVP has no infrastructure for yet.
"""
from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_current_user
from app.db.repositories import feedback_repository, preference_repository
from app.schemas.feedback import FeedbackRecord, FeedbackRequest
from app.scoring.preference_adjustment import compute_adjustment

router = APIRouter()


@router.post("/recommendations/{recommendation_id}/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    recommendation_id: str, body: FeedbackRequest, user: dict = Depends(get_current_user)
) -> dict:
    uid = user["uid"]
    record = FeedbackRecord(
        related_recommendation_id=recommendation_id,
        related_session_id=body.session_id,
        intent=body.intent,
        action=body.action,
        reason=body.reason,
        score_breakdown=body.score_breakdown,
    )
    feedback_repository.save_feedback(uid, record)

    recent = feedback_repository.list_recent_feedback(uid)
    adjustment = compute_adjustment(recent)
    preference_repository.save_inferred_adjustment(uid, adjustment)

    return {"status": "saved"}
