"""Job queue between the API and runner workers (a Redis list of submission ids)."""
from __future__ import annotations

import uuid
from functools import lru_cache

import redis

from core.config import settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url)


def enqueue(submission_id: uuid.UUID) -> None:
    get_redis().lpush(settings.queue_name, str(submission_id))


def dequeue(timeout: int = 5) -> uuid.UUID | None:
    """Block up to timeout seconds for the next job."""
    item = get_redis().brpop([settings.queue_name], timeout=timeout)
    return uuid.UUID(item[1].decode()) if item else None


def queue_depth() -> int:
    return get_redis().llen(settings.queue_name)
