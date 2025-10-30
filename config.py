"""Application configuration for the Aserras web frontend."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

# NOTE: Using pydantic v2+; BaseSettings imported from pydantic_settings.
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LOGGER = logging.getLogger(__name__)
DEFAULT_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    """Environment-backed settings."""

class Settings(BaseSettings):
    app_name: str = Field(
        "Aserras Frontend",
        title="Application Name",
    )   
    host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("HOST", "ASERRAS_HOST"),
    )
    port: int = Field(
        default=8001,
        validation_alias=AliasChoices("PORT", "ASERRAS_PORT"),
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG", "ASERRAS_DEBUG"),
    )
    brain_base: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BRAIN_BASE", "ASERRAS_BRAIN_BASE"),
    )
    service_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SERVICE_TOKEN", "ASERRAS_SERVICE_TOKEN"),
    )
    allowed_origins_raw: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ALLOWED_ORIGINS",
            "ASERRAS_ALLOWED_ORIGINS",
            "CORS_ORIGINS",
        ),
    )
    stripe_secret_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("STRIPE_SECRET_KEY", "ASERRAS_STRIPE_SECRET_KEY"),
    )
    stripe_webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "STRIPE_WEBHOOK_SECRET",
            "ASERRAS_STRIPE_WEBHOOK_SECRET",
        ),
    )
    stripe_price_pro: str = Field(
        default="price_test_pro",
        validation_alias=AliasChoices(
            "STRIPE_PRICE_PRO",
            "ASERRAS_STRIPE_PRICE_PRO",
        ),
    )
    stripe_price_enterprise: str = Field(
        default="price_test_enterprise",
        validation_alias=AliasChoices(
            "STRIPE_PRICE_ENTERPRISE",
            "ASERRAS_STRIPE_PRICE_ENTERPRISE",
        ),
    )
    optional_paypal_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "OPTIONAL_PAYPAL_ENABLED",
            "ASERRAS_OPTIONAL_PAYPAL_ENABLED",
        ),
    )
    optional_paypal_webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPTIONAL_PAYPAL_WEBHOOK_SECRET",
            "ASERRAS_OPTIONAL_PAYPAL_WEBHOOK_SECRET",
        ),
    )

    main_brain_base_url: str = "https://core.aserras.com/api"
    brain_api_auth_login: str | None = None
    brain_api_auth_signup: str | None = None
    brain_api_payment_create: str | None = None
    brain_api_payment_checkout: str | None = None
    brain_api_chat_send: str | None = None
    brain_api_user_history: str | None = None
    brain_api_content_policies: str | None = None
    brain_api_pricing: str | None = None
    brain_api_contact_send: str | None = None
    brain_api_account_status: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="ASERRAS_",
        case_sensitive=False,
        env_file=DEFAULT_ENV_FILE,
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:  # pragma: no cover - simple data mutation
        """Normalise endpoint configuration after loading settings and validate secrets."""

      
                    if not self.has_stripe_secret:
            LOGGER.warning(
                "Stripe secret key is not configured; Stripe-powered features will be disabled."
            )

        vite_base = os.getenv("VITE_API_BASE")
        
                    base_url = (self.main_brain_base_url or "").rstrip("/")
        if vite_base:
            candidate = vite_base.strip()
            if candidate:
                candidate = candidate.rstrip("/")
                if not candidate.endswith("/api"):
                    candidate = f"{candidate}/api"
                base_url = candidate
        elif self.brain_base:
            base_url = self.brain_base.rstrip("/")
        elif "main_brain_base_url" not in self.model_fields_set:
            base_url = base_url.rstrip("/")

        self.main_brain_base_url = base_url

        endpoint_suffixes = {
            "brain_api_auth_login": "/auth/login",
            "brain_api_auth_signup": "/auth/signup",
            "brain_api_payment_create": "/payment/create",
            "brain_api_payment_checkout": "/payments/create-checkout-session",
            "brain_api_chat_send": "/chat/send",
            "brain_api_user_history": "/chat/history",
            "brain_api_content_policies": "/content/policies",
            "brain_api_pricing": "/pricing",
            "brain_api_contact_send": "/contact/send",
            "brain_api_account_status": "/payments/subscription-status",
        }

        for field_name, suffix in endpoint_suffixes.items():
            if field_name in self.model_fields_set:
                continue
            setattr(self, field_name, f"{base_url}{suffix}" if base_url else suffix)

    @property
    def allowed_origins(self) -> list[str]:
        """Return a parsed list of allowed origins from configuration."""

        if not self.allowed_origins_raw:
            return []
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def has_stripe_secret(self) -> bool:
        """Return True when a Stripe secret key has been provided."""

        return bool(self.stripe_secret_key and self.stripe_secret_key.get_secret_value().strip())

    def stripe_price_for_plan(self, plan: str) -> str | None:
        """Return the configured Stripe price identifier for the supplied plan."""

        mapping = {
            "pro": self.stripe_price_pro.strip(),
            "enterprise": self.stripe_price_enterprise.strip(),
        }
        return mapping.get(plan.lower()) or None


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
