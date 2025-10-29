"""Routes for marketing and dashboard pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.dependencies.auth import get_optional_user
from app.services.brain_api import BrainAPIError, BrainAPIUnavailable

router = APIRouter()

STATIC_DIR = Path("static")


def render(request: Request, template_name: str, context: dict[str, Any] | None = None) -> HTMLResponse:
    templates = request.app.state.templates
    settings = request.app.state.settings
    payload: dict[str, Any] = {
        "request": request,
        "settings": settings,
        "nav_active": None,
    }
    if context:
        payload.update(context)
    if "nav" in payload and payload.get("nav_active") is None:
        payload["nav_active"] = payload["nav"]
    payload.setdefault("user", getattr(request.state, "user", None))
    return templates.TemplateResponse(request, template_name, payload)


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request) -> HTMLResponse:
    return render(
        request,
        "index.html",
        {"page_title": "Home", "nav": "home"},
    )


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request) -> HTMLResponse:
    return render(request, "about.html", {"page_title": "About", "nav": "about"})


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request) -> HTMLResponse:
    return render(request, "contact.html", {"page_title": "Contact", "nav": "contact"})


@router.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request) -> HTMLResponse:
    return render(request, "pricing.html", {"page_title": "Pricing", "nav": "pricing"})


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request, plan: str = "pro") -> HTMLResponse:
    plans = {
        "free": {
            "id": "free",
            "name": "Free",
            "price": "$0",
            "description": "Preview chat workflows and secure account basics.",
            "features": [
                "Single creator seat",
                "Chat workspace preview",
                "Community help center",
            ],
        },
        "basic": {
            "id": "basic",
            "name": "Basic",
            "price": "$12",
            "description": "Start collaborating with guided onboarding.",
            "features": [
                "Up to 3 teammates",
                "Project space templates",
                "Email support",
            ],
        },
        "pro": {
            "id": "pro",
            "name": "Pro",
            "price": "$29",
            "description": "Scale private workflows with premium support.",
            "features": [
                "Unlimited projects",
                "Priority workspace routing",
                "Dedicated success partner",
            ],
        },
        "elite": {
            "id": "elite",
            "name": "Elite",
            "price": "$99",
            "description": "Tailored concierge intelligence for executive teams.",
            "features": [
                "Custom governance",
                "Compliance-ready exports",
                "Strategic concierge access",
            ],
        },
    }
    selected_plan = plans.get(plan.lower(), plans["pro"])
    return render(
        request,
        "checkout.html",
        {
            "page_title": "Checkout",
            "nav": "pricing",
            "selected_plan": selected_plan,
        },
    )


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request) -> HTMLResponse:
    return render(request, "terms.html", {"page_title": "Terms"})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request) -> HTMLResponse:
    return render(request, "privacy.html", {"page_title": "Privacy"})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: dict[str, Any] | None = Depends(get_optional_user),
) -> HTMLResponse:
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

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

    user_name = user.get("name") or user.get("email") or "Creator"

    return render(
        request,
        "dashboard.html",
        {
            "page_title": "Dashboard",
            "nav": "dashboard",
            "user": user,
            "user_name": user_name,
            "history": history[:12],
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
