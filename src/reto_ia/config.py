from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"

    database_url: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str | None = None
    llm_model_primary: str | None = None
    llm_model_fallback: str = "openrouter/free"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
