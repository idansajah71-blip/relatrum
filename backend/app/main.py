"""RELATRUM API entry point with health, versioning, CORS, tracing and errors."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import (
    ApiError,
    api_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging, get_logger, request_id_var
from app.database import create_all, init_engine, engine as db_engine
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    get_logger(__name__).info("Starting RELATRUM backend (env=%s)", settings.app_env)
    init_engine(settings.database_url)
    if settings.app_env != "production":
        create_all()  # quick-start convenience; Alembic is authoritative for production
    app.state.app_env = settings.app_env
    yield
    get_logger(__name__).info("Shutting down RELATRUM backend")
    if db_engine is not None:
        db_engine.dispose()


app = FastAPI(
    title="RELATRUM API",
    version=get_settings().app_version,
    description=(
        "Evidence Intelligence Platform. "
        "Reality Evidence, Layered Alignment, Temporal Reasoning & Uncertainty Mapping."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request_id_var.set(request_id)
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.get("/health/live", tags=["health"], operation_id="health_live")
def health_live() -> dict:
    return envelope_health("live", "alive")


@app.get("/health/ready", tags=["health"], operation_id="health_ready")
def health_ready():
    settings = get_settings()
    db_ok = db_engine is not None
    provider_ok = settings.ai_provider in ("mock",) or bool(
        settings.gemini_api_key if settings.ai_provider == "gemini" else settings.groq_api_key
    )
    ready = db_ok and provider_ok
    body = envelope_health(
        "ready",
        "ready" if ready else "degraded",
        database=db_ok,
        ai_provider=settings.ai_provider if provider_ok else "misconfigured",
    )
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=200 if ready else 503, content=body)


def envelope_health(check: str, status: str, **details) -> dict:
    body = {"success": True, "message": f"health/{check} = {status}", "data": {"check": check, "status": status}}
    data = body["data"]
    data.update(details)
    return body


app.include_router(api_router, prefix="/api/v1")


__all__ = ["app"]
