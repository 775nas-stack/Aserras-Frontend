"""FastAPI application serving the Aserras marketing site and chat UI."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from secrets import token_hex
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from fastapi.responses import FileResponse

from config import Settings, get_settings

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class AuthRequest(BaseModel):
    """Expected payload for authentication requests."""

    email: str
    password: str


class SignupRequest(AuthRequest):
    """Signup payload adds a full name field."""

    full_name: str = Field(..., alias="fullName")


class PaymentRequest(BaseModel):
    """Minimal payment request details."""

    plan_id: str = Field(..., alias="planId")
    token: str | None = None


class ChatRequest(BaseModel):
    """Payload for sending a chat message."""

    message: str
    token: str | None = None


class ContactRequest(BaseModel):
    """Payload for contact form submissions."""

    name: str
    email: str
    message: str


DEFAULT_CHAT_HISTORY: tuple[dict[str, str], ...] = (
    {
        "id": "welcome-ai",
        "role": "ai",
        "text": "Welcome back to your private workspace. Ask anything to continue our flow.",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    },
)


def _friendly_name(email: str, *, fallback: str | None = None) -> str:
    """Return a readable display name for the provided email address."""

    if fallback:
        return fallback

    local_part = email.split("@", 1)[0]
    if not local_part:
        return "Creator"
    return " ".join(part.capitalize() for part in local_part.replace("_", " ").split("."))


def _new_token(prefix: str = "session") -> str:
    """Generate a predictable-length placeholder token."""

    return f"{prefix}_{token_hex(16)}"


def _timestamp(hours: int = 0) -> str:
    """Return an ISO 8601 timestamp with optional hour offset."""

    return (datetime.utcnow() + timedelta(hours=hours)).isoformat(timespec="seconds") + "Z"


def create_app(settings: Settings) -> FastAPI:
    """Application factory to build the FastAPI instance."""

    app = FastAPI(title="Aserras Web")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = BASE_DIR / "static"
    templates_dir = BASE_DIR / "templates"

    static_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=str(templates_dir))
    templates.env.globals["now"] = datetime.utcnow

    def render(
        template_name: str,
        request: Request,
        *,
        status_code: int | None = None,
        **context: Any,
    ):
        base_context: dict[str, Any] = {"settings": settings, **context}
        base_context.setdefault("nav_active", None)

        if status_code is None:
            return templates.TemplateResponse(request, template_name, base_context)
        return templates.TemplateResponse(
            request,
            template_name,
            base_context,
            status_code=status_code,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return render(
                "404.html",
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                page_title="Not Found",
            )
        if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            return render(
                "500.html",
                request,
                status_code=exc.status_code,
                page_title="Server error",
            )
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return render(
            "500.html",
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            page_title="Server error",
        )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        """Simple readiness probe for load balancers and uptime checks."""

        return {"status": "ok"}

    @app.get("/")
    async def index(request: Request):
        return render("index.html", request, page_title="Home", nav_active="home")

    @app.get("/about")
    async def about(request: Request):
        return render("about.html", request, page_title="About", nav_active="about")

    @app.get("/contact")
    async def contact(request: Request):
        return render("contact.html", request, page_title="Contact", nav_active="contact")

    @app.get("/chat")
    async def chat(request: Request):
        return render(
            "chat.html",
            request,
            page_title="Chat",
            nav_active="chat",
            user_name="Visionary",
        )

    @app.get("/pricing")
    async def pricing(request: Request):
        return render(
            "pricing.html",
            request,
            page_title="Pricing",
            nav_active="pricing",
            is_upgrade=False,
        )

    @app.get("/upgrade")
    async def upgrade(request: Request):
        return render(
            "pricing.html",
            request,
            page_title="Upgrade",
            nav_active="pricing",
            is_upgrade=True,
        )

    @app.get("/robots.txt", include_in_schema=False)
    async def robots():
        return FileResponse(static_dir / "robots.txt", media_type="text/plain")

    @app.get("/sitemap.xml", include_in_schema=False)
    async def sitemap():
        return FileResponse(static_dir / "sitemap.xml", media_type="application/xml")

    @app.get("/checkout")
    async def checkout(request: Request, plan: str = "pro"):
        # TODO: Replace static plan data with live pricing from the control service.
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
            "checkout.html",
            request,
            page_title="Checkout",
            nav_active="pricing",
            selected_plan=selected_plan,
        )

    @app.get("/settings")
    async def settings_page(request: Request):
        return render(
            "settings.html", request, page_title="Settings", nav_active="settings"
        )

    @app.get("/login")
    async def login(request: Request):
        return render("login.html", request, page_title="Login", nav_active="login")

    @app.get("/signup")
    async def signup(request: Request):
        return render("signup.html", request, page_title="Sign Up", nav_active="signup")

    @app.get("/forgot")
    async def forgot(request: Request):
        return render(
            "forgot.html", request, page_title="Reset password", nav_active="login"
        )

    @app.get("/dashboard")
    async def dashboard(request: Request):
        return render(
            "dashboard.html",
            request,
            page_title="Dashboard",
            nav_active="dashboard",
            user_name="Visionary Founder",
        )

    @app.get("/terms")
    async def terms(request: Request):
        return render("terms.html", request, page_title="Terms")

    @app.get("/privacy")
    async def privacy(request: Request):
        return render("privacy.html", request, page_title="Privacy")

    app.state.chat_history = deque(DEFAULT_CHAT_HISTORY, maxlen=200)

    @app.post("/api/auth/login")
    async def api_login(payload: AuthRequest):
        if len(payload.password.strip()) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

        user = {
            "email": payload.email,
            "name": _friendly_name(payload.email),
        }

        return {
            "status": "ok",
            "message": f"Welcome back, {user['name']}.",
            "redirect": "/dashboard",
            "token": _new_token("session"),
            "tokenType": "bearer",
            "sessionExpires": _timestamp(hours=8),
            "user": user,
        }

    @app.post("/api/auth/signup")
    async def api_signup(payload: SignupRequest):
        if len(payload.password.strip()) < 8:
            raise HTTPException(status_code=400, detail="Choose a password that is at least 8 characters long")

        user = {
            "email": payload.email,
            "name": _friendly_name(payload.email, fallback=payload.full_name.strip()),
        }

        return {
            "status": "ok",
            "message": f"Your workspace is ready, {user['name']}.",
            "redirect": "/dashboard",
            "token": _new_token("session"),
            "tokenType": "bearer",
            "sessionExpires": _timestamp(hours=12),
            "user": user,
        }

    @app.post("/api/payment/create")
    async def api_payment(payload: PaymentRequest):
        if not payload.plan_id:
            raise HTTPException(status_code=400, detail="Missing plan identifier")

        return {
            "status": "ok",
            "planId": payload.plan_id,
            "message": "Your upgrade request has been scheduled. We'll email confirmation shortly.",
            "reference": _new_token("payment"),
        }

    @app.post("/api/chat/send")
    async def api_chat(payload: ChatRequest, request: Request):
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        history: deque[dict[str, str]] = request.app.state.chat_history

        user_entry = {
            "id": _new_token("user"),
            "role": "user",
            "text": message,
            "timestamp": _timestamp(),
        }

        reply_text = (
            "I'm capturing that now. Here's a quick insight: "
            f"{message[:180]}"
            if len(message) <= 180
            else f"I'm capturing that now. Here's a quick insight: {message[:177]}..."
        )

        ai_entry = {
            "id": _new_token("ai"),
            "role": "ai",
            "text": reply_text,
            "timestamp": _timestamp(),
        }

        history.append(user_entry)
        history.append(ai_entry)

        return {
            "status": "ok",
            "reply": ai_entry["text"],
            "messages": list(history),
        }

    @app.get("/api/user/history")
    async def api_history(request: Request):
        history: deque[dict[str, str]] = request.app.state.chat_history
        return {
            "status": "ok",
            "messages": list(history),
        }

    @app.post("/api/contact/send")
    async def api_contact(payload: ContactRequest):
        return {
            "status": "ok",
            "message": "Thank you for contacting us. Our concierge team will follow up soon.",
            "reference": _new_token("contact"),
        }

    return app


app = create_app(get_settings())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8001)
