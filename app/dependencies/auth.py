"""Authentication helpers and dependencies."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.services.brain_api import BrainAPIClient, BrainAPIError, BrainAPIUnavailable
from app.settings import Settings, get_settings


def get_brain_client(settings: Settings = Depends(get_settings)) -> BrainAPIClient:
    """Return a client for communicating with Aserras Brain."""

    return BrainAPIClient(settings=settings)


def get_session_token(request: Request, settings: Settings = Depends(get_settings)) -> str | None:
    """Extract the JWT session token from the request cookies."""

    return request.cookies.get(settings.SESSION_COOKIE_NAME)


async def fetch_user(
    request: Request,
    *,
    client: BrainAPIClient,
    token: str | None,
) -> dict[str, Any] | None:
    """Utility used by dependencies and middleware to resolve the current user."""

    if not token:
        return None

    try:
        profile = await client.get_profile(token)
    except BrainAPIUnavailable:
        return None
    except BrainAPIError as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise

    return profile


async def get_optional_user(
    request: Request,
    token: str | None = Depends(get_session_token),
    client: BrainAPIClient = Depends(get_brain_client),
) -> dict[str, Any] | None:
    return await fetch_user(request, client=client, token=token)


async def require_user(user: dict[str, Any] | None = Depends(get_optional_user)) -> dict[str, Any]:
    """Ensure that a user is authenticated before proceeding."""

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


async def resolve_user_from_request(request: Request, settings: Settings, client: BrainAPIClient) -> dict[str, Any] | None:
    """Helper used by middleware to reuse the dependency logic."""

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    return await fetch_user(request, client=client, token=token)
