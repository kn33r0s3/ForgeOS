"""
Hami — main FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload

This file only wires things together: app instance, CORS, startup DB
init, and router registration. All logic lives in services/ and api/.
"""

import os
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import init_db, SessionLocal
from app.api import signals, analyze, opportunities, observer, forge, world, workers, intelligence, rare_signals, products, lessons, orchestrator, earn, payments, repair_shop, evidence_triage, public, scheduled, substrate, forge_bot
from app.security import api_key_middleware, require_owner_api_key
from app.request_limits import PublicWriteSizeLimitMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    on_startup()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Hami — the ForgeOS-evolved economic intelligence system.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Optional API-key gate (only enforced on POST/PUT/PATCH/DELETE when
# FORGE_API_KEY is set). Silent pass-through otherwise — local-first by default.
app.middleware("http")(api_key_middleware)
app.add_middleware(PublicWriteSizeLimitMiddleware)

CRON_SCHEDULE = "0 0 * * *"


def on_startup():
    init_db()
    if not settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED:
        logger.info("Legacy intelligence startup disabled.")
        return

    from app.services import (
        autonomy_engine,
        money_engine,
        scenario_engine,
        source_manager,
        truth_audit,
    )

    # Seed default Source reliability rows. Revenue-source startup
    # withdraws payout percentages that were stored without a primary
    # terms page. It does not insert new figures.
    db = SessionLocal()
    try:
        truth_audit.reconcile_stale_cycles(db)
        source_manager.seed_default_sources(db)
        money_engine.seed_default_revenue_sources(db)
        autonomy_engine.seed_default_policy(db)
        scenario_engine.seed_default_scenarios(db)
        scenario_engine.seed_musk_forecaster_and_predictions(db)
        scenario_engine.seed_phase1_indicators(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "ai_provider": settings.AI_PROVIDER,
        "focus": "Living system for understanding and acting upon the real world",
    }


def _health_details() -> dict[str, Any]:
    cycle = None
    database_error = None
    from app import database, models

    database_url_configured = bool(os.getenv("DATABASE_URL"))
    is_vercel = bool(os.getenv("VERCEL"))
    cron_secret_configured = bool(os.getenv("CRON_SECRET"))
    database_driver = database.engine.dialect.name
    database_durability = (
        "ephemeral"
        if is_vercel and database_driver == "sqlite" and not database_url_configured
        else "configured"
    )

    try:
        db = database.SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            row = db.query(models.CycleRun).order_by(models.CycleRun.id.desc()).first()
            if row is not None:
                cycle = {
                    "id": row.id,
                    "status": row.status,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                }
        finally:
            db.close()
    except Exception as exc:
        database_error = type(exc).__name__

    blockers = []
    if is_vercel and database_durability == "ephemeral":
        blockers.append("durable_database_not_configured")
    if is_vercel and not cron_secret_configured:
        blockers.append("cron_secret_not_configured")
    if database_error is not None:
        blockers.append("database_unavailable")

    return {
        "status": "degraded" if blockers else "ok",
        "cycle": cycle,
        "database": {
            "driver": database_driver,
            "durability": database_durability,
            "url_configured": database_url_configured,
            "available": database_error is None,
            "error": database_error,
        },
        "scheduler": {
            "cron_secret_configured": cron_secret_configured,
            "cron_schedule": CRON_SCHEDULE,
        },
        "readiness": {
            "ready": not blockers,
            "blockers": blockers,
        },
    }


@app.get("/health")
def health():
    details = _health_details()
    return {"status": details["status"], "ready": details["readiness"]["ready"]}


@app.get("/health/details")
def health_details(request: Request):
    require_owner_api_key(request)
    return _health_details()


@app.get("/ai/status")
def ai_status():
    from app.services.ai_engine import get_provider_status
    return get_provider_status()


@app.get("/ai/tools")
def ai_tools():
    from app.services.tool_registry import default_registry

    registry = default_registry()
    return [
        {
            **capability.__dict__,
            "available_now": registry.get(capability.name).is_available(),
        }
        for capability in registry.list_capabilities()
    ]


for _router in (
    signals.router,
    analyze.router,
    opportunities.router,
    observer.router,
    forge.router,
    substrate.router,
    world.router,
    workers.router,
    intelligence.router,
    rare_signals.router,
    products.router,
    lessons.router,
    orchestrator.router,
    earn.router,
    payments.router,
    repair_shop.router,
    evidence_triage.router,
    public.router,
    scheduled.router,
    forge_bot.router,
):
    app.include_router(_router)
    # Vercel keeps the /api prefix. Same router, no second implementation.
    app.include_router(_router, prefix="/api", include_in_schema=False)


def _alias_app_routes_under_api() -> None:
    """Mirror every root route under /api for the Vercel service ingress.

    Only `/api/*` reaches the Python service on Vercel, so the machine-readable
    contract must answer there too. The interactive docs UIs are deliberately
    left unaliased: their HTML points at `/openapi.json`, which the frontend
    rewrite answers with the SPA, so aliasing them would ship a broken page.
    """
    for route in list(app.routes):
        path = getattr(route, "path", None)
        endpoint = getattr(route, "endpoint", None)
        methods = getattr(route, "methods", None)
        if not path or endpoint is None or not path.startswith("/") or path.startswith("/api"):
            continue
        if path in {"/docs", "/docs/oauth2-redirect", "/redoc"}:
            continue
        alias = "/api" if path == "/" else f"/api{path}"
        app.add_api_route(
            alias,
            endpoint,
            methods=sorted(methods) if methods else ["GET"],
            include_in_schema=False,
            name=f"vercel_{getattr(route, 'name', alias)}",
        )


_alias_app_routes_under_api()


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = ".".join(str(part) for part in location if part != "body") or "request"
        errors.append({
            "field": field,
            "message": (
                "A value is required."
                if error.get("type") == "missing"
                else "Invalid value."
            ),
        })
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed.", "errors": errors},
    )


@app.exception_handler(ValueError)
async def invalid_input(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request value."},
    )


@app.exception_handler(HTTPException)
async def safe_http_exception(request: Request, exc: HTTPException):
    if exc.status_code == 422:
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid request value."},
            headers=exc.headers,
        )
    return await http_exception_handler(request, exc)
