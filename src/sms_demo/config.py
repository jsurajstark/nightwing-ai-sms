from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "ollama"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b-instruct-q4_K_M"

    database_url: str = "sqlite:///./data/demo.db"

    enable_twilio_webhook: bool = False
    twilio_auth_token: str | None = None
    # Public HTTPS origin for Twilio signature URL (e.g. https://xxx.ngrok-free.app), no trailing slash.
    public_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
