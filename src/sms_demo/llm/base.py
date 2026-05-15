from abc import ABC, abstractmethod


class LLMError(Exception):
    """Raised when the LLM provider fails or returns unusable output."""


class LLMProvider(ABC):
    @abstractmethod
    def extract_referral(self, sms_body: str, system_prompt: str) -> dict:
        """Return a dict parsed from model JSON (referral fields + optional confidence)."""
