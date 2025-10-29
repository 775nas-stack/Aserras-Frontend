"""Automation and code generation workspace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.dependencies.auth import get_brain_client, get_session_token, require_user
from app.services.brain_api import BrainAPIClient, BrainAPIError, BrainAPIUnavailable

router = APIRouter(tags=["code"])


class CodePayload(BaseModel):
    instructions: str = Field(..., max_length=4000)
    language: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)


@router.get("/code", response_class=HTMLResponse)
async def code_page(
    request: Request,
    user: dict[str, Any] = Depends(require_user),
) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "workspaces/code.html",
        {
            "request": request,
            "page_title": "Automation Studio",
            "nav": "code",
            "user": user,
        },
    )


@router.post("/api/code")
async def code_api(
    payload: CodePayload,
    request: Request,
    client: BrainAPIClient = Depends(get_brain_client),
    token: str | None = Depends(get_session_token),
) -> JSONResponse:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    instructions = payload.instructions.strip()
    if not instructions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Instructions cannot be empty")

    try:
        result = await client.code_generation(
            instructions=instructions,
            token=token,
            language=payload.language,
            model=payload.model,
        )
    except BrainAPIUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Aserras Brain is unavailable")
    except BrainAPIError as exc:
        raise HTTPException(status_code=exc.status_code or 400, detail=str(exc))

    return JSONResponse(result)
