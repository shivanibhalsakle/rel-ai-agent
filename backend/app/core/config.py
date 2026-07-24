"""
Central app configuration. Reads from environment variables so the same code
runs locally (.env), in CI, and on Cloud Run (env vars injected from Secret
Manager) without changes.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"  # local | staging | production
    cors_allow_origins: str = "http://localhost:3000"

    firebase_project_id: str | None = None
    # Path to the Firebase service account JSON, for local dev only. On Cloud Run this stays
    # unset — the deployed service uses its attached service account identity instead (no key
    # file needed there).
    google_application_credentials: str | None = None

    # Populated in later milestones — left optional so M0 runs with none of them set.
    anthropic_api_key: str | None = None
    google_maps_api_key: str | None = None

    # Milestone 8 — Google Calendar OAuth (phase 2, opt-in per user). Separate
    # client id/secret from google_maps_api_key on purpose: this is a distinct
    # OAuth 2.0 client (Web application type) with its own consent screen and
    # scopes, not an API key. Never sent to the frontend -- the redirect URI
    # points back at this backend, which exchanges the auth code server-side
    # and stores only the resulting refresh/access tokens (see
    # db/repositories/calendar_repository.py, M8.3).
    google_calendar_client_id: str | None = None
    google_calendar_client_secret: str | None = None
    # Must exactly match an "Authorized redirect URI" registered on the OAuth
    # client in Cloud Console -- Google rejects the exchange otherwise.
    google_calendar_redirect_uri: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
