# Nightwing AI SMS demo

**FastAPI** demo: console or Twilio inbound SMS (any language) → **Celery + Redis** extraction queue → **LLM JSON extraction** (local **Ollama** or **Google Gemini**) → routing (auto / review / spam) → **Nightwing Core** `POST /api/v1/partial-referral` (or local stub when disabled) → **SQLite** + Jinja2 console.

Production path: swap `QUEUE_BACKEND=sqs` and run workers on **AWS SQS** (Lambda/ECS) — same `complete_intake` entrypoint.

This repository is **demo-only**. See [docs/KNOWN_GAPS.md](docs/KNOWN_GAPS.md) for production scope.

## Requirements

- Python 3.12+
- A virtualenv with dependencies installed (`pip install -e .` from this directory). Example:

  ```bash
  source /home/stark/Nightwing_AI_flow/fastapi_ai_venv_3.12/bin/activate
  ```

- **Redis** ([install](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/)) for the extraction queue (`redis-server` on `127.0.0.1:6379`)
- **Ollama** ([install](https://ollama.com/)) if using local model — `ollama serve` + `make ollama-pull`
- **Gemini** — [AI Studio API key](https://aistudio.google.com/apikey) in `.env` if using cloud model

## Quick start

```bash
cd nightwing_ai_sms_demo
cp .env.example .env
# Edit .env once: set GOOGLE_API_KEY for Gemini; keep Ollama vars for local runs
source /path/to/your/py3.12/venv/bin/activate   # e.g. fastapi_ai_venv_3.12
pip install -e .
make ollama-pull   # first time only, when using Ollama
redis-server       # separate terminal (or system service)
make worker        # Celery extraction worker — separate terminal
make demo          # API — uses LLM_PROVIDER from .env
```

If you use [uv](https://docs.astral.sh/uv/), you can run `uv sync` instead of `pip install -e .`.

Open [http://127.0.0.1:8000/demo/console](http://127.0.0.1:8000/demo/console).

LLM calls log in the **worker** terminal (`make worker`), not the API. Set `LOG_LEVEL=DEBUG` in `.env` for full model output.

### Queue backends

| `QUEUE_BACKEND` | Broker | Worker |
|-----------------|--------|--------|
| `celery` (default) | Redis | `make worker` (Celery) |
| `sqs` | AWS SQS | Lambda/ECS → `sms_demo.workers.sqs_handler.lambda_handler` |

Demo uses **Celery + Redis**. For production, set `QUEUE_BACKEND=sqs`, `SQS_QUEUE_URL`, install `pip install -e ".[sqs]"`, and deploy a consumer that calls `complete_intake(intake_id)` (see `src/sms_demo/workers/sqs_handler.py`).

### Switch Ollama ↔ Gemini

Keep **both** provider blocks in `.env`; change only:

```env
LLM_PROVIDER=ollama   # local
# LLM_PROVIDER=gemini  # API (needs GOOGLE_API_KEY)
```

Or override for one run without editing `.env`:

```bash
make demo-ollama    # local
make demo-gemini    # API
make seed-ollama
make seed-gemini
```

SMS body may be in **any language** (or mixed). The model is instructed to parse multilingual text and return the same JSON field names; use **Try Spanish** on the console for a sample.

## Endpoints

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health` | Liveness |
| GET | `/demo/console` | Demo UI; optional `?sample=clean\|messy\|ambiguous` |
| POST | `/demo/simulate` | Form field `sms_body` → pipeline → redirect to console |
| POST | `/demo/reset` | Truncate demo tables |
| POST | `/stub/core/v1/referrals/partial` | Stub “Core” (same process) |
| POST | `/webhooks/twilio/sms` | **404** when `ENABLE_TWILIO_WEBHOOK=false`; when `true`, validates signature, enqueues extraction |

## Twilio + real phone (optional)

1. Set `ENABLE_TWILIO_WEBHOOK=true`, `TWILIO_AUTH_TOKEN`, and `PUBLIC_BASE_URL` to your public HTTPS origin (e.g. `https://abc123.ngrok-free.app`, no trailing slash).
2. Point your Twilio number’s **Messaging** webhook to `https://<host>/webhooks/twilio/sms` (HTTP POST).
3. Send an SMS from a real handset to the Twilio number. Intakes appear in the console with `source=twilio`.

There is **no outbound SMS** in this demo.

## Nightwing Core partial referral

When routing is **auto**, the worker maps extraction → `POST {CORE_API_BASE_URL}/api/v1/partial-referral` with header `x-access-token`.

In `.env`:

```env
CORE_API_BASE_URL=http://localhost:8080
CORE_API_ACCESS_TOKEN=<JWT from Core login>
# CORE_DEFAULT_CLIENT_ID=   # optional; leave unset for null clientId
CORE_PARTIAL_REFERRAL_ENABLED=true
```

Smoke-test without SMS:

```bash
python scripts/test_core_partial.py
```

End-to-end (SMS → LLM → Core partial-referral):

```bash
python scripts/test_e2e_sms.py
python scripts/test_e2e_sms.py "Referral for Jane Doe, phone +15551234567, needs MRI."
python scripts/test_e2e_sms.py --file samples/clean.txt
make test-e2e-sms
```

Set `CORE_PARTIAL_REFERRAL_ENABLED=false` (or leave token empty) to use the in-process stub instead.

## Makefile

- `make demo` — API server (uses `LLM_PROVIDER` from `.env`)
- `make worker` — Celery worker (Redis + one LLM job at a time)
- `make demo-ollama` / `make demo-gemini` — same server, force provider for this run
- `make ollama-pull` — pull default Ollama model
- `make seed` — samples using `.env` provider; `make seed-ollama` / `make seed-gemini` to force
- `make reset` — truncate demo tables
- `make test-twilio-webhook` — signed POST to `/webhooks/twilio/sms` (local + `PUBLIC_BASE_URL`; needs `make demo` running)
- `make test-e2e-sms` — full pipeline SMS → LLM → Core partial-referral (no server required)

## Talk track

See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).
