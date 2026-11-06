import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging, get_logger
from backend.app.db.connection import close_db_pool, connect_with_retry, keep_connecting, run_migrations
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

    background_tasks = []

    async def on_database_ready():
        await run_migrations()
        from backend.app.api.routes.documents import resume_stalled_documents, watch_stalled_documents

        try:
            result = await resume_stalled_documents()
            if result["resumed"] or result["failed"]:
                logger.warning(
                    f"Interrupted uploads: {result['resumed']} resumed, {result['failed']} marked failed."
                )
        except Exception as e:
            logger.warning(f"Could not check for interrupted uploads: {e}")
        from backend.app.services import bkt_fitting

        try:
            await bkt_fitting.load_saved()
        except Exception as e:
            logger.warning(f"Could not load the fitted BKT parameters: {e}")
        if not background_tasks:
            background_tasks.append(asyncio.create_task(watch_stalled_documents()))
            background_tasks.append(asyncio.create_task(bkt_fitting.refit_loop()))

    # Start serving even when the database is unreachable (e.g. a paused free-tier project):
    # data requests get a clear 503 and the API reconnects and migrates on its own once it is back.
    reconnect_task = None
    if await connect_with_retry(attempts=3):
        await on_database_ready()
    elif settings.database_url:
        logger.error("Starting without the database; retrying every 30 s in the background.")
        reconnect_task = asyncio.create_task(keep_connecting(on_database_ready))
    yield
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}...")
    if reconnect_task:
        reconnect_task.cancel()
    for task in background_tasks:
        task.cancel()
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
