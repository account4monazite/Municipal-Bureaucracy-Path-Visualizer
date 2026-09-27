
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.settings import get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
if settings.is_production:
    for noisy_logger in ("httpx", "httpcore", "supabase", "hpack"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info(
        "Starting Civic Task Navigator backend (env=%s, log_level=%s)",
        settings.app_env,
        settings.log_level,
    )
    yield
    logger.info("Shutting down Civic Task Navigator backend.")



def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Civic Task Navigator API",
        description=(
            "Backend for Civic Task Navigator — helps citizens navigate government procedures "
            "with AI-powered task extraction, dependency-graph roadmaps, and voice support."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    from fastapi.exceptions import RequestValidationError
    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s %s — %s", request.method, request.url, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            },
        )

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get(
        "/health",
        tags=["Health"],
        summary="Health check",
        response_description="Service is healthy",
    )
    async def health_check() -> dict:
        """Returns 200 OK when the service is up.  Used by load balancers."""
        return {"status": "healthy", "service": "civic-task-navigator-backend"}

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_router)
                    
    logger.info(
        "CORS allowed origins: %s", settings.allowed_origins
    )
    return app


app = create_app()
