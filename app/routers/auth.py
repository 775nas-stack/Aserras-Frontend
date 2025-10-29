"""Authentication routes for login, registration, and logout."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.services.brain_api import BrainAPIClient, BrainAPIError, BrainAPIUnavailable

router = APIRouter(prefix="", tags=["auth"])


def render(request: Request, template_name: str, context: dict[str, Any] | None = None) -> HTMLResponse:
    templates = request.app.state.templates
    payload = {"request": request, "settings": request.app.state.settings}
    if context:
        payload.update(context)
    payload.setdefault("user", getattr(request.state, "user", None))
    return templates.TemplateResponse(request, template_name, payload)


def _session_cookie_params(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "key": settings.SESSION_COOKIE_NAME,
        "httponly": True,
        "secure": settings.SESSION_COOKIE_SECURE,
        "samesite": "lax",
        "max_age": settings.SESSION_COOKIE_MAX_AGE,
        "path": "/",
    }


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "auth/login.html", {"page_title": "Sign in", "nav": "login"})


async def _extract_form(request: Request) -> dict[str, str]:
    body = await request.body()
    form = parse_qs(body.decode("utf-8"))
    return {key: values[-1] for key, values in form.items()}


@router.post("/login")
async def login_submit(request: Request) -> HTMLResponse:
    client: BrainAPIClient = request.app.state.brain_client
    form = await _extract_form(request)
    email = form.get("email", "").strip().lower()
    password = form.get("password", "").strip()

    if not email or not password:
        return render(
            request,
            "auth/login.html",
            {
                "page_title": "Sign in",
                "nav": "login",
                "error": "Email and password are required.",
                "email": email,
            },
        )

    try:
        result = await client.login(email=email, password=password)
    except BrainAPIUnavailable:
        return render(
            request,
            "auth/login.html",
            {
                "page_title": "Sign in",
                "nav": "login",
                "error": "Aserras Brain is temporarily offline. Please try again soon.",
                "email": email,
            },
        )
    except BrainAPIError as exc:
        return render(
            request,
            "auth/login.html",
            {
                "page_title": "Sign in",
                "nav": "login",
                "error": exc.args[0],
                "email": email,
            },
        )

    token = result.get("access_token") or result.get("token")
    if not token:
        return render(
            request,
            "auth/login.html",
            {
                "page_title": "Sign in",
                "nav": "login",
                "error": "Login succeeded but no token was returned.",
                "email": email,
            },
        )

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(**_session_cookie_params(request), value=token)
    return response


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request) -> HTMLResponse:
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "auth/signup.html", {"page_title": "Create account", "nav": "signup"})


@router.post("/signup")
async def signup_submit(request: Request) -> HTMLResponse:
    client: BrainAPIClient = request.app.state.brain_client
    form = await _extract_form(request)
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()
    password = form.get("password", "").strip()

    if not name or not email or not password:
        return render(
            request,
            "auth/signup.html",
            {
                "page_title": "Create account",
                "nav": "signup",
                "error": "All fields are required.",
                "name": name,
                "email": email,
            },
        )

    try:
        result = await client.register(name=name, email=email, password=password)
    except BrainAPIUnavailable:
        return render(
            request,
            "auth/signup.html",
            {
                "page_title": "Create account",
                "nav": "signup",
                "error": "Aserras Brain is temporarily offline. Please try again soon.",
                "name": name,
                "email": email,
            },
        )
    except BrainAPIError as exc:
        return render(
            request,
            "auth/signup.html",
            {
                "page_title": "Create account",
                "nav": "signup",
                "error": exc.args[0],
                "name": name,
                "email": email,
            },
        )

    token = result.get("access_token") or result.get("token")
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    if token:
        response.set_cookie(**_session_cookie_params(request), value=token)
    return response


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    response = JSONResponse({"status": "ok"})
    params = _session_cookie_params(request)
    response.delete_cookie(params["key"], path="/")
    return response
