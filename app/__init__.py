"""Expose the FastAPI application at package level."""

from app.main import app, create_app

__all__ = ["app", "create_app"]
