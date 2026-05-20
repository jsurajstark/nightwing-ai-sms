import json
import logging
import time

import httpx

from sms_demo.llm.base import LLMError, LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str, timeout_s: float = 120.0) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout_s

    def extract_referral(
        self,
        sms_body: str,
        system_prompt: str,
        *,
        timeout_s: float | None = None,
    ) -> dict:
        request_timeout = timeout_s if timeout_s is not None else self._timeout
        url = f"{self._host}/api/chat"
        payload = {
            "model": self._model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": sms_body},
            ],
        }
        preview = (sms_body or "").replace("\n", " ")[:120]
        logger.info(
            "Ollama request → POST %s model=%s timeout_s=%.0f sms_chars=%d preview=%r",
            url,
            self._model,
            request_timeout,
            len(sms_body or ""),
            preview,
        )
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=request_timeout) as client:
                r = client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - started) * 1000
            if e.response.status_code == 404:
                detail = (
                    f"Ollama model {self._model!r} not found (HTTP 404). "
                    f"Run: ollama pull {self._model} — or set OLLAMA_MODEL to an installed model "
                    f"(see: ollama list). Or set LLM_PROVIDER=openrouter in .env."
                )
                try:
                    body = e.response.json()
                    if isinstance(body, dict) and body.get("error"):
                        detail = f"{detail} Ollama says: {body['error']}"
                except Exception:
                    pass
                logger.error("Ollama model missing after %.0fms", elapsed_ms)
                raise LLMError(detail) from e
            logger.error("Ollama request failed after %.0fms: %s", elapsed_ms, e)
            raise LLMError(str(e)) from e
        except httpx.HTTPError as e:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.error("Ollama request failed after %.0fms: %s", elapsed_ms, e)
            raise LLMError(str(e)) from e

        elapsed_ms = (time.perf_counter() - started) * 1000
        eval_count = data.get("eval_count")
        prompt_eval_count = data.get("prompt_eval_count")
        logger.info(
            "Ollama response ← %.0fms eval_count=%s prompt_eval_count=%s",
            elapsed_ms,
            eval_count,
            prompt_eval_count,
        )

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as e:
            logger.error("Ollama unexpected response shape: %r", data)
            raise LLMError(f"Unexpected Ollama response shape: {data!r}") from e

        logger.debug("Ollama raw content: %s", content[:2000])

        try:
            parsed = json.loads(content)
            logger.info(
                "Ollama JSON parsed keys=%s patient_phone=%r",
                list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__,
                parsed.get("patient_phone") if isinstance(parsed, dict) else None,
            )
            return parsed
        except json.JSONDecodeError as e:
            logger.error("Ollama invalid JSON (first 500 chars): %s", content[:500])
            raise LLMError(f"Model did not return valid JSON: {content[:500]}") from e
