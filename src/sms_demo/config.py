from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from repo root (parent of src/) so Celery/worker cwd does not matter.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "ollama"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str | None = None

    google_api_key: str | None = None
    gemini_model: str | None = None

    # OpenRouter (https://openrouter.ai) — all model ids from .env only
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_fallback_models: str | None = None
    openrouter_base_url: str | None = None
    openrouter_http_referer: str | None = None
    openrouter_app_title: str | None = None
    openrouter_max_retries: int = 2
    openrouter_retry_base_s: float = 5.0

    # GitHub Models (https://docs.github.com/en/rest/models/inference)
    github_models_api_key: str | None = None
    github_models_base_url: str | None = None
    github_models_model: str | None = None
    github_models_org: str | None = None
    github_models_api_version: str | None = None
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
        "google_api_key",
        "openrouter_api_key",
        "openrouter_http_referer",
        "openrouter_app_title",
        "ollama_model",
        "gemini_model",
        "openrouter_model",
        "openrouter_fallback_models",
        "github_models_api_key",
        "github_models_base_url",
        "github_models_model",
        "github_models_org",
        "github_models_api_version",
        "github_models_fallback_models",
        mode="before",
    )
    @classmethod
    def _strip_optional_str(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip()
            if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
                s = s[1:-1].strip()
            if s == "":
                return None
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
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def openrouter_model_chain(self) -> list[str]:
        """Primary model + comma-separated fallbacks from .env (deduped, order preserved)."""
        primary = (self.openrouter_model or "").strip()
        if not primary:
            return []
        models: list[str] = []
        seen: set[str] = set()
        for raw in (primary, *(self.openrouter_fallback_models or "").split(",")):
            m = (raw or "").strip()
            if m and m not in seen:
                seen.add(m)
                models.append(m)
        return models

    @property
    def github_models_model_chain(self) -> list[str]:
        primary = (self.github_models_model or "").strip()
        if not primary:
            return []
        models: list[str] = []
        seen: set[str] = set()
        for raw in (primary, *(self.github_models_fallback_models or "").split(",")):
            m = (raw or "").strip()
            if m and m not in seen:
                seen.add(m)
                models.append(m)
        return models


_settings: Settings | None = None
_env_mtime: float | None = None


def reload_settings() -> Settings:
    """Force reload from .env (use before each extraction job)."""
    global _settings, _env_mtime
    _settings = None
    _env_mtime = None
    return get_settings()


def get_settings() -> Settings:
    """Load settings from .env; reload when the file changes (no server restart needed)."""
    global _settings, _env_mtime
    mtime = _ENV_FILE.stat().st_mtime if _ENV_FILE.is_file() else None
    if _settings is None or mtime != _env_mtime:
        _settings = Settings()
        _env_mtime = mtime
        try:
            from sms_demo.queue.factory import reset_queue_backend_cache

            reset_queue_backend_cache()
        except Exception:
            pass
    return _settings
