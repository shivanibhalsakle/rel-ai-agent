"""
Shared response cache for all external provider calls (Places, Weather,
Routes, Geocoding), backed by Firestore's apiCache collection (see design
doc Step 6). Deliberately provider-agnostic about what's inside the cached
payload — each provider decides its own cache key inputs and TTL; this
module just does the get-or-fetch-and-store mechanics once, instead of every
provider reimplementing it. Shared across users (not scoped to a uid), since
place/weather/route data isn't user-specific.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, TypeVar

from pydantic import BaseModel

from app.db.firestore_client import get_firestore_client

T = TypeVar("T", bound=BaseModel)


def _cache_key(provider: str, params: dict) -> str:
    normalized = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"{provider}_{digest}"


def _doc_ref(cache_key: str):
    client = get_firestore_client()
    return client.collection("apiCache").document(cache_key)


async def get_or_fetch(
    provider: str,
    params: dict,
    ttl_seconds: int,
    fetch_fn: Callable[[], Awaitable[T | list[T] | None]],
    model_type: type[T],
    is_list: bool = False,
) -> T | list[T] | None:
    """Returns cached data if a non-expired entry exists; otherwise calls
    fetch_fn() (the real, billed API call), caches the result, and returns
    it. fetch_fn only ever runs on a cache miss."""
    cache_key = _cache_key(provider, params)
    doc = _doc_ref(cache_key).get()

    if doc.exists:
        data = doc.to_dict()
        expires_at = data.get("expiresAt")
        if expires_at and expires_at > datetime.now(timezone.utc):
            payload = data.get("responsePayload")
            if is_list:
                return [model_type.model_validate(item) for item in (payload or [])]
            return model_type.model_validate(payload) if payload is not None else None

    result = await fetch_fn()

    payload = (
        [item.model_dump(mode="json") for item in result]
        if is_list
        else (result.model_dump(mode="json") if result is not None else None)
    )
    _doc_ref(cache_key).set(
        {
            "provider": provider,
            "requestParams": params,
            "responsePayload": payload,
            "createdAt": datetime.now(timezone.utc),
            "expiresAt": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        }
    )
    return result
