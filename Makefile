.PHONY: demo demo-ollama demo-gemini demo-openrouter demo-github worker ollama-pull migrate seed seed-ollama seed-gemini seed-openrouter reset purge-queue test-twilio-webhook test-e2e-sms test-e2e-referral test-queue

# Prefer ./venv/bin/python when present; else python3 (Debian/Ubuntu often has no `python`).
PYTHON := $(if $(wildcard venv/bin/python),./venv/bin/python,python3)

UVICORN = $(PYTHON) -m uvicorn sms_demo.main:app --reload --host 0.0.0.0 --port 8000

# Uses LLM_PROVIDER from .env
demo:
	$(UVICORN)

# One-shot override (no .env edit): local vs cloud
demo-ollama:
	LLM_PROVIDER=ollama $(UVICORN)

demo-gemini:
	LLM_PROVIDER=gemini $(UVICORN)

demo-openrouter:
	LLM_PROVIDER=openrouter $(UVICORN)

demo-github:
	LLM_PROVIDER=github $(UVICORN)

# Celery worker (requires Redis at REDIS_URL). One concurrent LLM job per worker.
CELERY = $(PYTHON) -m celery -A sms_demo.celery_app:celery_app worker --loglevel=info --concurrency=1 -Q sms_extraction

worker:
	$(CELERY)

ollama-pull:
	ollama pull llama3.1:8b-instruct-q4_K_M

seed:
	$(PYTHON) scripts/seed_samples.py

seed-ollama:
	LLM_PROVIDER=ollama $(PYTHON) scripts/seed_samples.py

seed-gemini:
	LLM_PROVIDER=gemini $(PYTHON) scripts/seed_samples.py

seed-openrouter:
	LLM_PROVIDER=openrouter $(PYTHON) scripts/seed_samples.py

migrate:
	$(PYTHON) scripts/migrate_db.py

reset:
	$(PYTHON) scripts/reset_db.py

# Flush pending Celery extraction tasks from Redis (stale backlog after many submits)
purge-queue:
	$(PYTHON) -m celery -A sms_demo.celery_app:celery_app purge -f -Q sms_extraction

# Signed POST to /webhooks/twilio/sms (local + PUBLIC_BASE_URL). Requires `make demo` running.
test-twilio-webhook:
	$(PYTHON) scripts/test_twilio_webhook.py

# Full pipeline: SMS → LLM → Core partial-referral (uses .env; default sample: samples/clean.txt)
test-e2e-sms:
	$(PYTHON) scripts/test_e2e_sms.py

# GitHub/OpenRouter E2E via synchronous run_intake (samples/clean.txt)
test-e2e-referral:
	$(PYTHON) scripts/test_e2e_referral.py

# Async queue path (create_intake + schedule_intake_extraction; QUEUE_BACKEND=inline)
test-queue:
	$(PYTHON) scripts/test_queue.py

test-twilio-webhook-all:
	$(PYTHON) scripts/test_twilio_webhook.py --all --local-only
