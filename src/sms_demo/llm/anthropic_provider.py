from sms_demo.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def extract_referral(self, sms_body: str, system_prompt: str) -> dict:
        raise NotImplementedError(
            "AnthropicProvider is not implemented in this demo; set LLM_PROVIDER=ollama "
            "or extend llm/anthropic_provider.py."
        )
