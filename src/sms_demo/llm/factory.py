from sms_demo.config import Settings
from sms_demo.llm.anthropic_provider import AnthropicProvider
from sms_demo.llm.base import LLMProvider
from sms_demo.llm.bedrock_provider import BedrockProvider
from sms_demo.llm.gemini_provider import GeminiProvider
from sms_demo.llm.ollama_provider import OllamaProvider


def get_provider(settings: Settings) -> LLMProvider:
    p = (settings.llm_provider or "ollama").lower().strip()
    if p == "ollama":
        return OllamaProvider(
            settings.ollama_host,
            settings.ollama_model,
            timeout_s=settings.llm_timeout_s,
        )
    if p == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
        return GeminiProvider(
            settings.google_api_key,
            settings.gemini_model,
            timeout_s=settings.llm_timeout_s,
        )
    if p == "anthropic":
        return AnthropicProvider()
    if p == "bedrock":
        return BedrockProvider()
    raise ValueError(
        f"Unknown LLM_PROVIDER: {settings.llm_provider!r}; use ollama|gemini|anthropic|bedrock"
    )
