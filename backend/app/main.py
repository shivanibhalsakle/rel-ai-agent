from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.debug_providers import router as debug_providers_router
from app.api.health import router as health_router
from app.api.me import router as me_router
from app.api.preferences import router as preferences_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Relocation & Routine Copilot API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/v1", tags=["health"])
app.include_router(me_router, prefix="/v1", tags=["auth"])
app.include_router(preferences_router, prefix="/v1", tags=["preferences"])
app.include_router(debug_providers_router, prefix="/v1", tags=["debug"])
app.include_router(chat_router, prefix="/v1", tags=["chat"])
