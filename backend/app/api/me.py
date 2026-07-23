from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user

router = APIRouter()


@router.get("/me")
def read_current_user(user: dict = Depends(get_current_user)) -> dict:
    """Protected route — proves the frontend's Firebase ID token reaches the
    backend and verifies successfully. Real profile data comes in Milestone 1."""
    return {"uid": user["uid"], "email": user.get("email")}
