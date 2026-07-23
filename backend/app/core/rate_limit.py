"""
Simple in-memory, per-user rate limiter for routes that spend real money per
call (provider searches). Deliberately not Redis — per design doc, don't add
Redis until a demonstrated need; in-memory is fine at MVP scale on a single
Cloud Run instance.

Known limitation: if Cloud Run scales to multiple instances, each instance
tracks its own counts independently, so the effective limit becomes (this
limit x instance count) rather than one hard global cap. Acceptable for now;
revisit with a shared store (Redis, or a Firestore counter) if usage ever
gets high enough for that gap to matter.
"""
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user

_MAX_REQUESTS = 30
_WINDOW_SECONDS = 60

_request_log: dict[str, deque] = defaultdict(deque)


def rate_limit(user: dict = Depends(get_current_user)) -> dict:
    """Drop-in replacement for `Depends(get_current_user)` — does the same
    auth check, plus a sliding-window cap of _MAX_REQUESTS per user per
    _WINDOW_SECONDS. Use on any route that triggers a billed external API
    call; leave plain get_current_user on routes that only touch Firestore
    (those don't need this — cost isn't the concern there)."""
    uid = user["uid"]
    now = time.monotonic()
    log = _request_log[uid]

    while log and now - log[0] > _WINDOW_SECONDS:
        log.popleft()

    if len(log) >= _MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {_MAX_REQUESTS} requests per {_WINDOW_SECONDS}s. Try again shortly.",
        )

    log.append(now)
    return user
