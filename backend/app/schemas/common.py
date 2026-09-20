from typing import Generic, Optional, TypeVar, Any
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    success: bool = True
    message: Optional[str] = None
    data: Optional[DataT] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: str
    details: Optional[Any] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "lumora-backend"
    version: str = "0.1.0"
    backend: str = "healthy"
    presentation_mode: bool = False
    database: Optional[Any] = None
    vector: Optional[Any] = None
    gemini: Optional[Any] = None
    storage: Optional[Any] = None
    timestamp: Optional[str] = None
