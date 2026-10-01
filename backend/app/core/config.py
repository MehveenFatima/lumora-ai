import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Resolve absolute paths to repository root and backend directory .env files
_CONFIG_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CONFIG_DIR.parent.parent
_ROOT_DIR = _BACKEND_DIR.parent

_ROOT_ENV = _ROOT_DIR / ".env"
_BACKEND_ENV = _BACKEND_DIR / ".env"

# Explicitly load .env files
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV)
if _BACKEND_ENV.exists():
    load_dotenv(_BACKEND_ENV)


class Settings(BaseSettings):
    # Server & Environment
    app_name: str = "LumoraAI Backend"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    presentation_mode: bool = Field(default=False, validation_alias="PRESENTATION_MODE")
    port: int = Field(default=8000, validation_alias="PORT")
    frontend_origin: str = Field(default="http://localhost:3000", validation_alias="FRONTEND_ORIGIN")
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Google Gemini AI Configuration (Single authoritative source of truth: models/gemini-3.8-flash)
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="models/gemini-3.8-flash", validation_alias="GEMINI_MODEL")
    gemini_embedding_model: str = Field(
        default="models/gemini-embedding-001", validation_alias="GEMINI_EMBEDDING_MODEL"
    )
    embedding_dimensions: int = Field(default=768, validation_alias="EMBEDDING_DIMENSIONS")

    # Secondary AI Provider Configuration (OpenRouter / OpenAI-compatible)
    secondary_ai_provider_name: str = Field(default="openrouter", validation_alias="SECONDARY_AI_PROVIDER_NAME")
    openrouter_api_key: Optional[str] = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    secondary_ai_api_key: Optional[str] = Field(default=None, validation_alias="SECONDARY_AI_API_KEY")
    secondary_ai_base_url: str = Field(default="https://openrouter.ai/api/v1", validation_alias="SECONDARY_AI_BASE_URL")
    secondary_ai_model: str = Field(default="qwen/qwen3.8-27b:free", validation_alias="SECONDARY_AI_MODEL")
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, validation_alias="OPENAI_BASE_URL")
    openai_model: Optional[str] = Field(default=None, validation_alias="OPENAI_MODEL")

    @property
    def effective_secondary_api_key(self) -> Optional[str]:
        return self.openrouter_api_key or self.secondary_ai_api_key or self.openai_api_key

    @property
    def effective_secondary_base_url(self) -> str:
        return self.secondary_ai_base_url or self.openai_base_url or "https://openrouter.ai/api/v1"

    @property
    def effective_secondary_model(self) -> str:
        return self.secondary_ai_model or self.openai_model or "qwen/qwen3.8-27b:free"

    # Supabase & PostgreSQL Credentials
    supabase_url: Optional[str] = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_service_role_key: Optional[str] = Field(
        default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_anon_key: Optional[str] = Field(default=None, validation_alias="SUPABASE_ANON_KEY")
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    supabase_storage_bucket: str = Field(
        default="workspace-documents", validation_alias="SUPABASE_STORAGE_BUCKET"
    )

    # RAG Retrieval Quality & Thresholds
    rag_top_k: int = Field(default=5, validation_alias="RAG_TOP_K")
    # Note: the grounding threshold actually applied (tau = 0.50) is set in RetrievalService
    # (services/retrieval.py); this setting is kept for compatibility but is not read there.
    rag_similarity_threshold: float = Field(default=0.65, validation_alias="RAG_SIMILARITY_THRESHOLD")
    max_context_tokens: int = Field(default=3500, validation_alias="MAX_CONTEXT_TOKENS")
    conversation_history_limit: int = Field(
        default=8, validation_alias="CONVERSATION_HISTORY_LIMIT"
    )

    # Chunking Configuration
    chunk_size_chars: int = 1000
    chunk_overlap_chars: int = 150
    max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    model_config = SettingsConfigDict(
        env_file=([str(_ROOT_ENV), str(_BACKEND_ENV)] if (_ROOT_ENV.exists() or _BACKEND_ENV.exists()) else None),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("GEMINI_MODEL must be a non-empty string.")
        trimmed = v.strip()
        lower = trimmed.lower()
        if any(legacy in lower for legacy in ["3.6", "2.5", "1.5", "1.0", "pro-vision"]):
            raise ValueError(
                f"Obsolete or prohibited Gemini generation model configured: '{trimmed}'. "
                f"LumoraAI requires Gemini 3.8 Flash ('models/gemini-3.8-flash' or 'gemini-3.8-flash'). "
                f"Please update GEMINI_MODEL in your .env configuration."
            )
        normalized = trimmed.replace("models/", "")
        if normalized != "gemini-3.8-flash":
            raise ValueError(
                f"Unsupported Gemini generation model configured: '{trimmed}'. "
                f"LumoraAI strictly expects 'models/gemini-3.8-flash' or 'gemini-3.8-flash'. "
                f"Please check GEMINI_MODEL in your environment."
            )
        return trimmed

    @field_validator("gemini_embedding_model")
    @classmethod
    def validate_embedding_model(cls, v: str) -> str:
        if v != "models/gemini-embedding-001":
            raise ValueError(
                f"Invalid GEMINI_EMBEDDING_MODEL '{v}'. LumoraAI requires 'models/gemini-embedding-001'."
            )
        return v

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, v: int) -> int:
        if v != 768:
            raise ValueError(
                f"Invalid EMBEDDING_DIMENSIONS '{v}'. LumoraAI requires 768 dimensions."
            )
        return v

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v, info):
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        # Honour FRONTEND_ORIGIN so a deployed frontend can call the API directly
        frontend_origin = (info.data or {}).get("frontend_origin")
        if frontend_origin:
            origins.append(frontend_origin.rstrip("/"))
        if isinstance(v, list):
            origins.extend(v)
        return sorted(set(origins))


settings = Settings()
