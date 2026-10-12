"""Fixed-window rate limits kept in Redis."""
from __future__ import annotations

import time

from core.queue import get_redis

WINDOW_SECONDS = 60


def hit(bucket: str, limit: int) -> int | None:
    """Count one request in the bucket's current minute.

    Returns None when allowed, or the seconds until the window resets.
    A limit of 0 or less disables limiting.
    """
    if limit <= 0:
        return None
    now = int(time.time())
    window = now // WINDOW_SECONDS
    key = f"codeplay:rate:{bucket}:{window}"
    pipe = get_redis().pipeline()
    pipe.incr(key)
    pipe.expire(key, WINDOW_SECONDS * 2)
    count, _ = pipe.execute()
    if count > limit:
        return WINDOW_SECONDS - now % WINDOW_SECONDS
    return None
