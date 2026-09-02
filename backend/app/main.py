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
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
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
