"""
Forge — main FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload

This file only wires things together: app instance, CORS, startup DB
init, and router registration. All logic lives in services/ and api/.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, SessionLocal
from app.api import signals, analyze, opportunities, observer, forge, world, workers, intelligence, rare_signals, products, lessons, orchestrator, earn, payments, repair_shop, evidence_triage, public
from app.services import source_manager, money_engine, autonomy_engine, scenario_engine, truth_audit
from app.security import api_key_middleware

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ForgeOS — Personal AI Opportunity Intelligence Engine.",
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


@app.on_event("startup")
def on_startup():
    init_db()
    # Seed default Source reliability rows (manual/github/reddit/news/web)
    # and default RevenueSource rows (real, sourced, dated payout data —
    # see money_engine.py's DEFAULT_REVENUE_SOURCES). Both are no-ops
    # once already seeded — safe to run every startup.
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
        "focus": "Personal AI Opportunity Intelligence Engine",
    }


@app.get("/health")
def health():
    cycle = None
    try:
        from app.database import SessionLocal
        from app import models
        db = SessionLocal()
        try:
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
    except Exception:
        cycle = None
    return {"status": "ok", "cycle": cycle}


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


app.include_router(signals.router)
app.include_router(analyze.router)
app.include_router(opportunities.router)
app.include_router(observer.router)
app.include_router(forge.router)
app.include_router(world.router)
app.include_router(workers.router)
app.include_router(intelligence.router)
app.include_router(rare_signals.router)
app.include_router(products.router)
app.include_router(lessons.router)
app.include_router(orchestrator.router)
app.include_router(earn.router)
app.include_router(payments.router)
app.include_router(repair_shop.router)
app.include_router(evidence_triage.router)
app.include_router(public.router)


@app.exception_handler(ValueError)
async def invalid_input(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"detail": str(exc)})
