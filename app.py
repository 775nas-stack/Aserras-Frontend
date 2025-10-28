"""FastAPI application serving the Aserras marketing site and chat UI."""

from __future__ import annotations

from datetime import datetime
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
        """Return a simple heartbeat for uptime checks."""

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
        return render("pricing.html", request, page_title="Pricing", nav_active="pricing")

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

    @app.post("/api/auth/login")
    async def api_login(payload: AuthRequest):
        # TODO: Connect to the live authentication service.
        return {
            "status": "pending",
            "message": "Authentication will be available shortly.",
            "redirect": "/dashboard",
        }

    @app.post("/api/auth/signup")
    async def api_signup(payload: SignupRequest):
        # TODO: Connect to the live signup flow.
        return {
            "status": "pending",
            "message": "Account creation will open soon.",
        }

    @app.post("/api/payment/create")
    async def api_payment(payload: PaymentRequest):
        if not payload.plan_id:
            raise HTTPException(status_code=400, detail="Missing plan identifier")
        # TODO: Connect to the billing orchestration service.
        return {
            "status": "pending",
            "planId": payload.plan_id,
            "message": "Billing will be available in the next release.",
        }

    @app.post("/api/chat/send")
    async def api_chat(payload: ChatRequest):
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        # TODO: Connect to the live chat service and stream responses.
        raise HTTPException(
            status_code=503,
            detail="Live chat connectivity is not active yet.",
        )

    @app.get("/api/user/history")
    async def api_history():
        # TODO: Pull conversation history from the account service.
        return {"status": "pending", "messages": []}

    @app.post("/api/contact/send")
    async def api_contact(payload: ContactRequest):
        # TODO: Route contact messages to the concierge desk.
        return {
            "status": "pending",
            "message": "Messages will be routed to the concierge team soon.",
        }

    return app


app = create_app(get_settings())
