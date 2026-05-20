import logging
import time

import httpx

from sms_demo.llm.base import LLMError, LLMProvider
from sms_demo.llm.json_parse import parse_llm_json

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

        parsed = parse_llm_json(content)
        logger.info(
            "Ollama JSON parsed keys=%s patient_phone=%r",
            list(parsed.keys()),
            parsed.get("patient_phone"),
        )
        return parsed
