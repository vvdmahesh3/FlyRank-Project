"""Application settings loaded from environment variables.

All configuration flows through this single point so secrets are never
hardcoded and the $0-stack constraint is visible at a glance.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──
    database_url: str = (
        "postgresql+psycopg2://flyrank:flyrank_dev@localhost:5432/flyrank"
    )

    # ── Security ──
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    # ── CORS (dashboard API) ──
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ── Rate Limiting ──
    rate_limit_per_minute: int = 60
    rate_limit_public_per_minute: int = 10

    # ── Geo Enrichment ──
    geo_provider_primary: str = "ip-api"
    geo_provider_fallback: str = "ipinfo"
    geo_fallback_token: str = ""

    # ── Email ──
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@flyrank.local"

    # ── Webhook ──
    webhook_timeout_seconds: int = 5

    # ── Environment ──
    environment: str = "development"

    @field_validator("cors_origins")
    @classmethod
    def _strip_cors(cls, v: str) -> str:
        return ",".join(
            origin.strip() for origin in v.split(",") if origin.strip()
        )

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
