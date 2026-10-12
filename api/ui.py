"""Serves the web UI and a narrow proxy that lets it call the API without a key.

The browser never sees an API key: it calls /ui-api/..., and this proxy
forwards the request to /v1/... in-process with the UI's own key
(UI_API_KEY). Only the calls the UI needs are allowed through; creating or
editing problems still requires a real key.
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.ratelimit import hit

UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"
UUID = r"[0-9a-fA-F-]{36}"
ALLOWED = [
    ("GET", r"languages"),
    ("POST", r"runs"),
    ("GET", rf"runs/{UUID}"),
    ("GET", r"problems"),
    ("GET", rf"problems/{UUID}"),
    ("POST", r"submissions"),
    ("GET", r"submissions"),
    ("GET", rf"submissions/{UUID}"),
]


def is_allowed(method: str, path: str) -> bool:
    return any(method == m and re.fullmatch(p, path) for m, p in ALLOWED)


def mount_ui(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)

    @app.api_route("/ui-api/{path:path}", methods=["GET", "POST"], include_in_schema=False)
    async def ui_proxy(path: str, request: Request) -> Response:
        if not settings.ui_api_key:
            raise HTTPException(503, detail="the web UI is not configured (set UI_API_KEY)")
        if not is_allowed(request.method, path):
            raise HTTPException(404, detail="not available from the web UI")
        if request.method == "POST":
            # Every visitor shares the UI's key, so also limit each visitor.
            # Behind a reverse proxy, run uvicorn with --proxy-headers so this is the real IP.
            visitor = request.client.host if request.client else "unknown"
            retry_after = hit(f"ui:{visitor}", settings.ui_rate_limit_per_minute)
            if retry_after is not None:
                raise HTTPException(
                    429,
                    detail={"code": "rate_limited", "message": f"too many runs; retry in {retry_after} s"},
                    headers={"Retry-After": str(retry_after)},
                )
        async with httpx.AsyncClient(transport=transport, base_url="http://app") as client:
            upstream = await client.request(
                request.method,
                f"/v1/{path}",
                params=request.query_params,
                content=await request.body(),
                headers={
                    "Authorization": f"Bearer {settings.ui_api_key}",
                    "Content-Type": request.headers.get("content-type", "application/json"),
                },
            )
        return Response(
            upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type"),
        )

    if UI_DIST.is_dir():
        app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
