"""Settings read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _api_keys(raw: str) -> dict[str, str]:
    """Parse "client-a:key1,client-b:key2" into {key: client_id}."""
    keys = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        client_id, _, key = pair.partition(":")
        if not key:
            raise ValueError(f"API_KEYS entry must be client:key, got {pair!r}")
        keys[key] = client_id
    return keys


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL", "postgresql+psycopg://codeplay:codeplay@localhost:5432/codeplay"
        )
    )
    redis_url: str = field(default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    api_keys: dict[str, str] = field(default_factory=lambda: _api_keys(os.environ.get("API_KEYS", "dev:dev-key")))
    queue_name: str = field(default_factory=lambda: os.environ.get("QUEUE_NAME", "codeplay:jobs"))
    # Key the web UI uses through its proxy; must be one of API_KEYS. Empty disables the UI.
    ui_api_key: str = field(default_factory=lambda: os.environ.get("UI_API_KEY", ""))
    # Runs plus submissions allowed per minute, per API key and (for the web UI) per visitor IP.
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60")))
    ui_rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.environ.get("UI_RATE_LIMIT_PER_MINUTE", "20"))
    )


settings = Settings()
