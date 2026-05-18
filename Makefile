.PHONY: demo demo-ollama demo-gemini worker ollama-pull seed seed-ollama seed-gemini reset test-twilio-webhook

# Use an activated Python 3.12+ venv (e.g. source .../fastapi_ai_venv_3.12/bin/activate)
# so `python` resolves to the env that has dependencies installed (`pip install -e .`).

UVICORN = python -m uvicorn sms_demo.main:app --reload --host 0.0.0.0 --port 8000

# Uses LLM_PROVIDER from .env
demo:
	$(UVICORN)

# One-shot override (no .env edit): local vs cloud
demo-ollama:
	LLM_PROVIDER=ollama $(UVICORN)

demo-gemini:
	LLM_PROVIDER=gemini $(UVICORN)

# Celery worker (requires Redis at REDIS_URL). One concurrent LLM job per worker.
CELERY = python -m celery -A sms_demo.celery_app:celery_app worker --loglevel=info --concurrency=1 -Q sms_extraction

worker:
	$(CELERY)

ollama-pull:
	ollama pull llama3.1:8b-instruct-q4_K_M

seed:
	python scripts/seed_samples.py

seed-ollama:
	LLM_PROVIDER=ollama python scripts/seed_samples.py

seed-gemini:
	LLM_PROVIDER=gemini python scripts/seed_samples.py

reset:
	python scripts/reset_db.py

# Signed POST to /webhooks/twilio/sms (local + PUBLIC_BASE_URL). Requires `make demo` running.
test-twilio-webhook:
	python scripts/test_twilio_webhook.py

test-twilio-webhook-all:
	python scripts/test_twilio_webhook.py --all --local-only
