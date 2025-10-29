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
    payload = {
        "request": request,
        "settings": request.app.state.settings,
        "nav_active": None,
    }
    if context:
        payload.update(context)
    if "nav" in payload and payload.get("nav_active") is None:
        payload["nav_active"] = payload["nav"]
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


async def _process_login(
    request: Request, *, email: str, password: str
) -> tuple[str | None, str | None]:
    client: BrainAPIClient = request.app.state.brain_client
    email = email.strip().lower()
    password = password.strip()

    if not email or not password:
        return None, "Email and password are required."

    try:
        result = await client.login(email=email, password=password)
    except BrainAPIUnavailable:
        return None, "Aserras Brain is temporarily offline. Please try again soon."
    except BrainAPIError as exc:
        return None, exc.args[0]

    token = result.get("access_token") or result.get("token")
    if not token:
        return None, "Login succeeded but no token was returned."
    return token, None


async def _process_signup(
    request: Request, *, name: str, email: str, password: str
) -> tuple[str | None, str | None]:
    client: BrainAPIClient = request.app.state.brain_client
    name = name.strip()
    email = email.strip().lower()
    password = password.strip()

    if not name or not email or not password:
        return None, "All fields are required."

    try:
        result = await client.register(name=name, email=email, password=password)
    except BrainAPIUnavailable:
        return None, "Aserras Brain is temporarily offline. Please try again soon."
    except BrainAPIError as exc:
        return None, exc.args[0]

    token = result.get("access_token") or result.get("token")
    return token, None


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "login.html", {"page_title": "Sign in", "nav": "login"})


async def _extract_form(request: Request) -> dict[str, str]:
    body = await request.body()
    form = parse_qs(body.decode("utf-8"))
    return {key: values[-1] for key, values in form.items()}


@router.post("/login")
async def login_submit(request: Request) -> HTMLResponse:
    form = await _extract_form(request)
    email = form.get("email", "")
    password = form.get("password", "")

    token, error = await _process_login(request, email=email, password=password)
    if error:
        return render(
            request,
            "login.html",
            {
                "page_title": "Sign in",
                "nav": "login",
                "error": error,
                "email": email.strip().lower(),
            },
        )

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(**_session_cookie_params(request), value=token)
    return response


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request) -> HTMLResponse:
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "signup.html", {"page_title": "Create account", "nav": "signup"})


@router.get("/forgot", response_class=HTMLResponse)
async def forgot_page(request: Request) -> HTMLResponse:
    return render(
        request,
        "forgot.html",
        {"page_title": "Reset password", "nav": "login"},
    )


@router.post("/signup")
async def signup_submit(request: Request) -> HTMLResponse:
    form = await _extract_form(request)
    name = form.get("name", "")
    email = form.get("email", "")
    password = form.get("password", "")

    token, error = await _process_signup(request, name=name, email=email, password=password)
    if error:
        return render(
            request,
            "signup.html",
            {
                "page_title": "Create account",
                "nav": "signup",
                "error": error,
                "name": name.strip(),
                "email": email.strip().lower(),
            },
        )

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    if token:
        response.set_cookie(**_session_cookie_params(request), value=token)
    return response


@router.post("/api/auth/login")
async def login_api(request: Request) -> JSONResponse:
    data = await request.json()
    email = data.get("email", "") if isinstance(data, dict) else ""
    password = data.get("password", "") if isinstance(data, dict) else ""

    token, error = await _process_login(request, email=email, password=password)
    if error:
        return JSONResponse(
            {"status": "error", "detail": error}, status_code=status.HTTP_400_BAD_REQUEST
        )

    response = JSONResponse({"status": "ok", "redirect": "/dashboard"})
    response.set_cookie(**_session_cookie_params(request), value=token)
    return response


@router.post("/api/auth/signup")
async def signup_api(request: Request) -> JSONResponse:
    data = await request.json()
    name = data.get("name", "") if isinstance(data, dict) else ""
    email = data.get("email", "") if isinstance(data, dict) else ""
    password = data.get("password", "") if isinstance(data, dict) else ""

    token, error = await _process_signup(request, name=name, email=email, password=password)
    if error:
        return JSONResponse(
            {"status": "error", "detail": error}, status_code=status.HTTP_400_BAD_REQUEST
        )

    response = JSONResponse({"status": "ok", "redirect": "/dashboard"})
    if token:
        response.set_cookie(**_session_cookie_params(request), value=token)
    return response


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    response = JSONResponse({"status": "ok"})
    params = _session_cookie_params(request)
    response.delete_cookie(params["key"], path="/")
    return response
