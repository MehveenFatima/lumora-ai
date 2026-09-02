from fastapi import APIRouter
from backend.app.api.routes import health, documents, tutor, workspaces

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(workspaces.router)
api_router.include_router(documents.router)
api_router.include_router(tutor.router)
