from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Eum Backend", validation_alias="APP_NAME")
    app_env: str = Field(default="dev", validation_alias="APP_ENV")
    secret_key: str = Field(default="change-this-secret-key", validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=1440,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    database_url: str = Field(default="sqlite:///./eum.db", validation_alias="DATABASE_URL")
    cors_origins: list[str] | str = Field(default=["*"], validation_alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            if not value:
                return []
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
