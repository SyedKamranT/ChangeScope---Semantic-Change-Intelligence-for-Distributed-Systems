"""Environment configuration validation using Pydantic Settings."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Production-grade environment configuration schema with strict validation."""

    model_config = SettingsConfigDict(
        env_prefix="CHANGESCOPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Settings
    ENVIRONMENT: Literal["local", "test", "staging", "production"] = "local"
    APP_NAME: str = "ChangeScope"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Canonical Relational Database (PostgreSQL 17)
    DATABASE_URL: str = "sqlite+aiosqlite:///./changescope.db"
    DB_POOL_SIZE: int = Field(default=20, ge=5, le=100)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=50)
    DB_ECHO: bool = False

    # Redis Cache & Task Queue
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SOCKET_TIMEOUT: float = Field(default=5.0, ge=1.0)

    # Neo4j Graph Projection Database
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "changescope_password"
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MOCK_MODE: bool = False
    NEO4J_CONNECTION_TIMEOUT: float = Field(default=10.0, ge=1.0)

    # Security & Authentication (OIDC & JWT)
    JWT_SECRET: str = "changescope_production_secret_key_at_least_32_bytes_long_1234"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(default=60 * 24, ge=15)
    OIDC_ISSUER_URL: str | None = None
    OIDC_AUDIENCE: str | None = None
    GITHUB_WEBHOOK_SECRET: str = "changescope_webhook_secret_dev"

    # Default Tenant for single-tenant local/dev environments
    DEFAULT_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"

    # Execution SLA Boundaries
    MAX_BLAST_RADIUS_DEPTH: int = Field(default=5, ge=1, le=10)
    SCAN_TIMEOUT_SECONDS: int = Field(default=60, ge=10, le=300)

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long for security.")
        return v


settings = AppSettings()
