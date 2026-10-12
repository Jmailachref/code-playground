from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

bearer = HTTPBearer(auto_error=False)


def client_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    """The calling project's id, from its API key."""
    if credentials is None or credentials.credentials not in settings.api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or missing API key")
    return settings.api_keys[credentials.credentials]
