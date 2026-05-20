"""Parse and log LLM provider API errors in a readable, structured form."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from typing import Any

from sms_demo.llm.base import LLMError

_RE_LEADING_HTTP = re.compile(r"^(\d{3})\s+(\w+)\.\s*(.*)$", re.DOTALL)
_RE_RETRY_DELAY = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)


@dataclass(frozen=True)
class ApiErrorSummary:
    http_code: int | None
    status: str | None
    message: str
    retry_after_s: float | None
    quota_notes: tuple[str, ...]

    @property
    def short_message(self) -> str:
        """Single-line message for DB / routing (no embedded dicts)."""
        text = (self.message or "LLM request failed").strip()
        text = text.split("\n")[0].strip()
        if len(text) > 240:
            text = text[:237] + "..."
        return text

    @property
    def routing_reason(self) -> str:
        parts: list[str] = ["llm_error"]
        if self.http_code is not None:
            parts.append(str(self.http_code))
        if self.status:
            parts.append(self.status)
        parts.append(self.short_message)
        return ":".join(parts)


def _first_line(text: str | None, *, max_len: int = 500) -> str:
    if not text:
        return ""
    line = str(text).strip().split("\n")[0].strip()
    if len(line) > max_len:
        return line[: max_len - 3] + "..."
    return line


def _parse_retry_after_s(message: str | None, details: Any) -> float | None:
    if message:
        m = _RE_RETRY_DELAY.search(message)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

    detail_list: list[Any] = []
    if isinstance(details, dict):
        err = details.get("error")
        if isinstance(err, dict):
            detail_list = err.get("details") or []
        detail_list = detail_list or details.get("details") or []

    for item in detail_list:
        if not isinstance(item, dict):
            continue
        if "RetryInfo" in str(item.get("@type", "")):
            delay = item.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                try:
                    return float(delay[:-1])
                except ValueError:
                    pass
            if isinstance(delay, (int, float)):
                return float(delay)
    return None


def _quota_notes_from_details(details: Any) -> tuple[str, ...]:
    notes: list[str] = []
    detail_list: list[Any] = []
    if isinstance(details, dict):
        err = details.get("error")
        if isinstance(err, dict):
            detail_list = err.get("details") or []
        detail_list = detail_list or details.get("details") or []

    for item in detail_list:
        if not isinstance(item, dict):
            continue
        if "QuotaFailure" not in str(item.get("@type", "")):
            continue
        for v in item.get("violations") or []:
            if not isinstance(v, dict):
                continue
            metric = v.get("quotaMetric", "quota")
            model = (v.get("quotaDimensions") or {}).get("model", "")
            suffix = f" model={model}" if model else ""
            notes.append(f"{metric}{suffix}")
    return tuple(notes)


def summarize_api_error(exc: BaseException) -> ApiErrorSummary:
    """Build a compact summary from google-genai APIError or stringified errors."""
    code: int | None = getattr(exc, "code", None)
    status: str | None = getattr(exc, "status", None)
    message: str | None = getattr(exc, "message", None)
    details: Any = getattr(exc, "details", None)

    if message is None:
        raw = str(exc).strip()
        m = _RE_LEADING_HTTP.match(raw)
        if m:
            try:
                code = int(m.group(1))
            except ValueError:
                pass
            status = m.group(2)
            tail = m.group(3).strip()
            if tail.startswith("{") and tail.endswith("}"):
                try:
                    details = ast.literal_eval(tail)
                    if isinstance(details, dict):
                        err = details.get("error")
                        if isinstance(err, dict):
                            message = err.get("message")
                            code = code or err.get("code")
                            status = status or err.get("status")
                except (SyntaxError, ValueError):
                    message = _first_line(tail)
            else:
                message = _first_line(tail)
        else:
            message = _first_line(raw)

    message = _first_line(message or str(exc))
    retry_after_s = _parse_retry_after_s(message, details)
    quota_notes = _quota_notes_from_details(details)

    return ApiErrorSummary(
        http_code=int(code) if code is not None else None,
        status=status,
        message=message,
        retry_after_s=retry_after_s,
        quota_notes=quota_notes,
    )


def llm_error_from_exception(exc: BaseException) -> LLMError:
    summary = summarize_api_error(exc)
    return LLMError(
        summary.short_message,
        http_code=summary.http_code,
        status=summary.status,
        retry_after_s=summary.retry_after_s,
    )


def log_llm_api_failure(
    logger: logging.Logger,
    *,
    provider: str,
    model: str,
    elapsed_ms: float,
    exc: BaseException,
) -> ApiErrorSummary:
    """Emit a multi-line, structured error block (readable in uvicorn terminal)."""
    summary = summarize_api_error(exc)

    lines = [
        f"── {provider} request failed ──",
        f"  model          : {model}",
        f"  elapsed        : {elapsed_ms:.0f} ms",
        f"  http_code      : {summary.http_code if summary.http_code is not None else '—'}",
        f"  status         : {summary.status or '—'}",
    ]
    if summary.retry_after_s is not None:
        lines.append(f"  retry_after    : {summary.retry_after_s:.0f} s")
    lines.append(f"  message        : {summary.message}")
    for note in summary.quota_notes[:5]:
        lines.append(f"  quota          : {note}")
    if len(summary.quota_notes) > 5:
        lines.append(f"  quota          : … +{len(summary.quota_notes) - 5} more")

    if summary.http_code == 429:
        lines.append(
            "  hint           : Gemini free-tier quota exhausted for this model/project. "
            "Wait for retry_after, switch GEMINI_MODEL, enable billing, or use LLM_PROVIDER=ollama."
        )

    logger.error("\n".join(lines))
    return summary
