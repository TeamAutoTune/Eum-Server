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
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    llm_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="LLM_BASE_URL")
    llm_timeout_seconds: float = Field(default=15.0, validation_alias="LLM_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=1, validation_alias="LLM_MAX_RETRIES")
    llm_summary_top_n: int = Field(default=3, validation_alias="LLM_SUMMARY_TOP_N")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    gemini_use_env_proxy: bool = Field(default=False, validation_alias="GEMINI_USE_ENV_PROXY")
    backfill_onboarding_on_startup: bool = Field(default=False, validation_alias="BACKFILL_ONBOARDING_ON_STARTUP")
    backfill_onboarding_user_id_prefix: str = Field(default="", validation_alias="BACKFILL_ONBOARDING_USER_ID_PREFIX")
    backfill_onboarding_team_name_prefix: str = Field(default="", validation_alias="BACKFILL_ONBOARDING_TEAM_NAME_PREFIX")
    backfill_matching_summaries_on_startup: bool = Field(default=False, validation_alias="BACKFILL_MATCHING_SUMMARIES_ON_STARTUP")
    backfill_matching_summaries_user_id_prefix: str = Field(default="", validation_alias="BACKFILL_MATCHING_SUMMARIES_USER_ID_PREFIX")
    backfill_matching_summaries_team_name_prefix: str = Field(default="", validation_alias="BACKFILL_MATCHING_SUMMARIES_TEAM_NAME_PREFIX")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value):
        if isinstance(value, str) and value.startswith("postgres://"):
            # Render may provide postgres:// URL; SQLAlchemy expects postgresql+driver://
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if isinstance(value, str) and value.startswith("sqlite:///./"):
            rel_path = value.replace("sqlite:///./", "", 1)
            base_dir = Path(__file__).resolve().parents[2]
            abs_path = (base_dir / rel_path).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{abs_path.as_posix()}"
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            if not value:
                return []
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()

