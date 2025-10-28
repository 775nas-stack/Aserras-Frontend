"""Application configuration for the Aserras web frontend."""

from functools import lru_cache

# NOTE: Using pydantic v2+; BaseSettings imported from pydantic_settings.
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Environment-backed settings."""

    main_brain_base_url: str = "https://brain.aserras.com/api"
    brain_api_auth_login: str = "https://brain.aserras.com/api/auth/login"
    brain_api_auth_signup: str = "https://brain.aserras.com/api/auth/signup"
    brain_api_payment_create: str = "https://brain.aserras.com/api/payment/create"
    brain_api_chat_send: str = "https://brain.aserras.com/api/chat/send"
    brain_api_user_history: str = "https://brain.aserras.com/api/user/history"
    brain_api_content_policies: str = "https://brain.aserras.com/api/content/policies"
    brain_api_pricing: str = "https://brain.aserras.com/api/pricing"

    class Config:
        env_prefix = "ASERRAS_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
