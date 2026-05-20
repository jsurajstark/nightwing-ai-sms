"""GitHub Models inference adapter (https://docs.github.com/en/rest/models/inference)."""

from __future__ import annotations

import json
import logging
import time

import httpx

from sms_demo.llm.base import LLMError, LLMProvider

logger = logging.getLogger(__name__)

_FALLBACK_STATUS = frozenset({404, 500, 502, 503, 504, 429})


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
        detail = f"GitHub Models rate limit (HTTP 429) on model {model!r}."
        if retry_after:
            detail += f" Retry-After: {retry_after}s."
        return detail
    return (
        f"GitHub Models HTTP {status} for model {model!r}: "
        f"{e.response.text[:300]}"
    )


class GitHubModelsProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str,
        api_version: str,
        org: str | None = None,
        fallback_models: list[str] | None = None,
        timeout_s: float = 180.0,
        max_retries: int = 2,
        retry_base_s: float = 5.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._api_version = api_version.strip()
        self._org = (org or "").strip() or None
        self._timeout = timeout_s
        self._max_retries = max(0, max_retries)
        self._retry_base_s = max(0.0, retry_base_s)
        self._model_chain = _dedupe_models([model, *(fallback_models or [])])
        self._primary_model = self._model_chain[0] if self._model_chain else model
        self.last_model_used: str | None = None

    def _completion_url(self) -> str:
        if self._org:
            return f"{self._base_url}/orgs/{self._org}/inference/chat/completions"
        return f"{self._base_url}/inference/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": self._api_version,
        }

    def _chat_completion(
        self,
        url: str,
        payload: dict,
        request_timeout: float,
    ) -> dict:
        with httpx.Client(timeout=request_timeout) as client:
            response = client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise LLMError(
                f"Unexpected GitHub Models response type: {type(data).__name__}"
            )
        return data

    def _sleep_before_retry(
        self,
        attempt: int,
        *,
        retry_after_header: str | None = None,
    ) -> None:
        if retry_after_header:
            try:
                delay = float(retry_after_header.strip())
            except ValueError:
                delay = self._retry_base_s * (2**attempt)
        else:
            delay = self._retry_base_s * (2**attempt)
        delay = min(max(delay, 1.0), 120.0)
        logger.warning("GitHub Models backing off %.1fs before retry", delay)
        time.sleep(delay)

    def _extract_with_model(
        self,
        model: str,
        url: str,
        user_message: str,
        system_prompt: str,
        request_timeout: float,
        *,
        max_tokens: int,
    ) -> dict:
        payload: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
            "max_tokens": max_tokens,
        }
        try:
            data = self._chat_completion(url, payload, request_timeout)
        except httpx.HTTPStatusError as e:
            if (
                e.response.status_code == 400
                and "response_format" in payload
            ):
                logger.warning(
                    "GitHub Models model=%s rejected response_format; "
                    "retrying without JSON mode",
                    model,
                )
                fallback_payload = {
                    k: v for k, v in payload.items() if k != "response_format"
                }
                data = self._chat_completion(url, fallback_payload, request_timeout)
            else:
                raise
        return self._parse_completion(data, model)

    def _parse_completion(self, data: dict, model: str) -> dict:
        finish_reason: str | None = None
        try:
            choices = data["choices"]
            choice = choices[0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as e:
            logger.error(
                "GitHub Models unexpected response shape model=%s: %r",
                model,
                data,
            )
            raise LLMError(
                f"Unexpected GitHub Models response shape: {data!r}"
            ) from e

        content = (content or "").strip()
        if not content:
            raise LLMError(
                f"GitHub Models model {model!r} returned empty content"
            )

        if finish_reason == "length":
            logger.warning(
                "GitHub Models model=%s hit max_tokens (finish_reason=length); "
                "content=%r",
                model,
                content[:200],
            )
            raise LLMError(
                "Model response truncated (max_tokens); retry with higher limit"
            )

        logger.debug(
            "GitHub Models raw content model=%s: %s",
            model,
            content[:2000],
        )

        try:
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise LLMError(
                    f"Expected JSON object, got {type(parsed).__name__}"
                )
            logger.info(
                "GitHub Models JSON parsed model=%s keys=%s",
                model,
                list(parsed.keys()),
            )
            return parsed
        except json.JSONDecodeError as e:
            raise LLMError(f"invalid_json:{content[:500]}") from e

    def _is_retryable_llm_error(self, exc: LLMError) -> bool:
        msg = str(exc).lower()
        return (
            "truncated" in msg
            or "invalid_json:" in msg
            or "valid json" in msg
            or "empty content" in msg
        )

    def extract_referral(
        self,
        sms_body: str,
        system_prompt: str,
        *,
        timeout_s: float | None = None,
    ) -> dict:
        request_timeout = timeout_s if timeout_s is not None else self._timeout
        url = self._completion_url()
        user_message = (
            "Extract referral fields from this SMS only. "
            "Use names and numbers exactly as written in the message.\n\n"
            f"{sms_body}"
        )
        preview = (sms_body or "").replace("\n", " ")[:120]
        logger.info(
            "GitHub Models chain → url=%s models=%s timeout_s=%.0f preview=%r",
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
                    "GitHub Models falling back to model=%s (%s/%s)",
                    model,
                    model_index + 1,
                    len(self._model_chain),
                )

            for attempt in range(self._max_retries + 1):
                if attempt > 0:
                    logger.warning(
                        "GitHub Models retry model=%s attempt %s/%s",
                        model,
                        attempt + 1,
                        self._max_retries + 1,
                    )

                max_tokens = 2048 if attempt == 0 else 4096
                try:
                    parsed = self._extract_with_model(
                        model,
                        url,
                        user_message,
                        system_prompt,
                        request_timeout,
                        max_tokens=max_tokens,
                    )
                    self.last_model_used = model
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    logger.info(
                        "GitHub Models success model=%s max_tokens=%s after %.0fms",
                        model,
                        max_tokens,
                        elapsed_ms,
                    )
                    return parsed
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    retry_after = e.response.headers.get("retry-after")
                    msg = f"HTTP {status} model={model}"
                    errors.append(msg)
                    logger.error("GitHub Models %s", msg)
                    if status == 429 and attempt < self._max_retries:
                        self._sleep_before_retry(
                            attempt,
                            retry_after_header=retry_after,
                        )
                        continue
                    if (
                        status in _FALLBACK_STATUS
                        and model_index < len(self._model_chain) - 1
                    ):
                        break
                    raise LLMError(_format_http_error(e, model)) from e
                except httpx.HTTPError as e:
                    errors.append(f"model={model}: {e}")
                    if model_index < len(self._model_chain) - 1:
                        break
                    raise LLMError(str(e)) from e
                except LLMError as e:
                    errors.append(f"model={model}: {str(e)[:200]}")
                    if self._is_retryable_llm_error(e) and attempt < self._max_retries:
                        logger.warning(
                            "GitHub Models retryable error model=%s attempt %s/%s: %s",
                            model,
                            attempt + 1,
                            self._max_retries + 1,
                            str(e)[:120],
                        )
                        continue
                    if model_index < len(self._model_chain) - 1:
                        break
                    if str(e).startswith("invalid_json:"):
                        raise LLMError(
                            "Model did not return valid JSON: "
                            + str(e)[len("invalid_json:") :]
                        ) from e
                    raise

        elapsed_ms = (time.perf_counter() - started) * 1000
        summary = "; ".join(errors[-5:]) if errors else "unknown"
        raise LLMError(
            f"GitHub Models failed on all models {self._model_chain!r} "
            f"after {elapsed_ms:.0f}ms: {summary}"
        )
