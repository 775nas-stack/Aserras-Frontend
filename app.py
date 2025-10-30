"""FastAPI application serving the Aserras marketing site and chat UI."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from importlib import util as importlib_util
from pathlib import Path
from secrets import token_hex
import sys
from typing import Any

from anyio import to_thread
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import AliasChoices, BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from fastapi.responses import FileResponse

try:  # pragma: no cover - exercised indirectly via tests
    import stripe
except ModuleNotFoundError:  # pragma: no cover - fallback for local tests without dependency
    class _StripeError(Exception):
        """Base stub for Stripe errors."""

    class _StripeAuthError(_StripeError):
        """Stub authentication error."""

    class _StripeAPIConnectionError(_StripeError):
        """Stub connection error."""

    class _StripeSignatureError(_StripeError):
        """Stub signature verification error."""

    class _StripePaymentIntent:
        @staticmethod
        def create(*_: Any, **__: Any) -> Any:
            raise RuntimeError("stripe package is required for payment processing")

    class _StripeBalance:
        @staticmethod
        def retrieve(*_: Any, **__: Any) -> Any:
            raise RuntimeError("stripe package is required for payment processing")

    class _StripeWebhook:
        @staticmethod
        def construct_event(*_: Any, **__: Any) -> Any:
            raise RuntimeError("stripe package is required for payment processing")

    class _StripeCheckoutSession:
        @staticmethod
        def create(*_: Any, **__: Any) -> Any:
            raise RuntimeError("stripe package is required for payment processing")

    class _StripeCheckout:
        Session = _StripeCheckoutSession

    class _StripeStub:
        def __init__(self) -> None:
            self.api_key: str | None = None
            self.error = type(
                "error",
                (),
                {
                    "StripeError": _StripeError,
                    "AuthenticationError": _StripeAuthError,
                    "APIConnectionError": _StripeAPIConnectionError,
                    "SignatureVerificationError": _StripeSignatureError,
                },
            )
            self.PaymentIntent = _StripePaymentIntent
            self.Balance = _StripeBalance
            self.Webhook = _StripeWebhook
            self.checkout = _StripeCheckout

    stripe = _StripeStub()

from config import Settings, get_settings

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _load_payments_router():
    """Dynamically import the payments router if it exists."""

    router_path = BASE_DIR / "app" / "routers" / "payments.py"
    if not router_path.exists():
        return None

    module_name = "app.routers.payments"
    if "app.routers" not in sys.modules:
        package = importlib_util.module_from_spec(
            importlib_util.spec_from_loader("app.routers", loader=None)
        )
        package.__path__ = []  # type: ignore[attr-defined]
        sys.modules["app.routers"] = package
    spec = importlib_util.spec_from_file_location(module_name, router_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib_util.module_from_spec(spec)
    module.__package__ = "app.routers"
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return getattr(module, "router", None)


class AuthRequest(BaseModel):
    """Expected payload for authentication requests."""

    email: str
    password: str


class SignupRequest(AuthRequest):
    """Signup payload adds a full name field."""

    full_name: str = Field(..., alias="fullName")


class PaymentIntentRequest(BaseModel):
    """Payload for creating a Stripe payment intent."""

    plan_id: str = Field(..., validation_alias=AliasChoices("plan_id", "planId"))


class LegacyPaymentRequest(BaseModel):
    """Legacy payment request schema used by the marketing site."""

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

PLAN_PRICING: dict[str, dict[str, Any]] = {
    "basic": {"amount": 1200, "currency": "usd", "name": "Basic"},
    "pro": {"amount": 2900, "currency": "usd", "name": "Pro"},
    "elite": {"amount": 9900, "currency": "usd", "name": "Elite"},
}


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

    stripe.api_key = settings.stripe_secret_key.get_secret_value()

    print("Stripe keys loaded:", bool(settings.stripe_secret_key))

    allowed_origins = settings.allowed_origins
    allow_credentials = True
    if not allowed_origins:
        allowed_origins = ["*"]
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
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

    router = _load_payments_router()
    if router is not None:
        app.include_router(router)

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
    async def health() -> dict[str, bool]:
        """Simple readiness probe for load balancers and uptime checks."""

        return {"ok": True}

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
    app.state.payment_records: dict[str, dict[str, Any]] = {}
    app.state.paypal_orders: dict[str, dict[str, Any]] = {}
    app.state.user_subscriptions: dict[str, str] = {}

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

    def _get_plan_details(plan_id: str) -> dict[str, Any] | None:
        plan = PLAN_PRICING.get(plan_id.lower())
        if not plan:
            return None
        return {**plan, "id": plan_id.lower()}

    def _mark_payment(identifier: str, **metadata: Any) -> None:
        record = app.state.payment_records.setdefault(identifier, {})
        record.update(metadata)
        record["updated_at"] = _timestamp()

    @app.post("/api/payment/intent")
    async def create_payment_intent(payload: PaymentIntentRequest):
        plan_details = _get_plan_details(payload.plan_id)
        if not plan_details:
            raise HTTPException(status_code=404, detail="Unknown plan identifier")

        try:
            intent = await to_thread.run_sync(
                lambda: stripe.PaymentIntent.create(
                    amount=plan_details["amount"],
                    currency=plan_details["currency"],
                    automatic_payment_methods={"enabled": True},
                    metadata={"plan_id": plan_details["id"]},
                )
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to create payment intent",
            ) from exc

        if not intent.client_secret:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe did not return a client secret",
            )

        _mark_payment(
            intent.id,
            plan_id=plan_details["id"],
            status=intent.status,
            amount=plan_details["amount"],
            currency=plan_details["currency"],
        )

        return {"client_secret": intent.client_secret}

    @app.post("/api/payment/webhook")
    async def payment_webhook(request: Request):
        if not settings.stripe_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stripe webhook secret is not configured",
            )

        payload_bytes = await request.body()
        payload = payload_bytes.decode("utf-8")
        signature = request.headers.get("stripe-signature")
        if not signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe signature header")

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=settings.stripe_webhook_secret,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload") from exc
        except stripe.error.SignatureVerificationError as exc:  # type: ignore[attr-defined]
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature") from exc

        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})

        if event_type == "payment_intent.succeeded":
            intent_id = data_object.get("id")
            if intent_id:
                _mark_payment(
                    intent_id,
                    status="succeeded",
                    plan_id=data_object.get("metadata", {}).get("plan_id"),
                    amount=data_object.get("amount_received") or data_object.get("amount"),
                    currency=data_object.get("currency"),
                    customer=data_object.get("customer"),
                )
        elif event_type in {"checkout.session.completed", "invoice.paid"}:
            session_id = data_object.get("id")
            if session_id:
                _mark_payment(
                    session_id,
                    status="succeeded",
                    plan_id=data_object.get("metadata", {}).get("plan_id"),
                    customer=data_object.get("customer"),
                )

        return {"received": True}

    @app.get("/api/payment/selftest")
    async def payment_selftest():
        env_summary = {
            "BRAIN_BASE": bool(settings.brain_base),
            "SERVICE_TOKEN": bool(settings.service_token),
            "ALLOWED_ORIGINS": bool(settings.allowed_origins),
            "STRIPE_SECRET_KEY": settings.has_stripe_secret,
            "STRIPE_WEBHOOK_SECRET": bool(settings.stripe_webhook_secret),
            "OPTIONAL_PAYPAL_ENABLED": settings.optional_paypal_enabled,
            "OPTIONAL_PAYPAL_WEBHOOK_SECRET": bool(settings.optional_paypal_webhook_secret),
        }

        key_value = settings.stripe_secret_key.get_secret_value()
        stripe_ok = key_value.startswith("sk_")
        if stripe_ok:
            try:
                await to_thread.run_sync(stripe.Balance.retrieve)
            except stripe.error.AuthenticationError:  # type: ignore[attr-defined]
                stripe_ok = False
            except stripe.error.APIConnectionError:  # type: ignore[attr-defined]
                stripe_ok = True
            except stripe.error.StripeError:  # type: ignore[attr-defined]
                stripe_ok = False

        return {
            "env": env_summary,
            "allowed_origins": settings.allowed_origins,
            "stripe_ok": stripe_ok,
        }

    @app.get("/ops", include_in_schema=False)
    async def ops():
        return {
            "brain": {"configured": bool(settings.brain_base)},
            "core": {"configured": bool(settings.service_token)},
            "frontend": {"ok": True},
            "stripe": {"configured": settings.has_stripe_secret},
            "stripe_secret_present": settings.has_stripe_secret,
        }

    @app.post("/api/payment/create")
    async def api_payment(payload: LegacyPaymentRequest):
        if not payload.plan_id:
            raise HTTPException(status_code=400, detail="Missing plan identifier")

        return {
            "status": "ok",
            "planId": payload.plan_id,
            "message": "Your upgrade request has been scheduled. We'll email confirmation shortly.",
            "reference": _new_token("payment"),
        }

    if settings.optional_paypal_enabled:

        @app.post("/api/paypal/order")
        async def paypal_order():
            order_id = _new_token("paypal-order")
            app.state.paypal_orders[order_id] = {
                "status": "created",
                "created_at": _timestamp(),
            }
            return JSONResponse(
                {"id": order_id, "status": "not_implemented"},
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
            )

        @app.post("/api/paypal/capture")
        async def paypal_capture(payload: dict[str, Any]):
            order_id = payload.get("id")
            record = app.state.paypal_orders.get(order_id or "")
            if record:
                record["status"] = "capture_not_implemented"
                record["updated_at"] = _timestamp()
            return JSONResponse(
                {"id": order_id, "status": "not_implemented"},
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
            )

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
