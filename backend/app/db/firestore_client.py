"""
Firestore client, reusing the same Firebase Admin app initialized for auth
(app/auth/firebase.py) — one app instance, one set of credentials, whether
that's a local service account key or Cloud Run's attached identity.
"""
from functools import lru_cache

from firebase_admin import firestore

from app.auth.firebase import get_firebase_app


@lru_cache
def get_firestore_client():
    app = get_firebase_app()
    return firestore.client(app)
