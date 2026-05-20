from abc import ABC, abstractmethod


class LLMError(Exception):
    """Raised when the LLM provider fails or returns unusable output."""

    def __init__(
        self,
        message: str,
        *,
        http_code: int | None = None,
        status: str | None = None,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message)
        self.http_code = http_code
        self.status = status
        self.retry_after_s = retry_after_s

    @property
    def routing_reason(self) -> str:
        parts: list[str] = ["llm_error"]
        if self.http_code is not None:
            parts.append(str(self.http_code))
        if self.status:
            parts.append(self.status)
        msg = str(self.args[0]) if self.args else ""
        msg = msg.split("\n")[0].strip()
        if len(msg) > 200:
            msg = msg[:197] + "..."
        if msg:
            parts.append(msg)
        return ":".join(parts)


class LLMProvider(ABC):
    @abstractmethod
    def extract_referral(self, sms_body: str, system_prompt: str) -> dict:
        """Return a dict parsed from model JSON (referral fields + optional confidence)."""
