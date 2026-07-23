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


@lru_cache
def get_settings() -> Settings:
    return Settings()
