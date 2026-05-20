from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "ollama"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"

    google_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

    # GitHub Models (LLM_PROVIDER=github)
    github_models_api_key: str | None = None
    github_models_base_url: str = "https://models.github.ai"
    github_models_model: str = "meta/meta-llama-3.1-8b-instruct"
    github_models_api_version: str = "2026-03-10"
    github_models_org: str | None = None
    github_models_fallback_models: str | None = None
    github_models_max_retries: int = 2
    github_models_retry_base_s: float = 5.0

    llm_timeout_s: float = 180.0
    llm_max_retries: int = 2
    llm_timeout_increment_s: float = 30.0

    database_url: str = "sqlite:///./data/demo.db"

    # Queue: celery + Redis (demo/MVP) | sqs (production — Lambda/ECS worker)
    queue_backend: str = "celery"
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_queue_name: str = "sms_extraction"

    # Production SQS (QUEUE_BACKEND=sqs)
    aws_region: str = "us-east-1"
    sqs_queue_url: str | None = None

    enable_twilio_webhook: bool = False
    twilio_auth_token: str | None = None
    # Public HTTPS origin for Twilio signature URL (e.g. https://xxx.ngrok-free.app), no trailing slash.
    public_base_url: str | None = None

    # Nightwing Core partial-referral (POST /api/v1/partial-referral)
    core_api_base_url: str = "http://localhost:8080"
    core_api_access_token: str | None = None
    core_default_client_id: int | None = None
    core_partial_referral_enabled: bool = True
    core_api_timeout_s: float = 30.0

    @field_validator(
        "twilio_auth_token",
        "public_base_url",
        "celery_broker_url",
        "celery_result_backend",
        "sqs_queue_url",
        "core_api_access_token",
        "github_models_org",
        "github_models_fallback_models",
        mode="before",
    )
    @classmethod
    def _strip_optional_str(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
                s = s[1:-1].strip()
            return s
        return v

    @field_validator("core_default_client_id", mode="before")
    @classmethod
    def _optional_client_id(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("", "null", "none"):
                return None
            return int(s) if s.isdigit() else v
        return v

    @property
    def github_models_model_chain(self) -> list[str]:
        fallbacks: list[str] = []
        if self.github_models_fallback_models:
            fallbacks = [
                m.strip()
                for m in self.github_models_fallback_models.split(",")
                if m.strip()
            ]
        seen: set[str] = set()
        out: list[str] = []
        for raw in [self.github_models_model, *fallbacks]:
            m = (raw or "").strip()
            if not m or m in seen:
                continue
            seen.add(m)
            out.append(m)
        return out

    @property
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
