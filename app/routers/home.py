"""Routes for marketing and dashboard pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse

from app.dependencies.auth import get_optional_user
from app.services.brain_api import BrainAPIError, BrainAPIUnavailable

router = APIRouter()

STATIC_DIR = Path("app/static")


def render(request: Request, template_name: str, context: dict[str, Any] | None = None) -> HTMLResponse:
    templates = request.app.state.templates
    settings = request.app.state.settings
    payload = {"request": request, "settings": settings}
    if context:
        payload.update(context)
    payload.setdefault("user", getattr(request.state, "user", None))
    return templates.TemplateResponse(request, template_name, payload)


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    return render(
        request,
        "home/index.html",
        {"page_title": "Aserras AI", "nav": "home"},
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> HTMLResponse:
    if not user:
        return render(
            request,
            "home/index.html",
            {
                "page_title": "Aserras AI",
                "nav": "home",
                "flash": {
                    "type": "warning",
                    "message": "Please sign in to access your dashboard.",
                },
            },
        )

    brain_client = request.app.state.brain_client
    history: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    server_warning: str | None = None
    token = request.cookies.get(request.app.state.settings.SESSION_COOKIE_NAME)
    if token:
        try:
            history = await brain_client.get_history(token)
            models = await brain_client.list_models(token)
        except BrainAPIUnavailable:
            server_warning = "Aserras Brain is temporarily offline. Recent data may be stale."
        except BrainAPIError as exc:
            server_warning = str(exc)

    return render(
        request,
        "home/dashboard.html",
        {
            "page_title": "Dashboard",
            "nav": "dashboard",
            "user": user,
            "history": history[:6],
            "models": models,
            "server_warning": server_warning,
        },
    )


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> FileResponse:
    return FileResponse(STATIC_DIR / "robots.txt", media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> FileResponse:
    return FileResponse(STATIC_DIR / "sitemap.xml", media_type="application/xml")
