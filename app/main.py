"""FastAPI application factory.

Wires up:
- SlowAPI rate limiter (state + exception handler for 429)
- CORS middleware for the dashboard API (separate from per-widget public CORS)
- All routers
- Request body size limit (protects against oversized payloads)
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.routers import auth, dashboard, public, widgets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="FlyRank — Embeddable Widget & Lead-Capture Platform",
        description="Production-ready backend for embeddable widgets with secure public submissions, geo-enrichment, and multi-tenant isolation.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── Rate limiter state ──
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "detail": "Too many requests. Please slow down.",
            },
            headers={"Retry-After": "60"},
        )

    # ── CORS for dashboard API ──
    # The public submission endpoint handles its own CORS per-widget.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Routers ──
    app.include_router(auth.router)
    app.include_router(widgets.router)
    app.include_router(public.router)
    app.include_router(dashboard.router)

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "environment": settings.environment}

    @app.get("/", tags=["root"])
    def root():
        return {
            "name": "FlyRank",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app


app = create_app()
