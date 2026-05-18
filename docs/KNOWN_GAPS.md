# Known gaps (demo vs production)

This document is the **scope contract** between engineering and stakeholders. Anything listed here is **explicitly not promised** by the `nightwing_ai_sms_demo` repository unless a future milestone says otherwise.

## Security and compliance

- No Presidio / PII redaction; no HIPAA-oriented controls.
- No Guardrails or policy engines on model I/O.
- No MRN recognizer or enterprise identity linking.
- Twilio validation is **demo-grade**: correct `PUBLIC_BASE_URL` must match the webhook URL Twilio calls (including path, HTTPS, and trailing slash behavior).

## Platform and data

- SQLite only; no Alembic migrations; no MySQL compatibility guarantees.
- Demo queue is **Celery + Redis** (single-worker LLM serialization); production **SQS** backend is wired but not deployed here.
- No idempotency keys for duplicate Twilio `MessageSid` retries.
- Logs and DB may retain **real phone numbers** if you test with Twilio—use synthetic content and controlled numbers.

## Core and integrations

- Stub Core only (`REF-*` ids); no mTLS to real MyNightwing Core.
- No outbound Twilio (no confirmation SMS to patient or referrer).
- No staff UI, worklists, or escalation queues beyond routing badges.

## Multi-tenant and operations

- No per-tenant webhook signing secrets.
- No observability stack (metrics/tracing/log shipping) wired in.
- No CI/CD or container packaging in this demo repo baseline.

## Model quality

- No offline eval gates, golden sets, or automated regression on extraction JSON.
- Routing heuristics are string/rule based; not a substitute for clinical triage.

## Internationalization

- Demo extraction prompt accepts **any language** via the LLM; routing heuristics remain language-agnostic (field presence only).
- No per-locale models, translated staff UI, or locale-specific eval golden sets.

---

When scoping a production phase, treat each section above as a candidate **requirement** to design against—not as implied deliverables of this demo.
