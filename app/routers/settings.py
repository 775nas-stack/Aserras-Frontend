"""User settings pages and APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.dependencies.auth import get_brain_client, get_session_token, require_user
from app.services.brain_api import BrainAPIClient, BrainAPIError, BrainAPIUnavailable

router = APIRouter(tags=["settings"])


class ProfileUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    language: str | None = Field(default=None, max_length=10)
    model: str | None = Field(default=None, max_length=200)


class ThemePayload(BaseModel):
    theme: str = Field(..., pattern=r"^(light|dark)$")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: dict[str, Any] = Depends(require_user),
    client: BrainAPIClient = Depends(get_brain_client),
    token: str | None = Depends(get_session_token),
) -> HTMLResponse:
    models: list[dict[str, Any]] = []
    warning: str | None = None
    if token:
        try:
            models = await client.list_models(token)
        except BrainAPIUnavailable:
            warning = "Aserras Brain is unavailable. Model options may be limited."
        except BrainAPIError as exc:
            warning = str(exc)
    return request.app.state.templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "request": request,
            "page_title": "Settings",
            "nav": "settings",
            "user": user,
            "models": models,
            "warning": warning,
        },
    )


@router.post("/api/settings/profile")
async def update_profile(
    payload: ProfileUpdate,
    client: BrainAPIClient = Depends(get_brain_client),
    token: str | None = Depends(get_session_token),
) -> JSONResponse:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    try:
        result = await client.update_profile(
            token,
            {
                "name": payload.name,
                "language": payload.language,
                "default_model": payload.model,
            },
        )
    except BrainAPIUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Aserras Brain is unavailable")
    except BrainAPIError as exc:
        raise HTTPException(status_code=exc.status_code or status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return JSONResponse(result)


@router.post("/api/settings/theme")
async def update_theme(
    payload: ThemePayload,
    request: Request,
) -> JSONResponse:
    theme = payload.theme
    response = JSONResponse({"status": "ok", "theme": theme})
    response.set_cookie(
        "aserras_theme",
        theme,
        httponly=False,
        secure=request.app.state.settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24 * 365,
        path="/",
    )
    return response
