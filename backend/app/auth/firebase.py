"""
Initializes the Firebase Admin SDK exactly once per process. Used to verify
ID tokens the frontend sends on every authenticated request (see
app/auth/dependencies.py).
"""
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials

from app.core.config import get_settings


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    if firebase_admin._apps:  # already initialized (e.g. hot reload)
        return firebase_admin.get_app()

    settings = get_settings()

    if settings.google_application_credentials:
        # Local dev: explicit service account key file.
        cred = credentials.Certificate(settings.google_application_credentials)
        return firebase_admin.initialize_app(cred)

    # Cloud Run: no key file — use the service's attached identity.
    return firebase_admin.initialize_app()
