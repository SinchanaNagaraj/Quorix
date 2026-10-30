"""Application settings, loaded from environment variables / backend/.env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Phase 1 variables (names match backend/.env.example)
    app_name: str = "Quorix"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    database_url: SecretStr | None = None
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.0-flash"

    # Phase 2: ingestion
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    qdrant_collection: str = "quorix_chunks"
    chunk_size: int = 500  # characters
    chunk_overlap: int = 80  # characters
    data_dir: Path = REPO_ROOT / "data"
    max_document_bytes: int = 10 * 1024 * 1024

    # Phase 3: Query Analysis & Source Selection
    weight_relevance: float = 0.35
    weight_authority: float = 0.25
    weight_freshness: float = 0.20
    weight_directness: float = 0.20
    selection_threshold: float = 0.55
    max_selected_sources: int = 3
    dataset_as_of: str = "2025-03-31T00:00:00Z"
    freshness_half_life_days: float = 180.0

    def require_database_url(self) -> str:
        if self.database_url is None:
            raise RuntimeError("DATABASE_URL is not configured (set it in backend/.env).")
        return self.database_url.get_secret_value()

    def require_qdrant(self) -> tuple[str, str | None]:
        if not self.qdrant_url:
            raise RuntimeError("QDRANT_URL is not configured (set it in backend/.env).")
        key = self.qdrant_api_key.get_secret_value() if self.qdrant_api_key else None
        return self.qdrant_url, key


@lru_cache
def get_settings() -> Settings:
    return Settings()
