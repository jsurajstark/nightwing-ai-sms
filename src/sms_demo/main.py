from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from sms_demo.config import get_settings
from sms_demo.logging_config import configure_logging

configure_logging()

from sms_demo.db import get_engine
from sms_demo.models import Base
from sms_demo.routers import demo, health, stub_core, twilio_webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=get_engine())
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
