"""Stripe subscription endpoints for checkout sessions and webhooks."""

from __future__ import annotations

import base64
import json
from binascii import Error as BinasciiError
from typing import Any

try:  # pragma: no cover - exercised indirectly through app-level tests
    import stripe  # type: ignore[assignment]
except ModuleNotFoundError:  # pragma: no cover - fallback when dependency missing
    from app import stripe  # type: ignore  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from config import Settings, get_settings

router = APIRouter(prefix="/api/payments", tags=["payments"])

DEFAULT_PLAN = "free"


class CheckoutSessionRequest(BaseModel):
    """Request payload for creating a Stripe Checkout session."""

    plan: str


class CheckoutSessionResponse(BaseModel):
    """Response payload containing the checkout URL."""

    url: str


class SubscriptionStatusResponse(BaseModel):
    """Response describing the user's active subscription plan."""

    plan: str


def _decode_jwt_email(token: str) -> str:
    """Extract the email claim from a JWT without verifying its signature."""

    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("JWT does not contain a payload segment")

    payload_segment = parts[1]
    padding = "=" * (-len(payload_segment) % 4)
    payload_bytes = base64.urlsafe_b64decode(payload_segment + padding)
    data = json.loads(payload_bytes.decode("utf-8"))

    email = (
        data.get("email")
        or data.get("sub")
        or data.get("username")
        or data.get("user")
    )
    if not isinstance(email, str) or not email.strip():
        raise ValueError("JWT payload does not include an email claim")
    return email.strip()


def _get_current_user_email(request: Request) -> str:
    """Return the authenticated user's email derived from the Authorization header."""

    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

    try:
        return _decode_jwt_email(token).lower()
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, BinasciiError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from exc


def _get_price_id(plan: str, settings: Settings) -> str:
    """Resolve the Stripe price identifier for the given plan."""

    price_id = settings.stripe_price_for_plan(plan)
    if not price_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown plan identifier")
    return price_id


def _set_user_plan(app, email: str, plan: str) -> None:
    """Persist the user's plan in application state."""

    email_key = email.lower()
    app.state.user_subscriptions[email_key] = plan.lower()


@router.post(
    "/create-checkout-session",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout_session(
    payload: CheckoutSessionRequest,
    settings: Settings = Depends(get_settings),
    email: str = Depends(_get_current_user_email),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for the requested plan."""

    price_id = _get_price_id(payload.plan, settings)
    normalized_plan = payload.plan.lower()

    metadata = {"plan": normalized_plan, "email": email}

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            success_url="https://aserras.com/dashboard?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://aserras.com/pricing?canceled=true",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=email,
            metadata=metadata,
            subscription_data={"metadata": metadata},
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create checkout session",
        ) from exc

    session_url = getattr(session, "url", None)
    if not session_url:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Stripe did not return a checkout URL")

    return CheckoutSessionResponse(url=session_url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    """Handle Stripe webhook events related to subscriptions."""

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    secret = settings.stripe_webhook_secret
    if not secret:
        return Response(status_code=status.HTTP_200_OK)

    event: dict[str, Any] | None = None
    try:
        event = stripe.Webhook.construct_event(
            payload=payload.decode("utf-8"),
            sig_header=sig_header,
            secret=secret,
        )
    except (ValueError, stripe.error.StripeError):  # type: ignore[attr-defined]
        return Response(status_code=status.HTTP_200_OK)

    event_type = event.get("type", "") if isinstance(event, dict) else ""
    data_object = {}
    if isinstance(event, dict):
        data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        metadata = data_object.get("metadata", {}) or {}
        email = (
            metadata.get("email")
            or data_object.get("customer_details", {}).get("email")
            or data_object.get("customer_email")
        )
        plan = metadata.get("plan")
        if isinstance(email, str) and isinstance(plan, str):
            _set_user_plan(request.app, email, plan)
    elif event_type == "customer.subscription.updated":
        metadata = data_object.get("metadata", {}) or {}
        email = metadata.get("email")
        plan = metadata.get("plan")
        status_value = data_object.get("status")
        if isinstance(email, str):
            if status_value == "active" and isinstance(plan, str):
                _set_user_plan(request.app, email, plan)
            elif status_value in {"canceled", "incomplete", "incomplete_expired", "past_due", "unpaid"}:
                _set_user_plan(request.app, email, DEFAULT_PLAN)
    elif event_type == "customer.subscription.deleted":
        metadata = data_object.get("metadata", {}) or {}
        email = metadata.get("email")
        if isinstance(email, str):
            _set_user_plan(request.app, email, DEFAULT_PLAN)

    return Response(status_code=status.HTTP_200_OK)


@router.get(
    "/subscription-status",
    response_model=SubscriptionStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def subscription_status(
    request: Request,
    email: str = Depends(_get_current_user_email),
) -> SubscriptionStatusResponse:
    """Return the stored subscription plan for the authenticated user."""

    plan = request.app.state.user_subscriptions.get(email, DEFAULT_PLAN)
    return SubscriptionStatusResponse(plan=plan)
