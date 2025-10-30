"""Application configuration for the Aserras web frontend."""

from __future__ import annotations

import os
from functools import lru_cache

# NOTE: Using pydantic v2+; BaseSettings imported from pydantic_settings.
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings."""

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
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "ASERRAS_ALLOWED_ORIGINS"),
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
        env_file=".env",
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:  # pragma: no cover - simple data mutation
        """Normalise endpoint configuration after loading settings and validate secrets."""

        if not self.stripe_secret_key or not self.stripe_secret_key.get_secret_value().strip():
            msg = "STRIPE_SECRET_KEY environment variable must be configured before starting the app."
            raise ValueError(msg)

        vite_base = os.getenv("VITE_API_BASE")
        base_url = (
            vite_base
            or self.brain_base
            or self.main_brain_base_url
            or ""
        ).rstrip("/")
        if vite_base or self.brain_base or "main_brain_base_url" not in self.model_fields_set:
            self.main_brain_base_url = base_url

        endpoint_suffixes = {
            "brain_api_auth_login": "/auth/login",
            "brain_api_auth_signup": "/auth/signup",
            "brain_api_payment_create": "/payment/create",
            "brain_api_payment_checkout": "/payment/checkout",
            "brain_api_chat_send": "/chat/send",
            "brain_api_user_history": "/chat/history",
            "brain_api_content_policies": "/content/policies",
            "brain_api_pricing": "/pricing",
            "brain_api_contact_send": "/contact/send",
            "brain_api_account_status": "/account/status",
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
