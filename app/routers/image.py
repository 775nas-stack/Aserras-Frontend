"""Image generation workspace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.dependencies.auth import get_brain_client, get_session_token, require_user
from app.services.brain_api import BrainAPIClient, BrainAPIError, BrainAPIUnavailable

router = APIRouter(tags=["image"])


class ImagePayload(BaseModel):
    prompt: str = Field(..., max_length=1000)
    size: str | None = Field(default="1024x1024", max_length=20)


@router.get("/image", response_class=HTMLResponse)
async def image_page(
    request: Request,
    user: dict[str, Any] = Depends(require_user),
) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "workspaces/image.html",
        {
            "request": request,
            "page_title": "Image Studio",
            "nav": "image",
            "user": user,
        },
    )


@router.post("/api/image")
async def image_api(
    payload: ImagePayload,
    request: Request,
    client: BrainAPIClient = Depends(get_brain_client),
    token: str | None = Depends(get_session_token),
) -> JSONResponse:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt cannot be empty")

    try:
        result = await client.image_generation(prompt=prompt, token=token, size=payload.size)
    except BrainAPIUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Aserras Brain is unavailable")
    except BrainAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=str(exc))

    return JSONResponse(result)
