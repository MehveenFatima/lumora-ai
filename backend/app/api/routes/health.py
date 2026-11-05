import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Response
from backend.app.ai.gateway import ai_gateway
from backend.app.core.config import settings
from backend.app.db.connection import database_state, get_db_pool
from backend.app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    check_db: bool = Query(False, description="Also run a query, so the database counts as active"),
) -> HealthResponse:
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        pool = await get_db_pool()
    except HTTPException:
        # Production with the database unreachable: the API itself is up, so report instead of failing
        pool = None

    state = database_state()
    db_unavailable = bool(settings.database_url) and not pool
    db_info = {
        "status": "connected" if pool else ("unavailable" if db_unavailable else "in_memory_fallback"),
        "type": "postgresql" if pool else "in_memory",
        "pool_active": bool(pool),
        "url_configured": bool(settings.database_url),
        "migrations": state["migrations"],
    }
    if db_unavailable and state["last_error"]:
        db_info["error"] = state["last_error"]
    if check_db and pool:
        # Used by the scheduled keep-awake ping: a real query keeps a free-tier database active
        try:
            async with pool.acquire() as conn:
                await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=5)
        except Exception as e:
            db_info["status"] = "error"
            db_info["error"] = type(e).__name__

    if settings.presentation_mode and not pool:
        db_info["status"] = "unavailable"
        db_info["error"] = "Presentation backend unavailable: Real PostgreSQL connection required."

    vector_info = {
        "capability": "pgvector" if pool else "in_memory_numpy",
        "provider": "postgresql" if pool else "numpy_cosine",
        "dimensions": settings.embedding_dimensions,
    }

    gemini_info = {
        "configured": bool(settings.gemini_api_key),
        "model": settings.gemini_model,
        "embedding_model": settings.gemini_embedding_model,
    }

    storage_info = {
        "status": "active" if (settings.supabase_url and settings.supabase_service_role_key) else "local_fallback",
        "bucket": settings.supabase_storage_bucket,
    }

    ai_report = ai_gateway.get_readiness_report()
    providers = ai_report.get("providers", {})
    any_healthy = any(p.get("status") == "healthy" for p in providers.values())
    any_cooldown = any(p.get("status") == "cooldown" for p in providers.values())

    if any_healthy:
        ai_status = "healthy"
    elif any_cooldown:
        ai_status = "degraded"
    else:
        ai_status = "unavailable"

    ai_info = {
        "status": ai_status,
        "gateway_status": ai_report.get("gateway_status", "degraded"),
        "fallback_available": True,
        "providers": providers,
        "routing": ai_report.get("routing", {}),
    }

    overall_status = "ok"
    if settings.presentation_mode and not pool:
        overall_status = "error"
    elif db_unavailable or db_info["status"] == "error":
        overall_status = "degraded"
    # The plain check stays 200 while the process is up (it is the host's liveness check); the
    # scheduled ping asks for check_db and gets 503, so a database outage shows up as a failed run.
    if check_db and settings.database_url and db_info["status"] != "connected":
        response.status_code = 503

    return HealthResponse(
        status=overall_status,
        service=settings.app_name,
        version="0.1.0",
        backend="healthy",
        presentation_mode=settings.presentation_mode,
        database=db_info,
        vector=vector_info,
        gemini=gemini_info,
        ai=ai_info,
        storage=storage_info,
        timestamp=now_iso,
    )
