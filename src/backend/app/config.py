"""
Application configuration via pydantic-settings.
All settings can be overridden by environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg2://logicx:logicx@db:5432/wafer_yield"

    # Application
    environment: str = "production"  # production | test
    seed: int = 42

    # API
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
