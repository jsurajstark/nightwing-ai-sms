import logging
import time

from google import genai
from google.genai import types

from sms_demo.llm.base import LLMError, LLMProvider
from sms_demo.llm.error_format import llm_error_from_exception, log_llm_api_failure
from sms_demo.llm.json_parse import parse_llm_json

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, timeout_s: float = 180.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_s

    def _client_for_timeout(self, timeout_s: float) -> genai.Client:
        return genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )

    def extract_referral(
        self,
        sms_body: str,
        system_prompt: str,
        *,
        timeout_s: float | None = None,
    ) -> dict:
        request_timeout = timeout_s if timeout_s is not None else self._timeout
        preview = (sms_body or "").replace("\n", " ")[:120]
        logger.info(
            "Gemini request → model=%s timeout_s=%.0f sms_chars=%d preview=%r",
            self._model,
            request_timeout,
            len(sms_body or ""),
            preview,
        )
        started = time.perf_counter()
        client = self._client_for_timeout(request_timeout)
        try:
            user_message = (
                "Extract referral fields from this SMS only. "
                "Use names and numbers exactly as written in the message.\n\n"
                f"{sms_body}"
            )
            response = client.models.generate_content(
                model=self._model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                ),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - started) * 1000
            log_llm_api_failure(
                logger,
                provider="Gemini",
                model=self._model,
                elapsed_ms=elapsed_ms,
                exc=e,
            )
            raise llm_error_from_exception(e) from e

        elapsed_ms = (time.perf_counter() - started) * 1000
        usage = getattr(response, "usage_metadata", None)
        logger.info(
            "Gemini response ← %.0fms prompt_tokens=%s candidates_tokens=%s",
            elapsed_ms,
            getattr(usage, "prompt_token_count", None) if usage else None,
            getattr(usage, "candidates_token_count", None) if usage else None,
        )

        content = (getattr(response, "text", None) or "").strip()
        if not content:
            logger.error("Gemini empty response: %r", response)
            raise LLMError("Gemini returned empty content")

        logger.debug("Gemini raw content: %s", content[:2000])

        parsed = parse_llm_json(content)
        logger.info(
            "Gemini JSON parsed keys=%s mobile=%r",
            list(parsed.keys()),
            parsed.get("mobile"),
        )
        return parsed
