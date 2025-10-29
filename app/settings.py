"""Application settings for the Aserras frontend."""

from functools import lru_cache
from typing import Any

from pydantic import AnyHttpUrl, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration used throughout the application."""

    APP_NAME: str = "Aserras Frontend"
    APP_DEBUG: bool = False
    BRAIN_API_URL: AnyHttpUrl = "https://brain.aserras.com"
    STATIC_URL: str = "/static"
    TEMPLATE_DIR: str = "templates"
    STATIC_DIR: str = "static"
    SESSION_COOKIE_NAME: str = "aserras_session"
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_MAX_AGE: int = 60 * 60 * 24 * 7  # one week
    BRAIN_API_TIMEOUT: float = 30.0
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    CDN_TAILWIND_URL: HttpUrl = "https://cdn.jsdelivr.net/npm/tailwindcss@3.4.10/dist/tailwind.min.css"

    # Compatibility fields for legacy templates
    main_brain_base_url: AnyHttpUrl = "https://brain.aserras.com/api"
    brain_api_auth_login: AnyHttpUrl = "https://brain.aserras.com/api/auth/login"
    brain_api_auth_signup: AnyHttpUrl = "https://brain.aserras.com/api/auth/signup"
    brain_api_payment_create: AnyHttpUrl = "https://brain.aserras.com/api/payment/create"
    brain_api_chat_send: AnyHttpUrl = "https://brain.aserras.com/api/chat/send"
    brain_api_user_history: AnyHttpUrl = "https://brain.aserras.com/api/user/history"
    brain_api_content_policies: AnyHttpUrl = "https://brain.aserras.com/api/content/policies"
    brain_api_pricing: AnyHttpUrl = "https://brain.aserras.com/api/pricing"

    model_config = SettingsConfigDict(
        env_prefix="ASERRAS_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
