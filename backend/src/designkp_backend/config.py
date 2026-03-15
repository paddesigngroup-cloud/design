from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def normalize_postgres_url(raw_url: str, *, driver: str = "asyncpg") -> str:
    if not raw_url:
        raise ValueError("DATABASE_URL is required.")

    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return f"postgresql+{driver}://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"),),
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(alias="DATABASE_URL")
    alembic_database_url_override: str | None = Field(default=None, alias="ALEMBIC_DATABASE_URL")
    db_echo: bool = Field(default=False, alias="DB_ECHO")
    db_pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=40, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")

    @property
    def sqlalchemy_database_url(self) -> str:
        return normalize_postgres_url(self.database_url)

    @property
    def alembic_database_url_normalized(self) -> str:
        return normalize_postgres_url(self.alembic_database_url_override or self.database_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
