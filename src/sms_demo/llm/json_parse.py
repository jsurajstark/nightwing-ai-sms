"""Parse JSON objects from LLM text responses."""

from __future__ import annotations

import json
import re

from sms_demo.llm.base import LLMError

_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)


def _strip_markdown_fence(content: str) -> str:
    match = _FENCE_RE.match(content.strip())
    if match:
        return match.group(1).strip()
    return content.strip()


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        return content[start : end + 1]
    return content


def parse_llm_json(content: str, *, preview_len: int = 500) -> dict:
    """Parse a JSON object from model output; raise LLMError when invalid."""
    text = _strip_markdown_fence(content or "")
    if not text:
        raise LLMError("Model returned empty content", retryable=True)

    candidates = [text]
    extracted = _extract_json_object(text)
    if extracted != text:
        candidates.append(extracted)

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                raise LLMError(
                    f"Expected JSON object, got {type(parsed).__name__}",
                    retryable=False,
                )
            return parsed
        except json.JSONDecodeError as e:
            last_error = e

    preview = text[:preview_len]
    raise LLMError(
        f"Model did not return valid JSON: {preview}",
        retryable=True,
    ) from last_error
