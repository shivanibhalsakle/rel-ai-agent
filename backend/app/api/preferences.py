from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.db.repositories import preference_repository
from app.schemas.preferences import OnboardingRequest, UserPreferences
from app.scoring.preference_adjustment import InferredAdjustment

router = APIRouter()


@router.post("/onboarding", status_code=status.HTTP_200_OK)
def complete_onboarding(
    body: OnboardingRequest, user: dict = Depends(get_current_user)
) -> dict:
    preferences = UserPreferences.model_validate(body.model_dump(by_alias=True))
    preference_repository.save_preferences(user["uid"], preferences, updated_by="explicit")
    return {"status": "saved"}


@router.get("/preferences", response_model=UserPreferences)
def read_preferences(user: dict = Depends(get_current_user)) -> UserPreferences:
    preferences = preference_repository.get_preferences(user["uid"])
    if preferences is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preferences saved yet — complete onboarding first.",
        )
    return preferences


@router.put("/preferences", response_model=UserPreferences)
def update_preferences(
    body: UserPreferences, user: dict = Depends(get_current_user)
) -> UserPreferences:
    return preference_repository.save_preferences(user["uid"], body, updated_by="explicit")


@router.get("/preferences/inferred", response_model=InferredAdjustment)
def read_inferred_adjustment(user: dict = Depends(get_current_user)) -> InferredAdjustment:
    """The "why we think this" panel's data source (M7.6) -- what feedback
    has nudged, and why, kept separate from the explicit GET /preferences
    response on purpose (see preference_repository.py's module docstring).
    Unlike GET /preferences, there's no 404 case here: a user with no
    feedback yet, or none that crossed the adjustment threshold, has a
    real, valid, empty InferredAdjustment -- not a missing resource."""
    return preference_repository.get_inferred_adjustment(user["uid"])
