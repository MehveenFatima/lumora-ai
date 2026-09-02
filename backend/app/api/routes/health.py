from fastapi import APIRouter
from backend.app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="lumora-backend",
        version="0.1.0",
    )
