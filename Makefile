.PHONY: demo demo-ollama demo-gemini demo-github worker ollama-pull seed seed-ollama seed-gemini seed-github reset test-twilio-webhook test-e2e-sms

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

demo-github:
	LLM_PROVIDER=github $(UVICORN)

# Celery worker (requires Redis at REDIS_URL). One concurrent LLM job per worker.
CELERY = python -m celery -A sms_demo.celery_app:celery_app worker --loglevel=info --concurrency=1 -Q sms_extraction

worker:
	$(CELERY)

ollama-pull:
	ollama pull qwen2.5:7b

seed:
	python scripts/seed_samples.py

seed-ollama:
	LLM_PROVIDER=ollama python scripts/seed_samples.py

seed-gemini:
	LLM_PROVIDER=gemini python scripts/seed_samples.py

seed-github:
	LLM_PROVIDER=github python scripts/seed_samples.py

reset:
	python scripts/reset_db.py

# Signed POST to /webhooks/twilio/sms (local + PUBLIC_BASE_URL). Requires `make demo` running.
test-twilio-webhook:
	python scripts/test_twilio_webhook.py

# Full pipeline: SMS → LLM → Core partial-referral (uses .env; default sample: samples/clean.txt)
test-e2e-sms:
	python scripts/test_e2e_sms.py

test-twilio-webhook-all:
	python scripts/test_twilio_webhook.py --all --local-only
