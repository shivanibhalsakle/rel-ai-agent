import pytest
from fastapi import HTTPException

from app.core.rate_limit import _MAX_REQUESTS, _request_log, rate_limit


def test_allows_requests_under_the_limit():
    _request_log.clear()
    user = {"uid": "test-user-1"}
    for _ in range(_MAX_REQUESTS):
        assert rate_limit(user) == user  # should not raise


def test_blocks_requests_over_the_limit():
    _request_log.clear()
    user = {"uid": "test-user-2"}
    for _ in range(_MAX_REQUESTS):
        rate_limit(user)

    with pytest.raises(HTTPException) as exc_info:
        rate_limit(user)
    assert exc_info.value.status_code == 429


def test_limit_is_per_user_not_global():
    _request_log.clear()
    user_a = {"uid": "test-user-a"}
    user_b = {"uid": "test-user-b"}
    for _ in range(_MAX_REQUESTS):
        rate_limit(user_a)

    # user_a is now at the limit, but user_b should be unaffected
    assert rate_limit(user_b) == user_b
