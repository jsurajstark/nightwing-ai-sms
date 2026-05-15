from sms_demo.llm.base import LLMProvider


class BedrockProvider(LLMProvider):
    def extract_referral(self, sms_body: str, system_prompt: str) -> dict:
        raise NotImplementedError(
            "BedrockProvider is not implemented in this demo; set LLM_PROVIDER=ollama "
            "or extend llm/bedrock_provider.py."
        )
