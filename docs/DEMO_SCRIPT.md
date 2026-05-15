# Demo script (talk track)

Use this as a loose script for a 5–10 minute walkthrough. Adjust timing for your audience.

## Setup (before the room)

1. `cp .env.example .env`, `uv sync`, Ollama running, `make ollama-pull` once.
2. `make demo` — confirm `GET /health` returns `{"status":"ok"}`.
3. Open `/demo/console` in the browser.

## Console path (default, no telephony)

1. **Reset** — show empty state (optional).
2. **Try clean** — explain that samples are plain text files under `samples/`.
3. **Submit** — watch the 2s refresh; point out columns: raw → extraction JSON → routing badge → stub Core JSON when route is `auto`.
4. **Try messy** — show `review` only when first/last name are missing; phone and service are optional.
5. **Try ambiguous** — prompt tuning changes outcomes; this is expected in a demo model.

## Optional: real phone (Twilio)

1. Set `ENABLE_TWILIO_WEBHOOK=true`, `TWILIO_AUTH_TOKEN`, `PUBLIC_BASE_URL` (ngrok HTTPS origin, no trailing slash).
2. Start tunnel; set Twilio number Messaging webhook to `https://<public>/webhooks/twilio/sms`.
3. Send **30 seconds**: SMS from your handset with **synthetic** patient content only; refresh console — row shows `source=twilio` and `MessageSid` if present.
4. Mention **403** on bad signature: no LLM call (security story).

## Close (one slide)

Read the first bullet from `KNOWN_GAPS.md`: this stack is demo-only; production re-adds redaction, guardrails, signing, audit, real Core, MySQL, idempotency, observability, etc.

## Q&A prompts

- **Why SQLite?** Fast demo, zero ops.
- **Why Ollama?** No API spend; same adapter pattern swaps to Bedrock/Anthropic later.
- **Outbound SMS?** Out of scope; confirmation flows live in production backlog (`KNOWN_GAPS.md`).

## Extraction prompt tuning (checklist)

- [ ] Clean sample routes `auto` with plausible `missing_fields` from stub.
- [ ] Messy sample lands in `review` with readable `reason`.
- [ ] Ambiguous sample does not silently drop JSON keys (`format: json` + prompt).
- [ ] Empty submit is `spam` without LLM if you short-circuit later (currently still calls LLM — optional improvement).
