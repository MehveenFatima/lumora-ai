from datetime import datetime, timezone
from fastapi import APIRouter
from backend.app.ai.gateway import ai_gateway
from backend.app.core.config import settings
from backend.app.db.connection import get_db_pool
from backend.app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    now_iso = datetime.now(timezone.utc).isoformat()
    pool = await get_db_pool()

    db_info = {
        "status": "connected" if pool else "in_memory_fallback",
        "type": "postgresql" if pool else "in_memory",
        "pool_active": bool(pool),
        "url_configured": bool(settings.database_url),
    }

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
