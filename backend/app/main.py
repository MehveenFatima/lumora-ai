from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging, get_logger
from backend.app.db.connection import get_db_pool, close_db_pool
from backend.app.api.v1.router import api_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode...")

    # Assert Gemini generation model integrity
    from backend.app.ai.gateway import ai_gateway
    gemini_provider = ai_gateway.get_provider("gemini")
    effective_model = gemini_provider.model_name if gemini_provider else None

    logger.info(f"[AI Gateway] Effective Gemini generation model: {effective_model}")
    if effective_model != "gemini-3.8-flash":
        raise RuntimeError(
            f"Startup configuration validation failed: Effective Gemini generation model is '{effective_model}', "
            f"expected 'gemini-3.8-flash'. Obsolete model fallback is strictly prohibited."
        )

    if settings.is_production:
        if not settings.jwt_secret or len(settings.jwt_secret) < 32:
            raise RuntimeError(
                "JWT_SECRET must be set to a random value of at least 32 characters when ENVIRONMENT=production."
            )
        if not settings.database_url:
            logger.warning("ENVIRONMENT=production without DATABASE_URL: data will not survive a restart.")

    await get_db_pool()
    yield
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")
    await close_db_pool()


app = FastAPI(
    title="LumoraAI RAG Backend API",
    description="Workspace-Scoped Retrieval-Augmented Generation AI Tutor and Document Ingestion API.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Explicit CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    err_detail = str(exc) if settings.environment == "development" else "Internal server error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": err_detail,
            "success": False,
            "error": "Internal server error",
            "message": err_detail,
        },
    )


# Mount API Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "lumora-backend",
        "docs": "/docs",
        "health": "/api/v1/health",
        "version": "0.1.0",
    }
