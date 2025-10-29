"""History views and API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.dependencies.auth import get_brain_client, get_session_token, require_user
from app.services.brain_api import BrainAPIClient, BrainAPIError, BrainAPIUnavailable

router = APIRouter(tags=["history"])


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    user: dict[str, Any] = Depends(require_user),
    client: BrainAPIClient = Depends(get_brain_client),
    token: str | None = Depends(get_session_token),
) -> HTMLResponse:
    history: list[dict[str, Any]] = []
    warning: str | None = None
    if token:
        try:
            history = await client.get_history(token)
        except BrainAPIUnavailable:
            warning = "Aserras Brain is unavailable. Showing cached data only."
        except BrainAPIError as exc:
            warning = str(exc)
    return request.app.state.templates.TemplateResponse(
        request,
        "workspaces/history.html",
        {
            "request": request,
            "page_title": "History",
            "nav": "history",
            "user": user,
            "history": history,
            "warning": warning,
        },
    )


@router.get("/api/history")
async def history_api(
    request: Request,
    client: BrainAPIClient = Depends(get_brain_client),
    token: str | None = Depends(get_session_token),
) -> JSONResponse:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    try:
        history = await client.get_history(token)
    except BrainAPIUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Aserras Brain is unavailable")
    except BrainAPIError as exc:
        raise HTTPException(status_code=exc.status_code or status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return JSONResponse({"items": history})
