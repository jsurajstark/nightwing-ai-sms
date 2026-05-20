"""OpenRouter chat-completions adapter (OpenAI-compatible API)."""

from __future__ import annotations

import json
import logging
import time

import httpx

from sms_demo.llm.base import LLMError, LLMProvider

logger = logging.getLogger(__name__)

_FALLBACK_STATUS = frozenset({404, 429, 500, 502, 503, 504})


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        fallback_models: list[str] | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_s: float = 180.0,
        max_retries: int = 2,
        retry_base_s: float = 5.0,
        http_referer: str | None = None,
        app_title: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._max_retries = max(0, max_retries)
        self._retry_base_s = max(0.0, retry_base_s)
        self._http_referer = http_referer
        self._app_title = app_title
        self._model_chain = _dedupe_models([model, *(fallback_models or [])])
        self._primary_model = self._model_chain[0] if self._model_chain else model
        self.last_model_used: str | None = None

    @property
    def model(self) -> str:
        return self._primary_model

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._http_referer:
            headers["HTTP-Referer"] = self._http_referer
        if self._app_title:
            headers["X-Title"] = self._app_title
        return headers

    def _chat_completion(self, url: str, payload: dict, request_timeout: float) -> dict:
        with httpx.Client(timeout=request_timeout) as client:
            response = client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise LLMError(f"Unexpected OpenRouter response type: {type(data).__name__}")
        return data

    def _sleep_before_retry(
        self, attempt: int, *, retry_after_header: str | None = None
    ) -> None:
        if retry_after_header:
            try:
                delay = float(retry_after_header.strip())
            except ValueError:
                delay = self._retry_base_s * (2**attempt)
        else:
            delay = self._retry_base_s * (2**attempt)
        delay = min(max(delay, 1.0), 120.0)
        logger.warning("OpenRouter backing off %.1fs before retry", delay)
        time.sleep(delay)

    def _extract_with_model(
        self,
        model: str,
        url: str,
        user_message: str,
        system_prompt: str,
        request_timeout: float,
    ) -> dict:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        try:
            data = self._chat_completion(url, payload, request_timeout)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400 and "response_format" in payload:
                logger.warning(
                    "OpenRouter model=%s rejected response_format; retrying without JSON mode",
                    model,
                )
                fallback_payload = {k: v for k, v in payload.items() if k != "response_format"}
                data = self._chat_completion(url, fallback_payload, request_timeout)
            else:
                raise
        return self._parse_completion(data, model)

    def _parse_completion(self, data: dict, model: str) -> dict:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            logger.error("OpenRouter unexpected response shape model=%s: %r", model, data)
            raise LLMError(f"Unexpected OpenRouter response shape: {data!r}") from e

        content = (content or "").strip()
        if not content:
            raise LLMError(f"OpenRouter model {model!r} returned empty content")

        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise LLMError(f"Expected JSON object, got {type(parsed).__name__}")
            self.last_model_used = model
            return parsed
        except json.JSONDecodeError as e:
            raise LLMError(f"Model did not return valid JSON: {content[:500]}") from e

    def extract_referral(
        self,
        sms_body: str,
        system_prompt: str,
        *,
        timeout_s: float | None = None,
    ) -> dict:
        request_timeout = timeout_s if timeout_s is not None else self._timeout
        url = f"{self._base_url}/chat/completions"
        user_message = (
            "Extract referral fields from this SMS only. "
            "Use names and numbers exactly as written in the message.\n\n"
            f"{sms_body}"
        )
        preview = (sms_body or "").replace("\n", " ")[:120]
        logger.info(
            "OpenRouter chain → url=%s models=%s timeout_s=%.0f preview=%r",
            url,
            self._model_chain,
            request_timeout,
            preview,
        )

        errors: list[str] = []
        started = time.perf_counter()

        for model_index, model in enumerate(self._model_chain):
            if model_index > 0:
                logger.warning(
                    "OpenRouter falling back to model=%s (%s/%s)",
                    model,
                    model_index + 1,
                    len(self._model_chain),
                )

            for attempt in range(self._max_retries + 1):
                if attempt > 0:
                    logger.warning(
                        "OpenRouter retry model=%s attempt %s/%s",
                        model,
                        attempt + 1,
                        self._max_retries + 1,
                    )
                try:
                    parsed = self._extract_with_model(
                        model, url, user_message, system_prompt, request_timeout
                    )
                    self.last_model_used = model
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    logger.info("OpenRouter success model=%s after %.0fms", model, elapsed_ms)
                    return parsed
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    retry_after = e.response.headers.get("retry-after")
                    msg = f"HTTP {status} model={model}"
                    errors.append(msg)
                    logger.error("OpenRouter %s", msg)
                    if status == 429 and attempt < self._max_retries:
                        self._sleep_before_retry(attempt, retry_after_header=retry_after)
                        continue
                    if status in _FALLBACK_STATUS and model_index < len(self._model_chain) - 1:
                        break
                    raise LLMError(_format_http_error(e, model)) from e
                except httpx.HTTPError as e:
                    errors.append(f"model={model}: {e}")
                    if model_index < len(self._model_chain) - 1:
                        break
                    raise LLMError(str(e)) from e
                except LLMError as e:
                    errors.append(f"model={model}: {str(e)[:200]}")
                    if model_index < len(self._model_chain) - 1:
                        break
                    raise

        elapsed_ms = (time.perf_counter() - started) * 1000
        summary = "; ".join(errors[-5:]) if errors else "unknown"
        raise LLMError(
            f"OpenRouter failed on all models {self._model_chain!r} after {elapsed_ms:.0f}ms: {summary}"
        )


def _dedupe_models(models: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in models:
        m = (raw or "").strip()
        if not m or m in seen:
            continue
        seen.add(m)
        out.append(m)
    return out


def _format_http_error(e: httpx.HTTPStatusError, model: str) -> str:
    status = e.response.status_code
    if status == 429:
        retry_after = e.response.headers.get("retry-after", "")
        detail = f"OpenRouter rate limit (HTTP 429) on model {model!r}."
        if retry_after:
            detail += f" Retry-After: {retry_after}s."
        detail += (
            " Wait a few minutes, add credits, or switch OPENROUTER_MODEL / LLM_PROVIDER. "
            "Free models have strict limits."
        )
        return detail
    return f"OpenRouter HTTP {status} for model {model!r}: {e.response.text[:300]}"
