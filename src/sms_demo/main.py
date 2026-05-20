import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from sms_demo.config import _ENV_FILE, get_settings
from sms_demo.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

from sms_demo.db import init_database
from sms_demo.routers import demo, health, stub_core, twilio_webhook


def _llm_model_label(settings) -> str:
    p = (settings.llm_provider or "").lower()
    if p == "openrouter":
        chain = settings.openrouter_model_chain
        return chain[0] if chain else (settings.openrouter_model or "?")
    if p == "github":
        chain = settings.github_models_model_chain
        return chain[0] if chain else (settings.github_models_model or "?")
    if p == "gemini":
        return settings.gemini_model or "?"
    if p == "ollama":
        return settings.ollama_model or "?"
    return settings.llm_provider or "?"


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os

    settings = get_settings()
    env_override = os.environ.get("LLM_PROVIDER")
    if env_override and env_override.strip().lower() != settings.llm_provider.lower():
        logger.warning(
            "Shell LLM_PROVIDER=%r overrides .env (%r). Unset with: unset LLM_PROVIDER",
            env_override,
            settings.llm_provider,
        )
    if settings.queue_backend == "inline":
        logger.info(
            "QUEUE_BACKEND=inline — stop any Celery worker (make worker) to avoid duplicate extractions"
        )
    elif settings.queue_backend == "celery":
        logger.info(
            "QUEUE_BACKEND=celery — ensure Redis is up and run `make worker` in a second terminal"
        )
    logger.info(
        "LLM provider=%s model=%s queue=%s env_file=%s",
        settings.llm_provider,
        _llm_model_label(settings),
        settings.queue_backend,
        _ENV_FILE,
    )
    init_database()
    yield


app = FastAPI(title="Nightwing AI SMS Demo", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def root():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/demo/console")


app.include_router(health.router)
app.include_router(demo.router)
app.include_router(stub_core.router)

_settings = get_settings()
if _settings.enable_twilio_webhook:
    app.include_router(twilio_webhook.router)
else:

    @app.post("/webhooks/twilio/sms", include_in_schema=False)
    async def twilio_webhook_disabled():
        raise HTTPException(status_code=404, detail="Twilio webhook disabled")
