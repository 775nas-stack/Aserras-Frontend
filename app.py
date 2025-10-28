"""FastAPI application serving the Aserras marketing site and chat UI."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return templates.TemplateResponse(
                "404.html",
                {
                    "request": request,
                    "page_title": "Not Found",
                    "settings": settings,
                    "nav_active": None,
                },
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            return templates.TemplateResponse(
                "500.html",
                {
                    "request": request,
                    "page_title": "Server error",
                    "settings": settings,
                    "nav_active": None,
                },
                status_code=exc.status_code,
            )
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return templates.TemplateResponse(
            "500.html",
            {
                "request": request,
                "page_title": "Server error",
                "settings": settings,
                "nav_active": None,
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.get("/")
    async def index(request: Request):
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "page_title": "Home",
                "settings": settings,
                "nav_active": "home",
            },
        )

    @app.get("/about")
    async def about(request: Request):
        return templates.TemplateResponse(
            "about.html",
            {
                "request": request,
                "page_title": "About",
                "settings": settings,
                "nav_active": "about",
            },
        )

    @app.get("/contact")
    async def contact(request: Request):
        return templates.TemplateResponse(
            "contact.html",
            {
                "request": request,
                "page_title": "Contact",
                "settings": settings,
                "nav_active": "contact",
            },
        )

    @app.get("/chat")
    async def chat(request: Request):
        return templates.TemplateResponse(
            "chat.html",
            {
                "request": request,
                "page_title": "Chat",
                "settings": settings,
                "nav_active": "chat",
                "user_name": "Visionary",
            },
        )

    @app.get("/pricing")
    async def pricing(request: Request):
        return templates.TemplateResponse(
            "pricing.html",
            {
                "request": request,
                "page_title": "Pricing",
                "settings": settings,
                "nav_active": "pricing",
            },
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

        return templates.TemplateResponse(
            "checkout.html",
            {
                "request": request,
                "page_title": "Checkout",
                "settings": settings,
                "nav_active": "pricing",
                "selected_plan": selected_plan,
            },
        )

    @app.get("/settings")
    async def settings_page(request: Request):
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "page_title": "Settings",
                "settings": settings,
                "nav_active": "settings",
            },
        )

    @app.get("/login")
    async def login(request: Request):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "page_title": "Login",
                "settings": settings,
                "nav_active": "login",
            },
        )

    @app.get("/signup")
    async def signup(request: Request):
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "page_title": "Sign Up",
                "settings": settings,
                "nav_active": "signup",
            },
        )

    @app.get("/forgot")
    async def forgot(request: Request):
        return templates.TemplateResponse(
            "forgot.html",
            {
                "request": request,
                "page_title": "Reset password",
                "settings": settings,
                "nav_active": "login",
            },
        )

    @app.get("/dashboard")
    async def dashboard(request: Request):
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "page_title": "Dashboard",
                "settings": settings,
                "nav_active": "dashboard",
                "user_name": "Visionary Founder",
            },
        )

    @app.get("/terms")
    async def terms(request: Request):
        return templates.TemplateResponse(
            "terms.html",
            {
                "request": request,
                "page_title": "Terms",
                "settings": settings,
                "nav_active": None,
            },
        )

    @app.get("/privacy")
    async def privacy(request: Request):
        return templates.TemplateResponse(
            "privacy.html",
            {
                "request": request,
                "page_title": "Privacy",
                "settings": settings,
                "nav_active": None,
            },
        )

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
