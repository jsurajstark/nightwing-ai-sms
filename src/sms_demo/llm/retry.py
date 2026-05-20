from __future__ import annotations

import logging

import httpx

from sms_demo.config import Settings
from sms_demo.llm.base import LLMError, LLMProvider

logger = logging.getLogger(__name__)


def is_llm_timeout(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        return is_llm_timeout(cause)
    msg = str(exc).lower()
    return "timeout" in msg or "timed out" in msg


def is_retryable_llm_error(exc: LLMError) -> bool:
    if is_llm_timeout(exc):
        return True
    return bool(getattr(exc, "retryable", False))


def extract_with_retries(
    provider: LLMProvider,
    sms_body: str,
    system_prompt: str,
    settings: Settings,
) -> dict:
    """
    Call the LLM with escalating timeouts on retryable failures.

    Retries on timeouts and invalid/truncated JSON (transient model output).

    Attempt 1: llm_timeout_s (default 180s)
    Retry 1:   + llm_timeout_increment_s (210s)
    Retry 2:   + 2 * increment (240s)
    """
    last_error: LLMError | None = None
    max_attempts = settings.llm_max_retries + 1

    for attempt in range(max_attempts):
        timeout_s = settings.llm_timeout_s + attempt * settings.llm_timeout_increment_s
        try:
            if attempt > 0:
                logger.warning(
                    "LLM retry attempt %s/%s timeout_s=%.0f",
                    attempt + 1,
                    max_attempts,
                    timeout_s,
                )
            return provider.extract_referral(
                sms_body, system_prompt, timeout_s=timeout_s
            )
        except LLMError as e:
            last_error = e
            if not is_retryable_llm_error(e) or attempt >= settings.llm_max_retries:
                raise
            logger.warning(
                "LLM retryable failure on attempt %s/%s (timeout_s=%.0f): %s",
                attempt + 1,
                max_attempts,
                timeout_s,
                e,
            )

    assert last_error is not None
    raise last_error
