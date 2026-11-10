"""ChangeScope Configuration Module."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHANGESCOPE_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENVIRONMENT: Literal["local", "test", "staging", "production"] = "local"
    APP_NAME: str = "ChangeScope"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Canonical Relational Database (PostgreSQL 17, fallback to SQLite for local tests)
    DATABASE_URL: str = "sqlite+aiosqlite:///./changescope.db"
    DB_ECHO: bool = False

    # Neo4j Graph Projection Database
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "changescope_password"
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MOCK_MODE: bool = False

    # Redis Task Queue & Trace Buffer
    REDIS_URL: str = "redis://localhost:6379/0"

    # Authentication & Security
    JWT_SECRET: str = "changescope_dev_jwt_secret_key_change_in_production_32b"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    GITHUB_WEBHOOK_SECRET: str = "changescope_webhook_secret_dev"

    # Engine Constraints & SLAs
    MAX_BLAST_RADIUS_DEPTH: int = 5
    SCAN_TIMEOUT_SECONDS: int = 60
    DEFAULT_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"


settings = Settings()
