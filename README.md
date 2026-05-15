# Nightwing AI SMS demo

Single-process **FastAPI** demo: console or Twilio inbound SMS text (any language) → **Ollama** JSON extraction → routing (auto / review / spam) → in-process **stub Core** partial referral → **SQLite** + Jinja2 console (2s meta refresh).

This repository is **demo-only**. See [docs/KNOWN_GAPS.md](docs/KNOWN_GAPS.md) for production scope.

## Requirements

- Python 3.12+
- A virtualenv with dependencies installed (`pip install -e .` from this directory). Example:

  ```bash
  source /home/stark/Nightwing_AI_flow/fastapi_ai_venv_3.12/bin/activate
  ```

- [Ollama](https://ollama.com/) running locally (default `http://127.0.0.1:11434`)

## Quick start

```bash
cd nightwing_ai_sms_demo
cp .env.example .env
source /path/to/your/py3.12/venv/bin/activate   # e.g. fastapi_ai_venv_3.12
pip install -e .
make ollama-pull   # first time only
make demo
```

If you use [uv](https://docs.astral.sh/uv/), you can run `uv sync` instead of `pip install -e .`, and point `Makefile` `demo`/`seed`/`reset` targets at `uv run` if you prefer.

Open [http://127.0.0.1:8000/demo/console](http://127.0.0.1:8000/demo/console).

Ollama calls log to the **same terminal** as `make demo` (`INFO` by default). Set `LOG_LEVEL=DEBUG` in `.env` for full model output.

SMS body may be in **any language** (or mixed). The model is instructed to parse multilingual text and return the same JSON field names; use **Try Spanish** on the console for a sample.

## Endpoints

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health` | Liveness |
| GET | `/demo/console` | Demo UI; optional `?sample=clean\|messy\|ambiguous` |
| POST | `/demo/simulate` | Form field `sms_body` → pipeline → redirect to console |
| POST | `/demo/reset` | Truncate demo tables |
| POST | `/stub/core/v1/referrals/partial` | Stub “Core” (same process) |
| POST | `/webhooks/twilio/sms` | **404** when `ENABLE_TWILIO_WEBHOOK=false`; when `true`, validates `X-Twilio-Signature` then runs pipeline |

## Twilio + real phone (optional)

1. Set `ENABLE_TWILIO_WEBHOOK=true`, `TWILIO_AUTH_TOKEN`, and `PUBLIC_BASE_URL` to your public HTTPS origin (e.g. `https://abc123.ngrok-free.app`, no trailing slash).
2. Point your Twilio number’s **Messaging** webhook to `https://<host>/webhooks/twilio/sms` (HTTP POST).
3. Send an SMS from a real handset to the Twilio number. Intakes appear in the console with `source=twilio`.

There is **no outbound SMS** in this demo.

## Makefile

- `make demo` — dev server
- `make ollama-pull` — pull default model
- `make seed` / `make reset` — sample data helpers

## Talk track

See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).
