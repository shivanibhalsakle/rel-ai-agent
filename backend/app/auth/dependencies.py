"""
FastAPI dependency that verifies the Firebase ID token on the Authorization
header and returns the decoded claims. Add `user: dict = Depends(get_current_user)`
to any route that should require authentication.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from app.auth.firebase import get_firebase_app

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    try:
        get_firebase_app()  # ensures the SDK is initialized before verifying
        decoded_token = firebase_auth.verify_id_token(credentials.credentials)
    except Exception as exc:
        # Covers both "token is invalid/expired" (firebase_admin's own error types) and
        # "Firebase isn't configured in this environment" (e.g. CI, or a machine with no
        # service account) — both are correctly a 401 from the caller's point of view, not
        # a 500. Keeps `/v1/me` testable without real Firebase credentials present.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        ) from exc

    return decoded_token
