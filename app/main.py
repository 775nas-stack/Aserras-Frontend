"""Primary FastAPI application for the Aserras frontend."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.dependencies.auth import resolve_user_from_request
from app.services.brain_api import BrainAPIClient
from app.settings import Settings, get_settings

BASE_DIR = Path(__file__).resolve().parent


def configure_templates(settings: Settings) -> Jinja2Templates:
    """Create Jinja environment with shared globals."""

    template_dir = Path(settings.TEMPLATE_DIR)
    templates = Jinja2Templates(directory=str(template_dir))
    templates.env.globals.update({
        "now": datetime.utcnow,
        "app_name": settings.APP_NAME,
        "tailwind_cdn": settings.CDN_TAILWIND_URL,
    })
    return templates


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory used by uvicorn and tests."""

    settings = settings or get_settings()
    templates = configure_templates(settings)
    app = FastAPI(title=settings.APP_NAME, debug=settings.APP_DEBUG)

    app.state.settings = settings
    app.state.templates = templates
    app.state.brain_client = BrainAPIClient(settings=settings)
    app.state.rate_limiter = MemoryRateLimiter(
        capacity=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(settings.STATIC_DIR)
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount(settings.STATIC_URL, StaticFiles(directory=static_dir), name="static")

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        limiter = app.state.rate_limiter
        client_ip = request.client.host if request.client else "anonymous"
        if limiter.is_rate_limited(client_ip):
            return JSONResponse(
                {"detail": "Too many requests. Please slow down."},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return await call_next(request)

    @app.middleware("http")
    async def add_user_to_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        brain_client: BrainAPIClient = request.app.state.brain_client
        settings: Settings = request.app.state.settings
        request.state.user = await resolve_user_from_request(
            request,
            settings=settings,
            client=brain_client,
        )
        response = await call_next(request)
        return response

    from app.routers import auth, chat, code, history, home, image, settings as settings_router

    app.include_router(home.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(image.router)
    app.include_router(code.router)
    app.include_router(history.router)
    app.include_router(settings_router.router)

    @app.get("/health", tags=["monitoring"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        templates = request.app.state.templates
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return templates.TemplateResponse(
                request,
                "404.html",
                {
                    "request": request,
                    "page_title": "Not found",
                    "user": getattr(request.state, "user", None),
                },
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            return templates.TemplateResponse(
                request,
                "500.html",
                {
                    "request": request,
                    "page_title": "Server error",
                    "user": getattr(request.state, "user", None),
                },
                status_code=exc.status_code,
            )
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse({"detail": exc.errors()}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(Exception)
    async def server_error_handler(request: Request, exc: Exception):
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "500.html",
            {
                "request": request,
                "page_title": "Server error",
                "user": getattr(request.state, "user", None),
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return app


class MemoryRateLimiter:
    """In-memory fixed-window rate limiter."""

    def __init__(self, *, capacity: int, window_seconds: int) -> None:
        from collections import defaultdict, deque
        from time import time

        self.capacity = capacity
        self.window_seconds = window_seconds
        self._store: dict[str, "deque[float]"] = defaultdict(lambda: deque(maxlen=capacity))
        self._time = time

    def is_rate_limited(self, key: str) -> bool:
        timestamps = self._store[key]
        now = self._time()
        while timestamps and now - timestamps[0] > self.window_seconds:
            timestamps.popleft()
        if len(timestamps) >= self.capacity:
            return True
        timestamps.append(now)
        return False


app = create_app()
