from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    """Unauthenticated liveness check — used by Cloud Run and by the frontend
    to verify the deployed backend is reachable during Milestone 0."""
    return {"status": "ok"}
