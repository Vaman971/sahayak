from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime config comes from env vars prefixed SAHAYAK_ (or a .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SAHAYAK_", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    log_json: bool = False

    sarvam_api_key: SecretStr | None = None
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://sahayak:sahayak@localhost:5432/sahayak"


@lru_cache
def get_settings() -> Settings:
    return Settings()
