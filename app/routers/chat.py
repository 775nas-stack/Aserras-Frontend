"""Chat interface routes and API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.dependencies.auth import get_brain_client, get_session_token, require_user
from app.services.brain_api import BrainAPIClient, BrainAPIError, BrainAPIUnavailable

router = APIRouter(tags=["chat"])


class ChatPayload(BaseModel):
    prompt: str = Field(..., max_length=2000)
    model: str | None = Field(default=None, max_length=200)


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(
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
            warning = "Aserras Brain is offline. Generation is temporarily disabled."
        except BrainAPIError:
            warning = "Could not load model catalogue."
    return request.app.state.templates.TemplateResponse(
        request,
        "workspaces/chat.html",
        {
            "request": request,
            "page_title": "Chat",
            "nav": "chat",
            "user": user,
            "models": models,
            "warning": warning,
        },
    )


@router.post("/api/chat")
async def chat_api(
    payload: ChatPayload,
    request: Request,
    client: BrainAPIClient = Depends(get_brain_client),
    token: str | None = Depends(get_session_token),
) -> JSONResponse:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    message = payload.prompt.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty")

    try:
        result = await client.text_completion(prompt=message, token=token, model=payload.model)
    except BrainAPIUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Aserras Brain is unavailable")
    except BrainAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=str(exc))

    return JSONResponse(result)
