"""
SigmaFlow Configuration
=======================
Centralized settings using Pydantic Settings (v2).
Loads from .env file and environment variables.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_name: str = "SigmaFlow"
    app_version: str = "0.2.0"
    environment: str = Field(default="development", description="development, staging, production")
    debug: bool = False
    log_level: str = "INFO"
    log_format: str = "json"  # json or console

    # ── Database ──────────────────────────────────────────────────────────────
    # Sync URL for SQLAlchemy sync engine (Alembic, Celery, CLI)
    # Format: postgresql+psycopg2://user:pass@host:port/dbname
    # Default uses a local data directory (not versioned) to avoid permission issues
    database_url_sync: str = Field(
        default="sqlite:///./data/sigmaflow.db",
        description="Synchronous database URL",
    )
    # Async URL for FastAPI (asyncpg driver for PostgreSQL, aiosqlite for SQLite)
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    database_url_async: str = Field(
        default="sqlite+aiosqlite:///./data/sigmaflow.db",
        description="Asynchronous database URL",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery broker and result backend",
    )
    celery_broker_url: Optional[str] = None  # defaults to redis_url
    celery_result_backend: Optional[str] = None  # defaults to redis_url
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: list[str] = ["json"]
    celery_timezone: str = "America/Sao_Paulo"
    celery_enable_utc: bool = True
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 3600  # 1 hour
    celery_task_soft_time_limit: int = 3300  # 55 min
    celery_worker_prefetch_multiplier: int = 4
    celery_worker_max_tasks_per_child: int = 100

    # ── Security / Auth ───────────────────────────────────────────────────────
    secret_key: str = Field(
        default="change-me-in-production-use-a-long-random-string",
        description="Secret key for JWT tokens",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    bcrypt_rounds: int = 12

    # ── File Storage ──────────────────────────────────────────────────────────
    storage_type: str = Field(default="local", description="local, s3, minio")
    storage_local_root: str = Field(default="./storage", description="Local storage root path")
    # S3/MinIO settings (if storage_type != local)
    s3_endpoint_url: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"

    # ── Input/Output Paths (legacy compatibility) ─────────────────────────────
    input_dir: str = "input/datasets"
    output_dir: str = "output"

    # ── Dashboard / Report ────────────────────────────────────────────────────
    dashboard_enabled: bool = True
    report_compile_pdf: bool = True
    report_organization: str = "SigmaFlow"

    # ── External Integrations ─────────────────────────────────────────────────
    # Webhook URLs for notifications
    webhook_teams: Optional[str] = None
    webhook_slack: Optional[str] = None
    webhook_generic: Optional[str] = None

    # Email (SMTP)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_tls: bool = True
    email_from: Optional[str] = None

    # ── LLM (for enhanced insights) ───────────────────────────────────────────
    llm_provider: str = Field(default="none", description="none, groq, openrouter, openai, ollama")
    llm_api_key: Optional[str] = None
    llm_model: str = "llama-3.1-70b-versatile"
    llm_base_url: Optional[str] = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # ── Scheduler ─────────────────────────────────────────────────────────────
    scheduler_enabled: bool = True
    scheduler_timezone: str = "America/Sao_Paulo"

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_cors_origins: list[str] = ["*"]

    # ── Default Values ────────────────────────────────────────────────────────
    default_project_code: str = "SF"
    default_run_config: dict = Field(default_factory=dict)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()