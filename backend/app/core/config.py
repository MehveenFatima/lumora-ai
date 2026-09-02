from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # Server & Environment
    app_name: str = "LumoraAI Backend"
    environment: str = Field(default="development", env="ENVIRONMENT")
    port: int = Field(default=8000, env="PORT")
    frontend_origin: str = Field(default="http://localhost:3000", env="FRONTEND_ORIGIN")
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Google Gemini AI Configuration
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", env="GEMINI_MODEL")
    gemini_embedding_model: str = Field(
        default="models/gemini-embedding-001", env="GEMINI_EMBEDDING_MODEL"
    )
    embedding_dimensions: int = Field(default=768, env="EMBEDDING_DIMENSIONS")

    # Supabase & PostgreSQL Credentials
    supabase_url: Optional[str] = Field(default=None, env="SUPABASE_URL")
    supabase_service_role_key: Optional[str] = Field(
        default=None, env="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_anon_key: Optional[str] = Field(default=None, env="SUPABASE_ANON_KEY")
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    supabase_storage_bucket: str = Field(
        default="workspace-documents", env="SUPABASE_STORAGE_BUCKET"
    )

    # RAG Retrieval Quality & Thresholds
    rag_top_k: int = Field(default=5, env="RAG_TOP_K")
    rag_similarity_threshold: float = Field(default=0.65, env="RAG_SIMILARITY_THRESHOLD")
    max_context_tokens: int = Field(default=3500, env="MAX_CONTEXT_TOKENS")
    conversation_history_limit: int = Field(
        default=8, env="CONVERSATION_HISTORY_LIMIT"
    )

    # Chunking Configuration
    chunk_size_chars: int = 1000
    chunk_overlap_chars: int = 150
    max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    def assemble_cors_origins(cls, v, values):
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(v, list):
            return list(set(v + origins))
        return origins


settings = Settings()
