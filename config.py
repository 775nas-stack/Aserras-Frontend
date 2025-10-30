"""Application configuration for the Aserras web frontend."""

from __future__ import annotations

import os
from functools import lru_cache

# NOTE: Using pydantic v2+; BaseSettings imported from pydantic_settings.
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings."""

    main_brain_base_url: str = "https://core.aserras.com/api"
    brain_api_auth_login: str | None = None
    brain_api_auth_signup: str | None = None
    brain_api_payment_create: str | None = None
    brain_api_chat_send: str | None = None
    brain_api_user_history: str | None = None
    brain_api_content_policies: str | None = None
    brain_api_pricing: str | None = None
    brain_api_contact_send: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="ASERRAS_",
        case_sensitive=False,
    )

    def model_post_init(self, __context: object) -> None:  # pragma: no cover - simple data mutation
        """Normalise endpoint configuration after loading settings."""

        vite_base = os.getenv("VITE_API_BASE")
        base_url = (vite_base or self.main_brain_base_url or "").rstrip("/")
        if vite_base or "main_brain_base_url" not in self.model_fields_set:
            self.main_brain_base_url = base_url

        endpoint_suffixes = {
            "brain_api_auth_login": "/auth/login",
            "brain_api_auth_signup": "/auth/signup",
            "brain_api_payment_create": "/payment/create",
            "brain_api_chat_send": "/chat/send",
            "brain_api_user_history": "/chat/history",
            "brain_api_content_policies": "/content/policies",
            "brain_api_pricing": "/pricing",
            "brain_api_contact_send": "/contact/send",
        }

        for field_name, suffix in endpoint_suffixes.items():
            if field_name in self.model_fields_set:
                continue
            setattr(self, field_name, f"{base_url}{suffix}" if base_url else suffix)


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
