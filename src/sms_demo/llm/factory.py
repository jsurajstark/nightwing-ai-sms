from sms_demo.config import Settings
from sms_demo.llm.anthropic_provider import AnthropicProvider
from sms_demo.llm.base import LLMProvider
from sms_demo.llm.bedrock_provider import BedrockProvider
from sms_demo.llm.ollama_provider import OllamaProvider


def get_provider(settings: Settings) -> LLMProvider:
    p = (settings.llm_provider or "ollama").lower().strip()
    if p == "ollama":
        return OllamaProvider(settings.ollama_host, settings.ollama_model)
    if p == "anthropic":
        return AnthropicProvider()
    if p == "bedrock":
        return BedrockProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}; use ollama|anthropic|bedrock")
