import logging
import time

import httpx

from sms_demo.llm.base import LLMError, LLMProvider
from sms_demo.llm.error_format import log_llm_api_failure
from sms_demo.llm.json_parse import parse_llm_json

logger = logging.getLogger(__name__)

DEFAULT_CHAT_URL = "https://models.github.ai/inference/chat/completions"
DEFAULT_API_VERSION = "2026-03-10"


class GitHubModelsProvider(LLMProvider):
    """GitHub Models inference API (OpenAI-compatible chat completions)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_s: float = 180.0,
        max_tokens: int = 1024,
        chat_url: str = DEFAULT_CHAT_URL,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_s
        self._max_tokens = max_tokens
        self._url = chat_url.rstrip("/")
        self._api_version = api_version

    def extract_referral(
        self,
        sms_body: str,
        system_prompt: str,
        *,
        timeout_s: float | None = None,
    ) -> dict:
        request_timeout = timeout_s if timeout_s is not None else self._timeout
        user_message = (
            "Extract referral fields from this SMS only. "
            "Use names and numbers exactly as written in the message.\n\n"
            f"{sms_body}"
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": self._max_tokens,
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._api_key}",
            "X-GitHub-Api-Version": self._api_version,
            "Content-Type": "application/json",
        }

        preview = (sms_body or "").replace("\n", " ")[:120]
        logger.info(
            "GitHub Models request → POST %s model=%s timeout_s=%.0f sms_chars=%d preview=%r",
            self._url,
            self._model,
            request_timeout,
            len(sms_body or ""),
            preview,
        )
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=request_timeout) as client:
                r = client.post(self._url, json=payload, headers=headers)
                if r.status_code >= 400:
                    body_preview = (r.text or "")[:500]
                    err = LLMError(
                        f"GitHub Models HTTP {r.status_code}: {body_preview}",
                        http_code=r.status_code,
                    )
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    log_llm_api_failure(
                        logger,
                        provider="GitHub Models",
                        model=self._model,
                        elapsed_ms=elapsed_ms,
                        exc=err,
                    )
                    raise err
                data = r.json()
        except httpx.HTTPError as e:
            elapsed_ms = (time.perf_counter() - started) * 1000
            log_llm_api_failure(
                logger,
                provider="GitHub Models",
                model=self._model,
                elapsed_ms=elapsed_ms,
                exc=e,
            )
            raise LLMError(str(e)) from e

        elapsed_ms = (time.perf_counter() - started) * 1000
        usage = data.get("usage") if isinstance(data, dict) else None
        logger.info(
            "GitHub Models response ← %.0fms prompt_tokens=%s completion_tokens=%s",
            elapsed_ms,
            usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            usage.get("completion_tokens") if isinstance(usage, dict) else None,
        )

        try:
            choices = data["choices"]
            choice = choices[0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as e:
            logger.error("GitHub Models unexpected response shape: %r", data)
            raise LLMError(f"Unexpected GitHub Models response shape: {data!r}") from e

        if finish_reason == "length":
            logger.warning(
                "GitHub Models response truncated (finish_reason=length, max_tokens=%d)",
                self._max_tokens,
            )

        content = (content or "").strip()
        if not content:
            logger.error("GitHub Models empty response: %r", data)
            raise LLMError("GitHub Models returned empty content")

        logger.debug("GitHub Models raw content: %s", content[:2000])

        try:
            parsed = parse_llm_json(content)
            logger.info(
                "GitHub Models JSON parsed keys=%s mobile=%r",
                list(parsed.keys()),
                parsed.get("mobile"),
            )
            return parsed
        except LLMError:
            logger.error("GitHub Models invalid JSON (first 500 chars): %s", content[:500])
            raise
