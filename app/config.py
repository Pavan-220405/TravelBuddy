from pathlib import Path
from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings."""

    tavily_api_key: str
    groq_api_key: str
    aviationstack_api_key: str
    openweather_api_key: str = ""

    medium_model: str

    database_url: AnyUrl

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
